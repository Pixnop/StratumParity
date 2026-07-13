using Atlas.XUnit;
using Vintagestory.API.MathTools;
using Xunit;

namespace StratumParity.Scenarios;

/// <summary>
/// Same probe as <see cref="RandomTickProbes"/>, but the seeded
/// stratum-performance.json turns SimulationDistance.LimitRandomTicks off before boot.
/// Stratum must then random-tick far chunks again; vanilla ignores the file entirely.
/// One unconditional assertion proves parity on both flavors and proves the toggle
/// restores vanilla behavior. As with every Stratum config fixture, stratum.json must be
/// seeded too or the performance file is never read.
/// </summary>
[AtlasWorld(Mods = new[] { "mods/randomtickprobe" })]
[AtlasDataFiles("fixtures/stratum-randomticks-off", TargetPath = "")]
public class RandomTickDisabledScenarios : AtlasScenarioBase
{
    [AtlasScenario(TimeoutMs = 120_000)]
    public async Task FarPlatform_Should_Convert_When_LimitDisabledByConfig()
    {
        (List<BlockPos> near, List<BlockPos> far) =
            await RandomTickProbes.PlacePlatforms(World, "rt-anchor2");

        await World.Ticks(450);

        RandomTickProbes.AssertColumnStillLoaded(World, far[0]);
        int nearConverted = RandomTickProbes.CountConverted(World, near);
        int farConverted = RandomTickProbes.CountConverted(World, far);

        Assert.True(nearConverted > 3,
            $"near platform barely converted ({nearConverted}) on {ServerFlavor.Name}; setup is broken");
        Assert.True(farConverted > 3,
            $"far platform untouched on {ServerFlavor.Name} despite LimitRandomTicks=false: {farConverted} converted");
    }
}
