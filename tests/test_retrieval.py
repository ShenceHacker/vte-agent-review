import unittest
from copy import deepcopy

from vte_review.contracts import ContractError
from vte_review.demo import DEMO_EVIDENCE
from vte_review.retrieval import EvidenceIndex


class RetrievalTests(unittest.TestCase):
    def test_no_match_is_not_arbitrary_evidence(self):
        index = EvidenceIndex(DEMO_EVIDENCE)
        self.assertEqual(index.search("xyz-nomatch", "A"), [])

    def test_cache_returns_isolated_copies(self):
        index = EvidenceIndex(DEMO_EVIDENCE)
        found = index.search("VTE", "A")
        found[0]["text"] = "tampered"
        self.assertNotEqual(index.search("VTE", "A")[0]["text"], "tampered")

    def test_role_filter_and_chinese_terms(self):
        docs = deepcopy(DEMO_EVIDENCE)
        docs[0]["roles"] = ["B"]
        index = EvidenceIndex(docs)
        self.assertEqual(index.search("药物安全", "A"), [])
        self.assertEqual(len(index.search("药物安全", "B")), 1)

    def test_duplicate_id_rejected(self):
        with self.assertRaises(ContractError):
            EvidenceIndex(DEMO_EVIDENCE + DEMO_EVIDENCE)
