#!/usr/bin/env python3
"""
Compare two VSTest TRX files and report differences.

Usage: python3 diff_trx.py vanilla.trx stratum.trx
"""

import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


# TRX namespace
NS = {'trx': 'http://microsoft.com/schemas/VisualStudio/TeamTest/2010'}


def parse_trx(filepath):
    """
    Parse a TRX file and extract test results.

    Returns a dict: {testName: {'outcome': str, 'duration': float, 'error': str}}
    """
    results = {}

    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except FileNotFoundError:
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)
    except ET.ParseError as e:
        print(f"Error parsing {filepath}: {e}", file=sys.stderr)
        sys.exit(1)

    # Find all UnitTestResult elements
    for result_elem in root.findall('.//trx:UnitTestResult', NS):
        test_name = result_elem.get('testName', 'Unknown')
        outcome = result_elem.get('outcome', 'Unknown')

        # Parse duration (format: HH:MM:SS.mmm)
        duration_str = result_elem.get('duration', '0')
        try:
            parts = duration_str.split(':')
            if len(parts) == 3:
                hours, minutes, seconds = parts
                duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
            else:
                duration = 0.0
        except (ValueError, IndexError):
            duration = 0.0

        # Extract error message for failed tests
        error_msg = ''
        output_elem = result_elem.find('trx:Output', NS)
        if output_elem is not None:
            error_info = output_elem.find('trx:ErrorInfo', NS)
            if error_info is not None:
                message_elem = error_info.find('trx:Message', NS)
                if message_elem is not None and message_elem.text:
                    error_msg = message_elem.text[:300]

        results[test_name] = {
            'outcome': outcome,
            'duration': duration,
            'error': error_msg
        }

    return results


def print_summary(filepath, results):
    """Print a summary table for a TRX file."""
    outcome_counts = defaultdict(int)
    total_duration = 0.0

    for test_data in results.values():
        outcome = test_data['outcome']
        outcome_counts[outcome] += 1
        total_duration += test_data['duration']

    print(f"\n{filepath}:")
    print(f"  Total tests: {len(results)}")
    for outcome in sorted(outcome_counts.keys()):
        print(f"    {outcome}: {outcome_counts[outcome]}")
    print(f"  Total duration: {total_duration:.2f}s")


def print_diff(vanilla_results, stratum_results, vanilla_file, stratum_file):
    """Print tests with outcome differences and timing changes."""
    print("\nDIFF SECTION:")
    print("=" * 80)

    has_diff = False

    # Check for outcome differences
    for test_name in sorted(set(vanilla_results.keys()) | set(stratum_results.keys())):
        vanilla_data = vanilla_results.get(test_name)
        stratum_data = stratum_results.get(test_name)

        if vanilla_data is None:
            print(f"\n[PRESENT ONLY IN {stratum_file}]")
            print(f"  Test: {test_name}")
            print(f"    Outcome: {stratum_data['outcome']}")
            if stratum_data['error']:
                print(f"    Error: {stratum_data['error']}")
            has_diff = True
        elif stratum_data is None:
            print(f"\n[PRESENT ONLY IN {vanilla_file}]")
            print(f"  Test: {test_name}")
            print(f"    Outcome: {vanilla_data['outcome']}")
            if vanilla_data['error']:
                print(f"    Error: {vanilla_data['error']}")
            has_diff = True
        elif vanilla_data['outcome'] != stratum_data['outcome']:
            print(f"\n[OUTCOME CHANGED] {test_name}")
            print(f"  {vanilla_file}: {vanilla_data['outcome']}")
            print(f"  {stratum_file}: {stratum_data['outcome']}")

            # Print error from the failing side
            if stratum_data['outcome'] in ('Failed', 'Error'):
                if stratum_data['error']:
                    print(f"  Error: {stratum_data['error']}")
            elif vanilla_data['outcome'] in ('Failed', 'Error'):
                if vanilla_data['error']:
                    print(f"  Error: {vanilla_data['error']}")

            has_diff = True

    if not has_diff:
        print("No outcome differences found.")


