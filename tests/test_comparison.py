import asyncio
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from vte_review.comparison import (baseline_case, digest, extract_initial, load, prepare,
                                   request_for, response_output, run_one, save, export_and_verify)


def record():
    doc = {'id': 'KB-1', 'text': 'synthetic evidence'}
    case = {'case_id': 'TEST', 'observations': [{'status': 'excluded', 'value': 'excluded'}, {'status': 'unverified', 'value': 2}],
            'longitudinal': {'previous_recommendation': {'recommendation': 'SECRET REVIEWED ADVICE'},
                             'prior_events': [{'text': 'prior actual treatment'}]}}
    output = {'shared_plan': 'synthetic draft', 'assumptions': [], 'information_requests': []}
    events = [{'event': 'call_started', 'task': 'assess', 'role': r, 'seq': i, 'input': {'evidence': [doc]}} for i, r in enumerate('ABC')]
    events += [{'event': 'call_completed', 'task': 'synthesize', 'seq': 3, 'requests': 1, 'model': 'fake', 'usage': {'total_tokens': 20}},
               {'event': 'draft_created', 'version': 1, 'seq': 4, 'elapsed_s': 1, 'draft': output},
               {'event': 'call_started', 'task': 'review', 'seq': 5, 'input': {'evidence': [{'id': 'LEAK'}]}}]
    return {'id': 'CASE01-T1', 'case_id': 'CASE01', 'position': 0, 'label': 'test', 'source_run': '/synthetic',
            'case': case, 'events': events, 'meta': {'output_language': 'zh'}, 'library': [doc]}


