#!/usr/bin/env python3
"""
Render the GitHub job-summary markdown from `atlas diff --json-tests` output.

Usage: python3 render_summary.py diff.json >> "$GITHUB_STEP_SUMMARY"

Exits 1 when the two runs diverge (a test absent on either side, or present on
both with different outcomes), 0 when parity holds. The caller uses that exit
code as the parity gate: unlike `atlas diff`'s own exit code, which only flags
candidate regressions, this check is symmetric, matching what parity means
(a vanilla-only failure diverges just as much as a stratum-only one).
"""

import json
import sys

BADGE = {'passed': '✅', 'failed': '❌', 'skipped': '⏭️'}


def short_name(test):
    """ClassName.Method from a fully qualified test name."""
    parts = test.split('.')
    return '.'.join(parts[-2:]) if len(parts) >= 2 else test


def cell(side):
    if side is None:
        return '➖ absent'
    badge = BADGE.get(side['outcome'], '❓ ' + side['outcome'])
    ms = side.get('durationMs')
    return badge if ms is None else f"{badge} {ms / 1000:.1f}s"


def totals(tests, side_key):
    sides = [t[side_key] for t in tests if t.get(side_key)]
    passed = sum(1 for s in sides if s['outcome'] == 'passed')
    duration = sum(s.get('durationMs') or 0 for s in sides) / 1000
    return passed, len(sides), duration


def main():
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)

    with open(sys.argv[1], encoding='utf-8') as fh:
        doc = json.load(fh)
    tests = sorted(doc.get('tests') or [], key=lambda t: short_name(t['test']))

    divergences = 0
    print('## Parity report: vanilla vs stratum')
    print()
    print('| Scenario | Vanilla | Stratum | Δ duration |')
    print('|---|---|---|---|')
    for t in tests:
        baseline, candidate = t.get('baseline'), t.get('candidate')
        delta_cell = ''
        if (baseline and candidate
                and baseline.get('durationMs') is not None
                and candidate.get('durationMs') is not None):
            delta_cell = f"{(candidate['durationMs'] - baseline['durationMs']) / 1000:+.1f}s"
        if baseline is None or candidate is None or baseline['outcome'] != candidate['outcome']:
            divergences += 1
            delta_cell += ' ⚠️'
        print(f"| `{short_name(t['test'])}` | {cell(baseline)} | {cell(candidate)} | {delta_cell} |")

    vp, vt, vd = totals(tests, 'baseline')
    sp, st, sd = totals(tests, 'candidate')
    print()
    print(f"**Vanilla**: {vp}/{vt} passed in {vd:.0f}s. "
          f"**Stratum**: {sp}/{st} passed in {sd:.0f}s.")
    print()
    print('> Δ duration compares scenario wall time and is only a performance signal for '
          'scenarios whose flow is identical on both flavors. Probe scenarios are '
          'asymmetric by design: proving an absence on Stratum takes a fixed observation '
          'window, while proving a presence on vanilla ends at the first occurrence, so '
          'their Δ is expected and not a regression.')
    print()
    if divergences == 0:
        print('### ✅ Parity holds: no outcome divergence between flavors')
    else:
        print(f'### ❌ {divergences} outcome divergence(s) between flavors')
    sys.exit(1 if divergences else 0)


if __name__ == '__main__':
    main()
