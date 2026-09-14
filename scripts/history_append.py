#!/usr/bin/env python3
"""
Append one parity run (a vanilla + stratum TRX pair) to the dashboard history.

Usage:
  python3 history_append.py vanilla.trx stratum.trx \
      --history gh-pages/data/runs.json \
      --run-id 123 --sha abcdef --date 2026-07-14T10:00:00Z \
      --stratum-tag v1.22.3-stratum.15 [--event push] \
      [--atlas-version 0.13.1] [--vs-version 1.22.7]

Re-appending a run id REPLACES the previous entry for that id: GitHub re-run attempts
share the run id, and the re-run's results (say, green after a flaky red) must win.
With --missing-ok, a missing TRX file counts as an empty suite for that flavor, so a
run whose server never booted is still recorded (as a divergence) instead of vanishing.
"""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

# Perf pack scenarios emit `ATLAS_METRIC <key>=<number>` lines to their test stdout.
METRIC_RE = re.compile(r'ATLAS_METRIC\s+(\w+)=([-\d.]+)')

# A failure message can run to a full stack dump. The history keeps enough of it to tell
# two red runs apart at a glance; the whole thing stays in the run's TRX artifact.
ERROR_MAX = 400

# NOSONAR below: this is the XML namespace identifier mandated by the TRX schema,
# a fixed string compared against the document, never a URL that gets fetched.
TRX_NS = {'trx': 'http://microsoft.com/schemas/VisualStudio/TeamTest/2010'}  # NOSONAR


def short_error(message):
    """A TRX failure message flattened onto one capped line.

    Lines are joined in order, so the first one leads and the cap cuts the tail: an
    xunit assertion header, or the sentence an Atlas setup exception opens with, is
    what survives, not a truncated stack frame.
    """
    line = ' '.join(part.strip() for part in message.splitlines() if part.strip())
    return line if len(line) <= ERROR_MAX else line[:ERROR_MAX - 1] + '…'


def parse_trx(filepath):
    """testName -> {'outcome', 'duration' (s), 'stdout', 'error'} from a TRX report.

    The history needs stdout from BOTH flavors (the perf metrics ride in it), which
    is why this stays a TRX parse instead of consuming `atlas diff --json-tests`:
    that document only carries the candidate side's stdout.

    'error' is the failure message, read from the same Output/ErrorInfo/Message path
    Atlas.Cli's TrxResultsReader uses, and empty for a test that carries none.
    """
    try:
        root = ET.parse(filepath).getroot()
    except (OSError, ET.ParseError) as e:
        sys.exit(f'cannot read TRX {filepath}: {e}')

    results = {}
    for result in root.findall('.//trx:UnitTestResult', TRX_NS):
        parts = (result.get('duration') or '0').split(':')
        try:
            duration = (int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
                        if len(parts) == 3 else 0.0)
        except ValueError:
            duration = 0.0
        stdout = ''
        error = ''
        output = result.find('trx:Output', TRX_NS)
        if output is not None:
            stdout_elem = output.find('trx:StdOut', TRX_NS)
            if stdout_elem is not None and stdout_elem.text:
                stdout = stdout_elem.text
            message = output.find('trx:ErrorInfo/trx:Message', TRX_NS)
            if message is not None and message.text:
                error = short_error(message.text)
        results[result.get('testName', 'Unknown')] = {
            'outcome': result.get('outcome', 'Unknown'),
            'duration': duration,
            'stdout': stdout,
            'error': error,
        }
    return results


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
    parser.add_argument('--atlas-version', default='',
                        help='version of the Atlas CLI that ran the suite')
    parser.add_argument('--vs-version', default='',
                        help='Vintage Story version both flavors were built on')
    parser.add_argument('--missing-ok', action='store_true',
                        help='treat a missing TRX file as an empty suite for that flavor')
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
        history = {'schema': 3, 'runs': []}
    # Schema 2 added the optional per-scenario 'metrics' key, schema 3 the optional
    # per-scenario 'error' and the run's optional provenance fields. Every one of them is
    # optional on read: older runs simply lack them and are never rewritten to add them.
    history['schema'] = max(history.get('schema', 1), 3)

    # A re-run attempt shares the run id; its results replace the earlier attempt's.
    before = len(history['runs'])
    history['runs'] = [run for run in history['runs'] if run['run_id'] != args.run_id]
    if len(history['runs']) < before:
        print(f'run {args.run_id} already recorded, replacing its entry')

    def parse_side(path):
        if args.missing_ok and not Path(path).exists():
            return {}
        return parse_trx(path)

    vanilla = parse_side(args.vanilla_trx)
    stratum = parse_side(args.stratum_trx)

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

        # Why this scenario went red, per flavor, under an optional 'error' key: only a
        # side that did not pass carries one, so a green run adds nothing to the file.
        errors = {side: results[name]['error']
                  for side, results in (('v', vanilla), ('s', stratum))
                  if name in results and results[name]['outcome'] != 'Passed'
                  and results[name]['error']}
        if errors:
            entry['error'] = errors
        scenarios[short] = entry

    parity = all(
        'v' in e and 's' in e and e['v'][0] == e['s'][0]
        for e in scenarios.values()
    )

    run = {
        'run_id': args.run_id,
        'sha': args.sha[:12],
        'date': args.date,
        'stratum_tag': args.stratum_tag,
        'event': args.event,
    }
    # Provenance of what was tested, all optional: the workflows pass what they know and
    # nothing is invented here, so an entry recorded before these existed simply lacks them.
    for key, value in (('atlas_version', args.atlas_version),
                       ('vs_version', args.vs_version)):
        if value:
            run[key] = value
    run.update({
        'scenarios': scenarios,
        'totals': {'vanilla': totals(vanilla), 'stratum': totals(stratum)},
        'parity': parity,
    })
    history['runs'].append(run)
    # Parse, don't string-compare: recorded dates mix UTC and +02:00 offsets, and a raw
    # string sort is not chronological across offsets.
    history['runs'].sort(key=lambda recorded: datetime.fromisoformat(recorded['date']))

    history_path.parent.mkdir(parents=True, exist_ok=True)
    # NOSONAR below: the path is resolved and confined to the working tree at the top
    # of main(); Sonar's taint analysis does not recognize that sanitizer.
    history_path.write_text(json.dumps(history, indent=1) + '\n')  # NOSONAR
    print(f"recorded run {args.run_id} ({len(history['runs'])} run(s) in history)")


if __name__ == '__main__':
    main()
