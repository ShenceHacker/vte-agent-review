import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.serve_fe import configure_fe


class FELauncherTests(unittest.TestCase):
    def profile(self, root, base="https://api.forceeasyai.com", key="synthetic-only"):
        p = Path(root) / "profile.json"
        p.write_text(json.dumps({"env": {"ANTHROPIC_BASE_URL": base, "ANTHROPIC_AUTH_TOKEN": key}}))
        return p

    def test_reuses_profile_without_changing_it(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {"VTE_MODEL_A": "other-model"}, clear=True):
            p = self.profile(root)
            original = p.read_bytes()
            configure_fe(p, "gpt-5.6-sol")
            self.assertEqual(os.environ["VTE_BASE_URL"], "https://api.forceeasyai.com/v1")
            self.assertEqual(os.environ["VTE_MODEL"], "gpt-5.6-sol")
            self.assertEqual(os.environ["VTE_API_STYLE"], "responses")
            self.assertNotIn("VTE_MODEL_A", os.environ)
            self.assertEqual(p.read_bytes(), original)
            self.assertEqual(len(list(Path(root).iterdir())), 1)

    def test_rejects_unexpected_destinations_before_exporting_key(self):
        for base in ("https://example.invalid", "https://api.forceeasyai.com@evil.invalid", "http://api.forceeasyai.com", "https://api.forceeasyai.com/?key=secret"):
            with self.subTest(base=base), tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {}, clear=True):
                with self.assertRaises(ValueError):
                    configure_fe(self.profile(root, base))
                self.assertNotIn("VTE_API_KEY", os.environ)

    def test_rejects_missing_key_and_other_model(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                configure_fe(self.profile(root, key=""))
            with self.assertRaises(ValueError):
                configure_fe(self.profile(root), "unrequested-model")
            self.assertNotIn("VTE_API_KEY", os.environ)
