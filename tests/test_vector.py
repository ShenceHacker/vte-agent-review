from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from vte_review.knowledge import KnowledgeStore
from vte_review.vector import VectorStore, HybridEvidenceIndex


class SemanticFixture:
    """Explicit controlled vectors test ranking/caching, not embedding model quality."""
    def __init__(self):
        self.calls = []

    def embed(self, texts, **kwargs):
        self.calls.extend(texts)
        for value in texts:
            if any(t in value for t in ("renal", "肾", "kidney")):
                yield [1., 0., 0.]
            elif "bleeding" in value:
                yield [0., 1., 0.]
            else:
                yield [0., 0., 1.]


class HybridTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.encoder = SemanticFixture()
        self.vectors = VectorStore(Path(self.temp.name), self.encoder, enabled=True)
        self.docs = [
            {"id": "renal", "title": "Renal dose", "source": "fixture", "version": "1", "text": "renal impairment requires reviewing eligibility", "roles": ["B"], "synthetic": True},
            {"id": "bleed", "title": "Patient status", "source": "fixture", "version": "1", "text": "bleeding and hemoglobin change", "roles": ["C"], "synthetic": True},
            {"id": "goals", "title": "Treatment goals", "source": "fixture", "version": "1", "text": "DVT treatment duration", "roles": ["A", "B"], "synthetic": True},
        ]

    def tearDown(self):
        self.temp.cleanup()

    def test_semantic_match_without_keyword_and_role_filter(self):
        index = HybridEvidenceIndex(self.docs, self.vectors)
        try:
            result = index.search("肾功能下降", "B", 1)
            self.assertEqual(result[0]["id"], "renal")
            self.assertEqual(index.traces[-1]["keyword_ids"], [])
            self.assertEqual(index.search("renal bleeding", "C", 1)[0]["id"], "bleed")
            result[0]["text"] = "mutated"
            self.assertNotEqual(index.search("肾功能下降", "B", 1)[0]["text"], "mutated")
        finally:
            index.close()

    def test_persistent_dedup_and_changed_text_reindex(self):
        self.vectors.embed(["renal", "renal", "bleeding"])
        self.assertEqual(len(self.encoder.calls), 2)
        another = VectorStore(self.temp.name, self.encoder, enabled=True)
        another.embed(["renal", "bleeding"])
        self.assertEqual(len(self.encoder.calls), 2)
        another.embed(["renal changed"])
        self.assertEqual(len(self.encoder.calls), 3)
        self.assertEqual(another.status()["cached_texts"], 3)

    def test_archive_cannot_change_frozen_snapshot(self):
        knowledge = KnowledgeStore(Path(self.temp.name)/"knowledge.sqlite3")
        ids = knowledge.add_many([{k:v for k,v in d.items() if k != "id"} for d in self.docs])["ids"]
        index = HybridEvidenceIndex(knowledge.snapshot(ids), self.vectors)
        try:
            before = index.search("肾", "B", 1)
            knowledge.archive(ids[0], True)
            with self.assertRaises(ValueError):
                knowledge.snapshot(ids)
            self.assertEqual(index.search("肾", "B", 1), before)
        finally:
            index.close()

    def test_vector_failure_is_explicit_not_silent_keyword_success(self):
        class Broken:
            def embed(self, *args, **kwargs):
                raise RuntimeError("unavailable")
        self.vectors.encoder = Broken()
        index = HybridEvidenceIndex(self.docs, self.vectors)
        try:
            with self.assertRaisesRegex(ValueError, "Vector indexing failed"):
                index.search("renal", "B")
            self.assertEqual(self.vectors.status()["state"], "error")
        finally:
            index.close()


if __name__ == "__main__":
    unittest.main()
