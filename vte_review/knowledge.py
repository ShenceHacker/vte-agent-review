"""Local SQLite knowledge library, FTS5 retrieval, and immutable run snapshots."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .contracts import ContractError, ROLES, strings, text
from .retrieval import EvidenceIndex, terms

MAX_TEXT = 2_000_000
STOP_WORDS = frozenset("a an and are as at be by for from in is it of on or that the this to with case_id question facts missing_information".split())


def search_tokens(value: str) -> str:
    return " ".join(sorted(terms(value) - STOP_WORDS))


def match_query(value: str) -> str:
    return " OR ".join('"' + token + '"' for token in sorted(terms(value) - STOP_WORDS)[:128])


def split_text(value: str, size: int = 1200, overlap: int = 150) -> list[tuple[int, int, str]]:
    """Chunk normalized text with character offsets and a small context overlap."""
    out, start = [], 0
    while start < len(value):
        end = min(start + size, len(value))
        if end < len(value):
            boundary = max(value.rfind("\n", start + size // 2, end), value.rfind(" ", start + size // 2, end))
            if boundary > start:
                end = boundary
        if value[start:end].strip():
            out.append((start, end, value[start:end].strip()))
        if end == len(value):
            break
        start = max(start + 1, end - overlap)
    return out


def validate_document(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise ContractError("Document must be an object")
    doc = {}
    for key, limit in (("title", 500), ("source", 2000), ("version", 200)):
        doc[key] = text(raw.get(key), key).strip()
        if len(doc[key]) > limit:
            raise ContractError(f"{key} exceeds {limit} characters")
    doc["roles"] = strings(raw.get("roles"), "roles", set(ROLES))
    if not doc["roles"] or not isinstance(raw.get("synthetic"), bool):
        raise ContractError("Select at least one role and specify synthetic as true or false")
    doc["roles"] = sorted(doc["roles"])
    doc["synthetic"] = raw["synthetic"]
    doc["text"] = text(raw.get("text"), "text").replace("\r\n", "\n").replace("\x00", "").strip()
    if not doc["text"] or len(doc["text"]) > MAX_TEXT:
        raise ContractError(f"Document text must contain 1–{MAX_TEXT:,} characters")
    return doc


class KnowledgeStore:
    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, source TEXT NOT NULL,
                    version TEXT NOT NULL, roles TEXT NOT NULL, synthetic INTEGER NOT NULL,
                    text TEXT NOT NULL, digest TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL,
                    archived INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id),
                    ordinal INTEGER NOT NULL, start_offset INTEGER NOT NULL,
                    end_offset INTEGER NOT NULL, text TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS chunks_document ON chunks(document_id);
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(id UNINDEXED, title, body);
                PRAGMA user_version=1;
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def serialize(row) -> dict:
        item = dict(row)
        item["roles"] = json.loads(item["roles"])
        item["synthetic"] = bool(item["synthetic"])
        item["archived"] = bool(item.get("archived"))
        item.pop("digest", None)
        return item

    def stats(self) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT count(*) AS documents, coalesce(sum(synthetic),0) AS synthetic FROM documents WHERE archived=0").fetchone()
            return {**dict(row), "chunks": db.execute("SELECT count(*) FROM chunks c JOIN documents d ON d.id=c.document_id WHERE d.archived=0").fetchone()[0],
                    "storage": "SQLite", "retrieval": "FTS5 / BM25", "path": str(self.path)}

    def list_documents(self, archived: bool = False) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("""SELECT d.id,d.title,d.source,d.version,d.roles,d.synthetic,d.created_at,d.archived,
                                 length(d.text) AS characters,count(c.id) AS chunks
                                 FROM documents d LEFT JOIN chunks c ON c.document_id=d.id
                                 WHERE d.archived=? GROUP BY d.id ORDER BY d.created_at DESC,d.id""", (int(archived),)).fetchall()
            return [self.serialize(row) for row in rows]

    def get(self, document_id: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
            if row is None:
                raise LookupError("Document not found")
            doc = self.serialize(row)
            doc["chunks"] = [dict(chunk) for chunk in db.execute("SELECT id,ordinal,start_offset,end_offset,text FROM chunks WHERE document_id=? ORDER BY ordinal", (document_id,))]
            return doc

    def add_many(self, values: list[dict]) -> dict:
        if not isinstance(values, list) or not 1 <= len(values) <= 500:
            raise ContractError("Import between 1 and 500 documents at a time")
        docs = [validate_document(value) for value in values]
        ids, created, restored = [], 0, 0
        with self.connect() as db:
            for doc in docs:
                digest = hashlib.sha256(json.dumps(doc, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
                existing = db.execute("SELECT id,archived FROM documents WHERE digest=?", (digest,)).fetchone()
                if existing:
                    ids.append(existing["id"])
                    if existing["archived"]:
                        db.execute("UPDATE documents SET archived=0 WHERE id=?", (existing["id"],))
                        restored += 1
                    continue
                document_id = "KB-" + uuid4().hex
                db.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,0)",
                           (document_id, doc["title"], doc["source"], doc["version"], json.dumps(doc["roles"]),
                            int(doc["synthetic"]), doc["text"], digest, datetime.now(timezone.utc).isoformat()))
                for n, (start, end, content) in enumerate(split_text(doc["text"]), 1):
                    chunk_id = f"{document_id}-{n:04d}"
                    db.execute("INSERT INTO chunks VALUES (?,?,?,?,?,?)", (chunk_id, document_id, n, start, end, content))
                    db.execute("INSERT INTO chunks_fts VALUES (?,?,?)", (chunk_id, search_tokens(doc["title"]), search_tokens(content)))
                created += 1
                ids.append(document_id)
        return {"ids": list(dict.fromkeys(ids)), "created": created, "restored": restored, "duplicates": len(docs) - created - restored}

    def archive(self, document_id: str, archived: bool) -> dict:
        if not isinstance(archived, bool):
            raise ContractError("archived must be a boolean")
        with self.connect() as db:
            if db.execute("UPDATE documents SET archived=? WHERE id=?", (int(archived), document_id)).rowcount != 1:
                raise LookupError("Document not found")
        return {"id": document_id, "archived": archived}

    def search(self, query: str, role: str = "", limit: int = 20) -> list[dict]:
        if role and role not in ROLES:
            raise ContractError("Unknown specialist role")
        if not 1 <= limit <= 100:
            raise ContractError("Search limit must be between 1 and 100")
        expression = match_query(query)
        if not expression:
            return []
        with self.connect() as db:
            rows = db.execute("""SELECT c.id,c.document_id,c.ordinal,c.text,d.title,d.source,d.version,d.roles,d.synthetic,
                                 bm25(chunks_fts,0,5,1) AS rank
                                 FROM chunks_fts JOIN chunks c ON c.id=chunks_fts.id JOIN documents d ON d.id=c.document_id
                                 WHERE chunks_fts MATCH ? AND d.archived=0 AND (?='' OR d.roles LIKE ?)
                                 ORDER BY rank,c.id LIMIT ?""", (expression, role, f'%"{role}"%', limit)).fetchall()
            return [self.serialize(row) for row in rows]

    def snapshot(self, ids: list[str]) -> list[dict]:
        strings(ids, "knowledge_ids")
        if not 1 <= len(ids) <= 500:
            raise ContractError("Select between 1 and 500 knowledge documents")
        placeholders = ",".join("?" for _ in ids)
        with self.connect() as db:
            found = db.execute(f"SELECT id FROM documents WHERE archived=0 AND id IN ({placeholders})", ids).fetchall()
            if {row["id"] for row in found} != set(ids):
                raise ContractError("A selected document is archived or no longer available")
            rows = db.execute(f"""SELECT c.id,d.title,d.source,d.version,c.text,d.roles,d.synthetic
                                  FROM chunks c JOIN documents d ON d.id=c.document_id
                                  WHERE d.id IN ({placeholders}) ORDER BY c.document_id,c.ordinal""", ids).fetchall()
            return [{k: v for k, v in self.serialize(row).items() if k != "archived"} for row in rows]


class SQLiteEvidenceIndex(EvidenceIndex):
    """FTS5 over a frozen copy of selected evidence, independent of later library changes."""
    def __init__(self, documents: list[dict]):
        super().__init__(documents)
        self.lock = threading.Lock()
        self.db = sqlite3.connect(":memory:", check_same_thread=False)
        self.db.execute("CREATE VIRTUAL TABLE evidence USING fts5(id UNINDEXED, roles UNINDEXED, title, body)")
        self.db.executemany("INSERT INTO evidence VALUES (?,?,?,?)", [
            (doc["id"], json.dumps(doc["roles"]), search_tokens(doc["title"]), search_tokens(doc["text"]))
            for doc in self.documents.values()])

    def search(self, query: str, role: str, top_k: int = 4) -> list[dict]:
        if role not in ROLES or top_k < 1:
            raise ValueError("Invalid retrieval settings")
        key = (query, role, top_k)
        with self.lock:
            if key not in self._cache:
                expression = match_query(query)
                rows = self.db.execute("SELECT id FROM evidence WHERE evidence MATCH ? AND roles LIKE ? ORDER BY bm25(evidence,0,0,5,1),id LIMIT ?",
                                       (expression, f'%"{role}"%', top_k)).fetchall() if expression else []
                self._cache[key] = [self.documents[row[0]] for row in rows]
            return deepcopy(self._cache[key])

    def close(self):
        self.db.close()