def print_timing_diff(vanilla_results, stratum_results):
    """Print the 10 tests with largest absolute duration delta."""
    print("\n\nTIMING SECTION:")
    print("=" * 80)

    timing_diffs = []

    for test_name in sorted(set(vanilla_results.keys()) & set(stratum_results.keys())):
        vanilla_duration = vanilla_results[test_name]['duration']
        stratum_duration = stratum_results[test_name]['duration']
        delta = abs(vanilla_duration - stratum_duration)

        if delta > 0:
            timing_diffs.append((test_name, vanilla_duration, stratum_duration, delta))

    # Sort by delta (descending)
    timing_diffs.sort(key=lambda x: x[3], reverse=True)

    if not timing_diffs:
        print("No timing differences found.")
        return

    print(f"\nTop 10 tests with largest duration delta:")
    print(f"{'Test Name':<60} {'Vanilla (s)':<12} {'Stratum (s)':<12} {'Delta (s)':<12}")
    print("-" * 96)

    for test_name, vanilla_dur, stratum_dur, delta in timing_diffs[:10]:
        # Truncate test name if too long
        display_name = test_name if len(test_name) <= 60 else test_name[:57] + "..."
        print(f"{display_name:<60} {vanilla_dur:<12.3f} {stratum_dur:<12.3f} {delta:<12.3f}")


def outcome_badge(outcome):
    """Emoji badge for a TRX outcome."""
    return {'Passed': '✅', 'Failed': '❌', 'NotExecuted': '⏭️'}.get(outcome, f'❓ {outcome}')


def short_name(test_name):
    """ClassName.Method from a fully qualified test name."""
    parts = test_name.split('.')
    return '.'.join(parts[-2:]) if len(parts) >= 2 else test_name


def print_markdown(vanilla_results, stratum_results):
    """
    GitHub-flavored markdown report, meant for $GITHUB_STEP_SUMMARY: one row per
    scenario with both outcomes and durations, then totals and the parity verdict.
    """
    all_tests = sorted(set(vanilla_results.keys()) | set(stratum_results.keys()),
                       key=short_name)

    divergences = 0
    print('## Parity report: vanilla vs stratum')
    print()
    print('| Scenario | Vanilla | Stratum | Δ duration |')
    print('|---|---|---|---|')
    for name in all_tests:
        v = vanilla_results.get(name)
        s = stratum_results.get(name)
        v_cell = f"{outcome_badge(v['outcome'])} {v['duration']:.1f}s" if v else '➖ absent'
        s_cell = f"{outcome_badge(s['outcome'])} {s['duration']:.1f}s" if s else '➖ absent'
        if v and s:
            delta = s['duration'] - v['duration']
            delta_cell = f"{delta:+.1f}s"
        else:
            delta_cell = ''
        if v is None or s is None or v['outcome'] != s['outcome']:
            divergences += 1
            delta_cell += ' ⚠️'
        print(f"| `{short_name(name)}` | {v_cell} | {s_cell} | {delta_cell} |")

    def totals(results):
        passed = sum(1 for r in results.values() if r['outcome'] == 'Passed')
        duration = sum(r['duration'] for r in results.values())
        return passed, len(results), duration

    vp, vt, vd = totals(vanilla_results)
    sp, st, sd = totals(stratum_results)
    print()
    print(f"**Vanilla**: {vp}/{vt} passed in {vd:.0f}s. "
          f"**Stratum**: {sp}/{st} passed in {sd:.0f}s.")
    print()
    if divergences == 0:
        print('### ✅ Parity holds: no outcome divergence between flavors')
    else:
        print(f'### ❌ {divergences} outcome divergence(s) between flavors')


def main():
    if len(sys.argv) == 2 and sys.argv[1] in ('--help', '-h'):
        print(__doc__)
        sys.exit(0)

    args = [a for a in sys.argv[1:] if a != '--markdown']
    markdown = '--markdown' in sys.argv[1:]

    if len(args) != 2:
        print(__doc__)
        sys.exit(1)

    vanilla_file = args[0]
    stratum_file = args[1]

    # Parse both files
    vanilla_results = parse_trx(vanilla_file)
    stratum_results = parse_trx(stratum_file)

    if markdown:
        print_markdown(vanilla_results, stratum_results)
    else:
        # Print summaries
        print_summary(vanilla_file, vanilla_results)
        print_summary(stratum_file, stratum_results)

        # Print diff section
        print_diff(vanilla_results, stratum_results, vanilla_file, stratum_file)

        # Print timing section
        print_timing_diff(vanilla_results, stratum_results)

    # Determine exit code: 0 if no outcome differences, 1 otherwise
    has_outcome_diff = False
    for test_name in set(vanilla_results.keys()) | set(stratum_results.keys()):
        vanilla_data = vanilla_results.get(test_name)
        stratum_data = stratum_results.get(test_name)

        if vanilla_data is None or stratum_data is None:
            has_outcome_diff = True
            break

        if vanilla_data['outcome'] != stratum_data['outcome']:
            has_outcome_diff = True
            break

    sys.exit(1 if has_outcome_diff else 0)


if __name__ == '__main__':
    main()
