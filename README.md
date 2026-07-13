# StratumParity

Differential behavior test suite for [Stratum](https://github.com/StratumServer/Stratum),
the performance-oriented server fork of Vintage Story. Built on
[Atlas](https://github.com/Pixnop/Atlas), the in-process integration test harness.

Stratum promises performance gains without changing vanilla gameplay behavior. This suite
puts that promise under test: the same scenarios run against a vanilla install and against
a Stratum install, and the results must line up. Scenarios fall into two families:

- **Parity scenarios**: behavior that must be identical on both servers. Any divergence is
  a regression (in Stratum, or an incorrect assumption in the scenario).
- **Probe scenarios**: behavior that Stratum intentionally changes (entity tick throttling,
  simulation distance). Probes measure the delta, assert the vanilla baseline on vanilla,
  assert the documented Stratum behavior on Stratum, and verify that disabling the feature
  through `stratum-performance.json` restores parity.

## Requirements

- .NET 10 SDK
- A vanilla Vintage Story server install (1.22.x)
- A bootstrapped Stratum install (run `StratumServer` once so the vanilla assets and the
  Stratum overlay are in place)

## Running

One install at a time (the standard Atlas workflow):

```bash
VINTAGE_STORY=~/.local/share/vintagestory dotnet test -c Release
VINTAGE_STORY=~/dev/stratum-install dotnet test -c Release
```

Both installs plus a comparison report:

```bash
scripts/run-parity.sh ~/.local/share/vintagestory ~/dev/stratum-install
```

The script rebuilds per install on purpose: the test assembly copies `VintagestoryAPI.dll`
into its output, and that copy must match the install the run targets (mixing a fork's
`VintagestoryLib` with the vanilla API produces `MissingFieldException` at boot).

## Layout

- `scenarios/StratumParity.Scenarios/`: the xUnit scenario project (consumes the
  `Pixnop.Atlas.XUnit` NuGet package)
- `scripts/run-parity.sh`: differential runner (two builds, two runs, one diff)
- `scripts/diff_trx.py`: TRX comparison tool (outcome diffs, timing deltas)

## Versions

Pinned expectations: Vintage Story 1.22.3, Stratum v1.22.3-stratum.15, Atlas 0.9.0.
Stratum moves fast (releases every few days); when a scenario starts failing on a new
Stratum release, that is the suite doing its job.
