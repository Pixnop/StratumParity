using Atlas.XUnit;
using Xunit;

namespace StratumParity.Scenarios;

/// <summary>
/// Same probe as <see cref="EntityTickingProbes"/>, but the seeded
/// stratum-performance.json turns Performance.EntityTicking off before boot. Stratum must
/// then tick far entities at full rate again; vanilla ignores the file entirely. One
/// unconditional assertion therefore proves parity on both flavors, and proves that the
/// config toggle actually restores vanilla behavior on Stratum.
///
/// The fixture must also seed a stratum.json: StratumRuntime.LoadOrCreateConfig only
/// reads stratum-performance.json when stratum.json already exists, otherwise it writes
/// defaults over everything.
/// </summary>
[AtlasDataFiles("fixtures/stratum-entityticking-off", TargetPath = "")]
public class EntityTickingDisabledScenarios : AtlasScenarioBase
{
    [AtlasScenario(TimeoutMs = 120_000)]
    public async Task FarEntity_Should_TickFullRate_When_EntityTickingDisabledByConfig()
    {
        (TickCounterBehavior near, TickCounterBehavior far) =
            await EntityTickingProbes.SpawnProbePair(World);

        int nearBefore = near.Ticks;
        int farBefore = far.Ticks;
        await World.Ticks(150);
        int nearDelta = near.Ticks - nearBefore;
        int farDelta = far.Ticks - farBefore;

        Assert.True(nearDelta > 37,
            $"near probe barely ticked ({nearDelta}/150) on {ServerFlavor.Name}; setup is broken");

        double ratio = (double)farDelta / nearDelta;
        Assert.True(ratio > 0.8,
            $"far probe throttled on {ServerFlavor.Name} despite EntityTicking.Enabled=false: " +
            $"far={farDelta} near={nearDelta} ratio={ratio:F2}");
    }
}
