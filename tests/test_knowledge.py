import tempfile
import unittest
from pathlib import Path

from vte_review.contracts import ContractError
from vte_review.knowledge import KnowledgeStore, SQLiteEvidenceIndex, split_text


def document(**changes):
    return {"title": "VTE protocol fixture", "source": "local:test", "version": "test-v1",
            "roles": ["A", "B", "C"], "synthetic": True,
            "text": "Synthetic VTE anticoagulation duration and medication safety reassessment checkpoint.", **changes}


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "knowledge.sqlite3"
        self.store = KnowledgeStore(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_persistence_deduplication_and_metadata(self):
        added = self.store.add_many([document()])
        reopened = KnowledgeStore(self.path)
        self.assertEqual(reopened.stats()["documents"], 1)
        self.assertEqual(reopened.get(added["ids"][0])["text"], document()["text"])
        duplicate = reopened.add_many([document()])
        self.assertEqual(duplicate["duplicates"], 1)
        self.assertEqual(duplicate["ids"], added["ids"])

    def test_import_is_atomic_on_invalid_entry(self):
        with self.assertRaises(ContractError):
            self.store.add_many([document(), document(roles=["UNKNOWN"])])
        self.assertEqual(self.store.stats()["documents"], 0)

    def test_full_text_search_role_filter_and_unmatched_query(self):
        self.store.add_many([document(roles=["B"], text="药物安全 肾功能 Dose adjustment")])
        self.assertEqual(self.store.search("药物安全", "A"), [])
        self.assertEqual(len(self.store.search("药物安全", "B")), 1)
        self.assertEqual(len(self.store.search('"dose" OR ???', "B")), 1)
        self.assertEqual(self.store.search("nonmatchingxyz"), [])
        self.assertEqual(self.store.search("* AND ()"), [])

    def test_title_weighted_bm25_ranking(self):
        a = document(title="Apixaban", text="Long source text " * 20, source="local:first")
        b = document(title="Other protocol", text="Apixaban " + "unrelated term " * 100, source="local:second")
        ids = self.store.add_many([a, b])["ids"]
        self.assertEqual(self.store.search("apixaban")[0]["document_id"], ids[0])

    def test_archival_is_reversible_and_removes_search_hits(self):
        doc_id = self.store.add_many([document()])["ids"][0]
        self.store.archive(doc_id, True)
        self.assertEqual(self.store.search("VTE"), [])
        self.assertEqual(len(self.store.list_documents(True)), 1)
        with self.assertRaises(ContractError):
            self.store.snapshot([doc_id])
        self.store.archive(doc_id, False)
        self.assertEqual(len(self.store.search("VTE")), 1)

    def test_snapshot_keeps_original_evidence_after_archival(self):
        doc_id = self.store.add_many([document()])["ids"][0]
        frozen = SQLiteEvidenceIndex(self.store.snapshot([doc_id]))
        try:
            self.store.archive(doc_id, True)
            result = frozen.search("VTE medication", "B")
            self.assertEqual(result[0]["text"], document()["text"])
            result[0]["text"] = "tampered"
            self.assertEqual(frozen.search("VTE medication", "B")[0]["text"], document()["text"])
        finally:
            frozen.close()

    def test_chunks_cover_text_and_preserve_offsets(self):
        value = ("Synthetic source paragraph. " * 120).strip()
        parts = split_text(value)
        self.assertGreater(len(parts), 1)
        self.assertEqual(parts[0][0], 0)
        self.assertEqual(parts[-1][1], len(value))
        for start, end, passage in parts:
            self.assertEqual(passage, value[start:end].strip())
        for first, second in zip(parts, parts[1:]):
            self.assertLess(second[0], first[1])

    def test_empty_and_missing_document_selection_fail_closed(self):
        for ids in ([], ["KB-missing"], None):
            with self.subTest(ids=ids), self.assertRaises(ContractError):
                self.store.snapshot(ids)


if __name__ == "__main__":
    unittest.main()
