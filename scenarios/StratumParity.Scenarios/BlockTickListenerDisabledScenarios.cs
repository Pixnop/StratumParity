using Atlas.XUnit;
using Xunit;

namespace StratumParity.Scenarios;

/// <summary>
/// Same probe as <see cref="BlockTickListenerProbes"/>, but the seeded
/// stratum-performance.json turns SimulationDistance.LimitBlockGameTickListeners off
/// before boot. Stratum must then fire far listeners at full rate again; vanilla ignores
/// the file entirely. One unconditional assertion proves parity on both flavors, and
/// proves the config toggle actually restores vanilla behavior on Stratum. As with every
/// Stratum config fixture, stratum.json must be seeded too or the performance file is
/// never read.
/// </summary>
[AtlasDataFiles("fixtures/stratum-blockticks-off", TargetPath = "")]
public class BlockTickListenerDisabledScenarios : AtlasScenarioBase
{
    [AtlasScenario(TimeoutMs = 120_000)]
    public async Task FarListener_Should_FireFullRate_When_LimitDisabledByConfig()
    {
        (int[] near, int[] far) = await BlockTickListenerProbes.RegisterProbePair(
            World, "bt-anchor3", keepFarLoaded: false, farOffsetX: 200, farOffsetZ: 0);

        int nearBefore = near[0];
        int farBefore = far[0];
        await World.Ticks(120);
        int nearDelta = near[0] - nearBefore;
        int farDelta = far[0] - farBefore;

        Assert.True(nearDelta > 30,
            $"near listener barely fired ({nearDelta}/120) on {ServerFlavor.Name}; setup is broken");

        double ratio = (double)farDelta / nearDelta;
        Assert.True(ratio > 0.8,
            $"far listener limited on {ServerFlavor.Name} despite LimitBlockGameTickListeners=false: " +
            $"far={farDelta} near={nearDelta} ratio={ratio:F2}");
    }
}
