"""Local neural embeddings, persistent content cache and frozen hybrid retrieval."""
from __future__ import annotations

from array import array
from copy import deepcopy
from contextlib import contextmanager
import hashlib
import importlib.util
import math
import os
from pathlib import Path
import sqlite3
import threading

from .knowledge import SQLiteEvidenceIndex

MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
ENCODING = "mean-480chars-v1"


def normalize(vector):
    norm = math.sqrt(sum(x*x for x in vector))
    if not norm or not all(math.isfinite(x) for x in vector):
        raise ValueError("Embedding model returned an invalid vector")
    return [float(x / norm) for x in vector]


class VectorStore:
    def __init__(self, root, encoder=None, enabled=None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "vectors.sqlite3"
        self.model_name = MODEL
        self.encoder = encoder
        self.lock = threading.RLock()
        self.enabled = (os.environ.get("VTE_VECTOR_ENABLED", "1") != "0") if enabled is None else enabled
        self.available = encoder is not None or importlib.util.find_spec("fastembed") is not None
        self.state = "ready" if encoder else "not_loaded"
        self.error = None
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS embeddings (key TEXT PRIMARY KEY, model TEXT NOT NULL, vector BLOB NOT NULL)")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        try:
            with db:
                yield db
        finally:
            db.close()

    @property
    def active(self):
        return self.enabled and self.available

    def status(self):
        with self.connect() as db:
            count = db.execute("SELECT count(*) FROM embeddings WHERE model=?", (self.model_name + ":" + ENCODING,)).fetchone()[0]
        return {"enabled": self.enabled, "available": self.available, "state": self.state,
                "model": self.model_name, "cached_texts": count, "error": self.error,
                "method": "FTS5 BM25 + multilingual cosine / RRF" if self.active else "SQLite FTS5 / BM25",
                "fallback_reason": None if self.active else "Vector retrieval disabled or fastembed is not installed"}

    def _encode(self, texts):
        if self.encoder is None:
            self.state = "loading"
            from fastembed import TextEmbedding
            self.encoder = TextEmbedding(self.model_name, cache_dir=str(self.root / "embedding-models"), threads=4)
        return list(self.encoder.embed(texts, batch_size=16))

    def embed(self, texts):
        if not self.active:
            raise ValueError("Install the vector extra and enable vector retrieval")
        identity = self.model_name + ":" + ENCODING
        keys = [hashlib.sha256((identity + "\0" + t).encode()).hexdigest() for t in texts]
        with self.lock, self.connect() as db:
            found = {}
            for key in set(keys):
                row = db.execute("SELECT vector FROM embeddings WHERE key=?", (key,)).fetchone()
                if row:
                    a = array("f")
                    a.frombytes(row[0])
                    found[key] = list(a)
            missing = dict((k, t) for k, t in zip(keys, texts) if k not in found)
            try:
                if missing:
                    self.state = "indexing"
                    # Small windows prevent silently dropping the tail of long clinical paragraphs.
                    segments, owners = [], []
                    for key, value in missing.items():
                        for start in range(0, max(1, len(value)), 440):
                            segments.append(value[start:start+480] or " ")
                            owners.append(key)
                    vectors = self._encode(segments)
                    if len(vectors) != len(segments):
                        raise ValueError("Embedding count mismatch")
                    groups = {k: [] for k in missing}
                    for key, vector in zip(owners, vectors):
                        groups[key].append(normalize(vector))
                    for key, group in groups.items():
                        found[key] = normalize([sum(v[i] for v in group) / len(group) for i in range(len(group[0]))])
                        db.execute("INSERT OR REPLACE INTO embeddings VALUES (?,?,?)", (key, identity, array("f", found[key]).tobytes()))
                self.state, self.error = "ready", None
            except Exception as exc:
                self.state, self.error = "error", type(exc).__name__
                raise ValueError("Vector indexing failed. Check the local embedding model and retry.") from exc
            return [found[key] for key in keys]


class HybridEvidenceIndex(SQLiteEvidenceIndex):
    """Both rankers see exactly the same immutable, role-filtered evidence snapshot."""
    def __init__(self, documents, vectors):
        super().__init__(documents)
        self.vectors = vectors
        self._matrix = None
        self.vector_lock = threading.RLock()
        self.traces = []

    def search(self, query, role, top_k=5):
        if not self.vectors.active:
            return super().search(query, role, top_k)
        with self.vector_lock:
            if self._matrix is None:
                docs = list(self.documents.values())
                embedded = self.vectors.embed([d["title"] + "\n" + d["text"] for d in docs])
                self._matrix = dict(zip((d["id"] for d in docs), embedded))
            q = self.vectors.embed([query])[0]
            eligible = {k: d for k, d in self.documents.items() if role in d["roles"]}
            dense = sorted(((k, sum(a*b for a, b in zip(q, self._matrix[k]))) for k in eligible), key=lambda x: (-x[1], x[0]))
            pool = max(20, top_k * 4)
            dense = [k for k, score in dense[:pool]]
            sparse = [d["id"] for d in super().search(query, role, pool)]
            scores = {}
            for ranking in (dense, sparse):
                for rank, key in enumerate(ranking, 1):
                    scores[key] = scores.get(key, 0) + 1 / (60 + rank)
            chosen = sorted(scores, key=lambda k: (-scores[k], k))[:top_k]
            self.traces.append({"role": role, "query": query, "vector_ids": dense, "keyword_ids": sparse,
                                "selected_ids": chosen, "fusion": "RRF", "rrf_k": 60, "model": self.vectors.model_name})
            return deepcopy([eligible[k] for k in chosen])
