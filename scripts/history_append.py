#!/usr/bin/env python3
"""
Append one parity run (a vanilla + stratum TRX pair) to the dashboard history.

Usage:
  python3 history_append.py vanilla.trx stratum.trx \
      --history gh-pages/data/runs.json \
      --run-id 123 --sha abcdef --date 2026-07-14T10:00:00Z \
      --stratum-tag v1.22.3-stratum.15 [--event push]

Idempotent per run id: appending an already-recorded run id is a no-op.
"""

import argparse
import json
import sys
from pathlib import Path

from diff_trx import parse_trx


def totals(results):
    return {
        'passed': sum(1 for r in results.values() if r['outcome'] == 'Passed'),
        'total': len(results),
        'duration': round(sum(r['duration'] for r in results.values()), 2),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('vanilla_trx')
    parser.add_argument('stratum_trx')
    parser.add_argument('--history', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--sha', required=True)
    parser.add_argument('--date', required=True)
    parser.add_argument('--stratum-tag', default='')
    parser.add_argument('--event', default='')
    args = parser.parse_args()

    history_path = Path(args.history)
    if history_path.exists():
        history = json.loads(history_path.read_text())
    else:
        history = {'schema': 1, 'runs': []}

    if any(run['run_id'] == args.run_id for run in history['runs']):
        print(f'run {args.run_id} already recorded, nothing to do')
        return

    vanilla = parse_trx(args.vanilla_trx)
    stratum = parse_trx(args.stratum_trx)

    scenarios = {}
    for name in sorted(set(vanilla) | set(stratum)):
        short = '.'.join(name.split('.')[-2:])
        entry = {}
        if name in vanilla:
            entry['v'] = [vanilla[name]['outcome'], round(vanilla[name]['duration'], 2)]
        if name in stratum:
            entry['s'] = [stratum[name]['outcome'], round(stratum[name]['duration'], 2)]
        scenarios[short] = entry

    parity = all(
        'v' in e and 's' in e and e['v'][0] == e['s'][0]
        for e in scenarios.values()
    )

    history['runs'].append({
        'run_id': args.run_id,
        'sha': args.sha[:12],
        'date': args.date,
        'stratum_tag': args.stratum_tag,
        'event': args.event,
        'scenarios': scenarios,
        'totals': {'vanilla': totals(vanilla), 'stratum': totals(stratum)},
        'parity': parity,
    })
    history['runs'].sort(key=lambda run: run['date'])

    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(json.dumps(history, indent=1) + '\n')
    print(f"recorded run {args.run_id} ({len(history['runs'])} run(s) in history)")


if __name__ == '__main__':
    main()
