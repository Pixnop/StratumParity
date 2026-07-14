# StratumParity

Differential behavior test suite for [Stratum](https://github.com/StratumServer/Stratum),
the performance-oriented server fork of Vintage Story. Built on
[Atlas](https://github.com/Pixnop/Atlas), the in-process integration test harness.

**Dashboard**: [leonfvt.fr/StratumParity](http://leonfvt.fr/StratumParity/) — run history,
per-flavor and per-scenario duration trends, and the latest parity verdict, republished by
CI on every main-branch run.

Stratum promises performance gains without changing vanilla gameplay behavior. This suite
puts that promise under test: the same scenarios run against a vanilla install and against
a Stratum install, and the results must line up. Scenarios fall into two families:

- **Parity scenarios**: behavior that must be identical on both servers. Any divergence is
  a regression (in Stratum, or an incorrect assumption in the scenario).
- **Probe scenarios**: behavior that Stratum intentionally changes (entity tick throttling,
  simulation distance). Probes measure the delta, assert the vanilla baseline on vanilla,
  assert the documented Stratum behavior on Stratum, and verify that disabling the feature
  through `stratum-performance.json` restores parity.

## Coverage

16 scenarios, green on both flavors, re-run by CI on every PR and weekly against the
pinned Stratum release.

| Surface | Scenarios | What is pinned down |
|---|---|---|
| Boot, block placement, join | `SmokeParityScenarios` | Fundamentals identical on both flavors; a joined player survives Stratum's packet limiter |
| Entity tick throttling | `EntityTickingProbes`, `EntityTickingDisabledScenarios` | Far entities tick 1 in 10 on Stratum (measured), full rate on vanilla; `EntityTicking.Enabled: false` restores parity |
| Command surface | `CommandParityScenarios` | Vanilla commands behave identically (incl. unknown-command error codes); `/stratum` and `/sethome` exist on Stratum only |
| Block tick listeners | `BlockTickListenerProbes`, `BlockTickListenerDisabledScenarios` | Far listeners are skipped entirely on Stratum (128-block radius), force-loaded columns stay exempt, toggle restores parity |
| Chunk persistence | `ChunkPersistenceScenarios` | Blocks + chunk moddata survive save/unload/reload cycles identically through Stratum's incremental autosave and pooled reads |
| Random ticks | `RandomTickProbes`, `RandomTickDisabledScenarios` | Vanilla gates random ticks to 5 chunks around Playing clients; Stratum clamps to 3; probed at chunk distance 4 via a staged source mod whose block converts on every random tick |

Field results so far: Stratum's chunk persistence is byte-faithful, its throttles behave
as documented and their toggles genuinely restore vanilla behavior, and no behavioral
drift appeared between stratum.14 and stratum.15. The suite also surfaced
[StratumServer/Stratum#146](https://github.com/StratumServer/Stratum/issues/146)
(shutdown never completes when the game thread is blocked) and
[#151](https://github.com/StratumServer/Stratum/issues/151) (process-killing race in the
background assets packet build), and drove two Atlas features (Playing-state test
players in 0.9.0, assets-build wait on join in 0.9.1).

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
- `scenarios/StratumParity.Scenarios/mods/randomtickprobe/`: test-only source mod
  (compiled by the game's ModLoader) whose block turns to granite on every random tick,
  so random tick coverage becomes countable world state
- `scenarios/StratumParity.Scenarios/fixtures/`: seeded Stratum configs for the toggle
  scenarios (each includes `stratum.json`: the performance file is only read when the
  main config exists)
- `scripts/run-parity.sh`: differential runner (two builds, two runs, one diff)
- `scripts/diff_trx.py`: TRX comparison tool (outcome diffs, timing deltas)

## Versions

Pinned expectations: Vintage Story 1.22.3, Stratum v1.22.3-stratum.15, Atlas 0.9.1.
Stratum moves fast (releases every few days); when a scenario starts failing on a new
Stratum release, that is the suite doing its job.