class FakeModel:
    model = 'fake'
    def __init__(self, bad=False):
        self.calls = 0
        self.bad = bad
    def _user(self, value):
        return {'role': 'user', 'content': value}
    async def _post(self, endpoint, body):
        self.calls += 1
        text = 'not JSON' if self.bad else json.dumps({'shared_plan': 'test KB-invented', 'assumptions': [], 'information_requests': []})
        return {'status': 'completed', 'model': 'fake', 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': text}]}]}


class ComparisonTests(unittest.TestCase):
    def test_strip_model_advice_keep_historical_facts_and_no_mutation(self):
        original = record()['case']; before = deepcopy(original)
        clean = baseline_case(original)
        self.assertNotIn('SECRET', json.dumps(clean))
        self.assertEqual(clean['longitudinal']['prior_events'], before['longitudinal']['prior_events'])
        self.assertEqual(len(clean['observations']), 1)
        self.assertEqual(original, before)

    def test_initial_is_exact_and_no_review_evidence(self):
        r = record(); initial, evidence, _ = extract_initial(r['events'])
        self.assertEqual(initial['output'], r['events'][4]['draft'])
        self.assertEqual([e['id'] for e in evidence], ['KB-1'])
        self.assertFalse(initial['review_complete'])
        r['events'][1]['task'] = 'review'
        with self.assertRaises(ValueError): extract_initial(r['events'])

    def test_frozen_source_change_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            r = record(); prepare(r, d); prepare(r, d)
            r['case']['question'] = 'changed'
            with self.assertRaises(ValueError): prepare(r, d)

    def test_baselines_only_differ_in_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            folder = prepare(record(), d); frozen = load(folder/'input.json'); model = FakeModel()
            a = request_for(frozen, 'baseline', model); b = request_for(frozen, 'rag', model)
            pa = json.loads(a['input'][0]['content'].split('Input data:\n')[1]); pb = json.loads(b['input'][0]['content'].split('Input data:\n')[1])
            self.assertEqual(pa['case'], pb['case']); self.assertEqual(pa['evidence'], [])
            self.assertTrue(pb['evidence']); a.pop('input'); b.pop('input'); self.assertEqual(a, b)
            with self.assertRaises(ValueError): request_for(frozen, 'reviewed', model)

    def test_resume_and_citation_error_retained_without_resampling(self):
        async def check():
            with tempfile.TemporaryDirectory() as d:
                folder = prepare(record(), d); model = FakeModel(); sem = asyncio.Semaphore(1)
                self.assertEqual(await run_one(folder, 'rag', model, sem), 'completed')
                self.assertEqual(await run_one(folder, 'rag', model, sem), 'reused')
                self.assertEqual(model.calls, 1)
                self.assertEqual(load(folder/'rag/result.json')['unknown_citation_ids'], ['KB-invented'])
        asyncio.run(check())

    def test_invalid_received_output_is_terminal_across_resume(self):
        async def check():
            with tempfile.TemporaryDirectory() as d:
                folder = prepare(record(), d); model = FakeModel(bad=True); sem = asyncio.Semaphore(1)
                self.assertEqual(await run_one(folder, 'baseline', model, sem), 'failed')
                self.assertEqual(await run_one(folder, 'baseline', model, sem), 'failed')
                self.assertEqual(model.calls, 1)
                self.assertTrue((folder/'baseline/response-1.json').exists())
        asyncio.run(check())

    def test_received_response_recovered_without_new_call(self):
        async def check():
            with tempfile.TemporaryDirectory() as d:
                folder = prepare(record(), d); model = FakeModel(); raw = await model._post('', {})
                save(folder/'baseline/response-1.json', raw)
                self.assertEqual(await run_one(folder, 'baseline', model, asyncio.Semaphore(1)), 'completed')
                self.assertEqual(model.calls, 1)
        asyncio.run(check())

    def test_export_checks_raw_answer_and_escapes_html(self):
        async def check():
            with tempfile.TemporaryDirectory() as d:
                out = Path(d)/'out'; source = Path(d)/'source'; r = record(); source.mkdir()
                r['source_run'] = str(source)
                r['events'][4]['draft']['shared_plan'] = '<script>untrusted</script>'
                save(source/'case.json', r['case']); save(source/'evidence.json', r['library'])
                (source/'events.jsonl').write_text('\n'.join(json.dumps(e) for e in r['events']), encoding='utf-8')
                folder = prepare(r, out); model = FakeModel()
                for method in ('baseline', 'rag'):
                    await run_one(folder, method, model, asyncio.Semaphore(1))
                result = export_and_verify(out)
                self.assertEqual(result['verified_outputs'], 3)
                page = (out/'clinical_results.html').read_text(encoding='utf-8')
                self.assertIn('&lt;script&gt;untrusted', page)
                self.assertNotIn('<script>untrusted', page)
                output = load(folder/'rag/result.json'); output['output']['shared_plan'] = 'changed'
                save(folder/'rag/result.json', output)
                with self.assertRaises(AssertionError): export_and_verify(out)
        asyncio.run(check())

    def test_finite_batch_distinguishes_completion_failure_and_timeout(self):
        from scripts import run_comparison_dataset as runner
        for ready, completed, expected, code in [(1, 1, 'complete', 0), (1, 0, 'failed_outputs', 2), (0, 0, 'source_wait_timeout', 2)]:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as d:
                state = {'prepared_nodes': ready, 'methods': {m: {'completed': completed} for m in ('baseline', 'rag', 'synthesis')}}
                with patch('sys.argv', ['runner', '--out', d, '--run', '--follow-target', '1']), \
                     patch.object(runner, 'discover', return_value=[]), \
                     patch.object(runner, 'run', new=AsyncMock()), \
                     patch.object(runner, 'summary', return_value=state), \
                     patch.object(runner, 'export_and_verify', return_value={'verified': True}), \
                     patch.object(runner, 'time') as clock, \
                     patch('builtins.print'):
                    clock.monotonic.side_effect = [0, 100000]
                    self.assertEqual(runner.main(), code)
                self.assertEqual(load(Path(d)/'final-status.json')['status'], expected)


if __name__ == '__main__':
    unittest.main()
