#!/usr/bin/env python3
"""
Render the GitHub job-summary markdown from `atlas diff --json-tests` output.

Usage: python3 render_summary.py diff.json >> "$GITHUB_STEP_SUMMARY"

Exits 1 when the two runs diverge (a test absent on either side, or present on
both with different outcomes), 0 when parity holds. The caller uses that exit
code as the parity gate: unlike `atlas diff`'s own exit code, which only flags
candidate regressions, this check is symmetric, matching what parity means
(a vanilla-only failure diverges just as much as a stratum-only one).

An unusable diff document (absent, empty, malformed) also exits 1, naming the
file and the reason: no report is never a passing verdict.
"""

import json
import sys
from pathlib import Path

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


def load_diff(path):
    """The `atlas diff --json-tests` document, or a one-line failure when there is none.

    The caller redirects `atlas diff` into the file and ignores its exit code (a candidate
    regression is not this step's verdict), so an absent, empty or truncated document means
    atlas never produced usable output. Say which file and why, and exit 1, instead of
    dying on a traceback that buries the cause.
    """
    try:
        # NOSONAR below: the path is resolved and confined to the working tree by the
        # caller; Sonar's taint analysis does not recognize that sanitizer.
        with open(path, encoding='utf-8') as fh:  # NOSONAR
            doc = json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
        print(f'### ❌ No parity report: `{path.name}` is missing, empty or not valid JSON')
        sys.exit(f'cannot read the diff document {path}: {e}')
    if not isinstance(doc, dict):
        print(f'### ❌ No parity report: `{path.name}` is not an atlas diff document')
        sys.exit(f'the diff document {path} is a {type(doc).__name__}, expected a JSON object')
    return doc


def main():
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)

    # The diff file always lives in the caller's working tree (the CI job writes
    # ./diff.json); refuse anything that resolves outside it so a bad argument
    # cannot read elsewhere on the filesystem.
    diff_path = Path(sys.argv[1]).resolve()
    workdir = Path.cwd().resolve()
    if not diff_path.is_relative_to(workdir):
        sys.exit(f'refusing to read a diff file outside {workdir}: {diff_path}')

    doc = load_diff(diff_path)
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
