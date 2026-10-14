import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from contextlib import closing
from unittest.mock import patch

from scripts import prepare_rating_dataset as prep
from vte_review.dataset import processing_directory, write_json
from vte_review.intake import SourceStore


class DatasetBatchTests(unittest.TestCase):
    def test_batch_routing_preserves_legacy_and_new_cohorts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            self.assertEqual(processing_directory(root, {'case_id': 'CASE01'}), root / 'private/history/evaluation-20261009')
            self.assertEqual(processing_directory(root, {'case_id': 'CASE30'}), root / 'processing/sol-20261012')
            self.assertEqual(processing_directory(root, {'case_id': 'CASE31', 'processing_dir': 'processing/sol-20261014'}), root / 'processing/sol-20261014')

    def test_rejects_batch_paths_outside_dataset(self):
        for value in ['../other', '/tmp/other', 'C:/other', 'processing/../../other', '..\\other']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                processing_directory(Path('.'), {'case_id': 'CASE31', 'processing_dir': value})

    def test_preparation_keeps_completed_cases_and_holds_out_current_orders(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); data = root / 'data'; out = data / 'processing/new'
            (root / 'runs').mkdir()
            with closing(sqlite3.connect(root / 'runs/knowledge.sqlite3')) as db:
                db.execute('CREATE TABLE synthetic(value TEXT)')
            store = SourceStore(data / 'private/parsed')
            blocks = [{'text': '日期：入院', 'images': [], 'location': '1'},
                      {'text': '初始事实。开药：测试药物甲', 'images': [], 'location': '2'},
                      {'text': '日期：出院', 'images': [], 'location': '3'},
                      {'text': '新的事实。开药：测试药物乙', 'images': [], 'location': '4'}]
            src = store._save('synthetic.txt', json.dumps(blocks).encode(), 'text/plain', blocks=blocks)
            old = {'case_id': 'CASE30', 'processing_status': 'completed', 'result': 'frozen'}
            write_json(data / 'manifest.json', {'cases': [old, {'case_id': 'CASE31', 'processing_status': 'new', 'source_id': src['id']}]})
            write_json(data / 'private/curation.json', {'cases': {'CASE31': {'prescription_image_indices': []}}})
            with patch.object(prep, 'DATA', data), patch.object(prep, 'ROOT', root):
                prep.prepare(out, {'CASE31'})
                manifest = json.loads((data / 'manifest.json').read_text(encoding='utf-8'))
                self.assertEqual(manifest['cases'][0], old)
                self.assertEqual(manifest['cases'][1]['processing_dir'], 'processing/new')
                inputs = json.loads((out / 'CASE31-input.json').read_text(encoding='utf-8'))
                self.assertNotIn('测试药物甲', inputs[1]['text'])
                self.assertIn('测试药物甲', inputs[3]['text'])
                self.assertNotIn('测试药物乙', inputs[3]['text'])
                (out / 'batch.json').write_text('{}')
                with self.assertRaises(ValueError):
                    prep.prepare(out, {'CASE31'})
                with self.assertRaises(ValueError):
                    prep.prepare(out, {'CASE30'})


if __name__ == '__main__':
    unittest.main()
