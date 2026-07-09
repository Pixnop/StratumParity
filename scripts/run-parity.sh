#!/usr/bin/env bash
set -euo pipefail

# Differential runner: builds and runs the scenario suite against two installs,
# then compares the TRX outputs.
#
# Usage: scripts/run-parity.sh <vanilla-install> <stratum-install>
#
# A full rebuild per install is deliberate. The test assembly copies
# VintagestoryAPI.dll into its output directory (test method bodies reference API
# types, so the copy is required); that copy must come from the install the run
# targets, otherwise the fork's VintagestoryLib and the vanilla API mix and the
# server fails at boot with MissingFieldException.

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <vanilla-install> <stratum-install>" >&2
  exit 2
fi

vanilla="$(cd -- "$1" && pwd)"
stratum="$(cd -- "$2" && pwd)"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/.." && pwd)"
results="$repo_root/results"
mkdir -p "$results"

run_suite() {
  local label="$1" install="$2"
  echo "== $label ($install) =="
  ( cd "$repo_root" \
    && VINTAGE_STORY="$install" dotnet test scenarios/StratumParity.Scenarios -c Release \
         --logger "trx;LogFileName=$label.trx" --results-directory "$results" )
}

run_suite vanilla "$vanilla"
run_suite stratum "$stratum"

echo
echo "== Comparison =="
python3 "$script_dir/diff_trx.py" "$results/vanilla.trx" "$results/stratum.trx"
