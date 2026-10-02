"""Replaceable local lexical retrieval, with explicit source/version metadata."""
from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path

from .contracts import ContractError, ROLES, object_fields, strings, text


def terms(value: str) -> set[str]:
    tokens = set(re.findall(r"[a-z0-9]+", value.lower()))
    for run in re.findall(r"[\u4e00-\u9fff]+", value):
        tokens.update(run[i:i + 2] for i in range(max(1, len(run) - 1)))
    return tokens


class EvidenceIndex:
    def __init__(self, documents: list[dict]):
        if not isinstance(documents, list) or not documents:
            raise ContractError("evidence: expected nonempty document list")
        self.documents = {}
        for doc in documents:
            object_fields(doc, {"id", "title", "source", "version", "text", "roles", "synthetic"}, "evidence")
            for key in ("id", "title", "source", "version", "text"):
                text(doc[key], f"evidence {key}")
            strings(doc["roles"], "evidence roles", set(ROLES))
            if not doc["roles"] or not isinstance(doc["synthetic"], bool):
                raise ContractError("evidence needs roles and boolean synthetic flag")
            if doc["id"] in self.documents:
                raise ContractError("duplicate evidence ID")
            self.documents[doc["id"]] = deepcopy(doc)
        self._cache: dict[tuple, list[dict]] = {}

    @classmethod
    def from_file(cls, path: str | Path) -> EvidenceIndex:
        return cls(json.loads(Path(path).read_text(encoding="utf-8-sig")))

    def search(self, query: str, role: str, top_k: int = 4) -> list[dict]:
        if top_k < 1 or role not in ROLES:
            raise ValueError("invalid retrieval settings")
        key = (query, role, top_k)
        if key not in self._cache:
            query_terms = terms(query)
            ranked = []
            for doc in self.documents.values():
                if role in doc["roles"]:
                    score = len(query_terms & terms(doc["title"] + " " + doc["text"]))
                    if score > 0:
                        ranked.append((score, doc["id"], doc))
            ranked.sort(key=lambda x: (-x[0], x[1]))
            self._cache[key] = [doc for _, _, doc in ranked[:top_k]]
        return deepcopy(self._cache[key])
