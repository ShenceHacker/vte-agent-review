"""Prepare, run, resume and audit the three manuscript control configurations."""
from pathlib import Path
import argparse
import asyncio
import json
import os
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.serve_fe import configure_fe
from vte_review.comparison import VERSION, PROMPT, discover, prepare, run_one, digest, export_and_verify
from vte_review.longitudinal import load, save
from vte_review.providers import ChatCompletionsModel
from vte_review.experiment_html import write_experiment_html


def summary(out):
    nodes = sorted((out/'nodes').glob('*/input.json'))
    result = {'protocol': VERSION, 'prepared_nodes': len(nodes), 'patients': len({p.parent.name.split('-T')[0] for p in nodes}),
              'methods': {}, 'path': str(out.resolve())}
    for method in ('baseline', 'rag', 'synthesis'):
        outputs = [load(p.parent/method/'result.json') for p in nodes if (p.parent/method/'result.json').exists()]
        result['methods'][method] = {'completed': len(outputs), 'pending': len(nodes)-len(outputs),
                                    'unknown_citations': sum(bool(o.get('unknown_citation_ids')) for o in outputs)}
    save(out/'progress.json', result)
    write_experiment_html(out)
    return result


async def run(args, folders):
    configure_fe(Path.home()/'.claude/settings.json', 'gpt-5.6-sol')
    if args.ssh_tunnel:
        os.environ['VTE_BASE_URL'] = 'http://127.0.0.1:18881/v1'
    model = ChatCompletionsModel(os.environ['VTE_BASE_URL'], os.environ['VTE_API_KEY'], 'gpt-5.6-sol',
                                timeout=240, max_tokens=6000, api_style='responses', reasoning_effort='low')
    semaphore = asyncio.Semaphore(args.concurrency)
    try:
        pending = [asyncio.create_task(run_one(folder, method, model, semaphore, args.max_attempts))
                   for folder in folders for method in ('baseline', 'rag')]
        for task in asyncio.as_completed(pending):
            await task
            summary(args.out)
    finally:
        await model.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset', type=Path, default=ROOT/'data/vte_dataset')
    p.add_argument('--out', type=Path, default=ROOT/'data/vte_dataset/comparison-20261015-concise')
    p.add_argument('--run', action='store_true')
    p.add_argument('--ssh-tunnel', action='store_true', help='Use separately established local SSH tunnel on 18881')
    p.add_argument('--concurrency', type=int, default=4)
    p.add_argument('--max-attempts', type=int, default=3)
    p.add_argument('--limit', type=int)
    p.add_argument('--verify', action='store_true', help='Verify saved results and export local HTML/CSV')
    p.add_argument('--follow-target', type=int, help='Finite batch: wait for this many authoritative nodes')
    p.add_argument('--wait-minutes', type=int, default=180)
    args = p.parse_args()
    if not 1 <= args.concurrency <= 8 or not 1 <= args.max_attempts <= 6:
        p.error('concurrency must be 1..8; attempts must be 1..6')
    if args.follow_target and (not args.run or args.limit or args.follow_target < 1 or not 1 <= args.wait_minutes <= 360):
        p.error('follow-target requires --run, no --limit and a 1..360 minute bound')
    records = discover(args.dataset)
    if args.limit:
        records = records[:args.limit]
    folders = [prepare(record, args.out) for record in records]
    protocol = {'version': VERSION, 'model': 'gpt-5.6-sol', 'prompt': PROMPT, 'prompt_hash': digest(PROMPT),
                'reasoning_effort': 'low', 'max_output_tokens': 6000, 'timeout_s': 240,
                'temperature': 'not explicitly set', 'base_and_rag_case': 'identical, no previous model advice',
                'language': 'matches original generation: first cohort en, later cohorts zh',
                'synthesis': 'verbatim paired initial draft, not independent static longitudinal rollout',
                'reviewed': 'never invoked by this runner', 'extraction': 'reuse original, including known errors',
                'rag': 'union of initial role retrieval from same frozen library; no post-review retrieval or tools',
                'images': 'baseline/rag see extracted observations and source text; original workflow may inspect images via tools'}
    existing = load(args.out/'protocol.json')
    if existing is not None and existing != protocol:
        raise ValueError('Protocol changed; choose a new output directory')
    save(args.out/'protocol.json', protocol)
    print(json.dumps(summary(args.out)), flush=True)
    if args.run:
        asyncio.run(run(args, folders))
        print('COMPARISON_BATCH_FINISHED', json.dumps(summary(args.out)), flush=True)
    if args.verify:
        print(json.dumps(export_and_verify(args.out)), flush=True)
        write_experiment_html(args.out)
    if args.follow_target:
        deadline = time.monotonic() + args.wait_minutes*60
        while True:
            state = summary(args.out)
            ready = state['prepared_nodes'] >= args.follow_target
            complete = all(state['methods'][m]['completed'] >= args.follow_target for m in ('baseline', 'rag', 'synthesis'))
            if complete or ready or time.monotonic() >= deadline:
                final = {'status': 'complete' if complete else 'failed_outputs' if ready else 'source_wait_timeout',
                         'target_nodes': args.follow_target, 'progress': state,
                         'verification': export_and_verify(args.out)}
                save(args.out/'final-status.json', final)
                write_experiment_html(args.out)
                print('COMPARISON_FINAL', json.dumps(final), flush=True)
                return 0 if complete else 2
            time.sleep(30)
            records = discover(args.dataset)
            folders = [prepare(record, args.out) for record in records]
            # A failed request is bounded by its persisted attempts, so this loop
            # cannot repeatedly resample terminal or exhausted results.
            asyncio.run(run(args, folders))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
