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
import re
import sys
from pathlib import Path

from diff_trx import parse_trx

# Perf pack scenarios emit `ATLAS_METRIC <key>=<number>` lines to their test stdout.
METRIC_RE = re.compile(r'ATLAS_METRIC\s+(\w+)=([-\d.]+)')


def metrics_of(result):
    """Numeric ATLAS_METRIC values parsed from a test result's stdout, or {} if none."""
    out = {}
    for key, value in METRIC_RE.findall(result.get('stdout', '') or ''):
        try:
            out[key] = float(value)
        except ValueError:
            pass
    return out


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

    # The history file is always somewhere under the caller's working tree (the
    # gh-pages checkout in CI); refuse anything that resolves outside it so a bad
    # argument cannot write elsewhere on the filesystem.
    history_path = Path(args.history).resolve()
    workdir = Path.cwd().resolve()
    if not history_path.is_relative_to(workdir):
        sys.exit(f'refusing to touch a history file outside {workdir}: {history_path}')

    if history_path.exists():
        history = json.loads(history_path.read_text())
    else:
        history = {'schema': 2, 'runs': []}
    # Schema 2 adds the optional per-scenario 'metrics' key; older runs simply lack it.
    history['schema'] = max(history.get('schema', 1), 2)

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

        # Optional per-scenario perf metrics (only the tick-cost pack emits them). Stored
        # under an optional 'metrics' key so pre-schema-2 runs simply lack it.
        v_metrics = metrics_of(vanilla[name]) if name in vanilla else {}
        s_metrics = metrics_of(stratum[name]) if name in stratum else {}
        if v_metrics or s_metrics:
            metrics = {}
            if v_metrics:
                metrics['v'] = {k: round(x, 3) for k, x in v_metrics.items()}
            if s_metrics:
                metrics['s'] = {k: round(x, 3) for k, x in s_metrics.items()}
            vt = v_metrics.get('ms_per_tick')
            st = s_metrics.get('ms_per_tick')
            if vt and st and vt > 0:
                metrics['ratio'] = round(st / vt, 3)
            entry['metrics'] = metrics
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
    # NOSONAR below: the path is resolved and confined to the working tree at the top
    # of main(); Sonar's taint analysis does not recognize that sanitizer.
    history_path.write_text(json.dumps(history, indent=1) + '\n')  # NOSONAR
    print(f"recorded run {args.run_id} ({len(history['runs'])} run(s) in history)")


if __name__ == '__main__':
    main()
