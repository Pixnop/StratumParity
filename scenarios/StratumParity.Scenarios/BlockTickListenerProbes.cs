using Atlas.Api;
using Atlas.XUnit;
using Vintagestory.API.MathTools;
using Vintagestory.API.Server;
using Xunit;

namespace StratumParity.Scenarios;

/// <summary>
/// Probes Stratum's block game-tick listener limiting
/// (Performance.SimulationDistance.LimitBlockGameTickListeners, enabled by default,
/// radius 128 blocks). Two positioned tick listeners are registered through the public
/// API: one near the anchor player (its column is always active, it doubles as the tick
/// clock) and one 200 blocks out. Vanilla fires both; Stratum must freeze the far one
/// entirely, except when its column is force-loaded (TickForceLoadedBlockListeners,
/// also default on), which the second scenario pins down.
/// </summary>
public class BlockTickListenerProbes : AtlasScenarioBase
{
    private const int MeasurementTicks = 120;

    [AtlasScenario(TimeoutMs = 120_000)]
    public async Task FarListener_Should_FireOnVanillaAndFreezeOnStratum_When_DefaultsActive()
    {
        (int[] near, int[] far) = await RegisterProbePair(
            World, "bt-anchor", keepFarLoaded: false, farOffsetX: 200, farOffsetZ: 0);

        int nearBefore = near[0];
        int farBefore = far[0];
        await World.Ticks(MeasurementTicks);
        int nearDelta = near[0] - nearBefore;
        int farDelta = far[0] - farBefore;

        Assert.True(nearDelta > MeasurementTicks / 4,
            $"near listener barely fired ({nearDelta}/{MeasurementTicks}) on {ServerFlavor.Name}; setup is broken");

        double ratio = (double)farDelta / nearDelta;
        if (ServerFlavor.IsStratum)
        {
            // Outside the active columns the listener is not throttled but skipped
            // entirely, so the expected ratio is 0; the bound stays loose on purpose.
            Assert.True(ratio < 0.2,
                $"far listener not frozen on stratum: far={farDelta} near={nearDelta} ratio={ratio:F2}");
        }
        else
        {
            Assert.True(ratio > 0.8,
                $"far listener limited on vanilla: far={farDelta} near={nearDelta} ratio={ratio:F2}");
        }
    }

    [AtlasScenario(TimeoutMs = 120_000)]
    public async Task ForceLoadedFarListener_Should_KeepFiring_When_ColumnIsKeptLoaded()
    {
        // Stratum exempts force-loaded columns from the limit
        // (TickForceLoadedBlockListeners, default true); vanilla has no limit at all.
        // One unconditional assertion covers both flavors.
        // Distinct far column from the default-behavior scenario: both scenarios share
        // the class host and world, and a KeepLoaded column stays force-loaded for the
        // rest of the class, which would exempt the other probe and void its assertion.
        (int[] near, int[] far) = await RegisterProbePair(
            World, "bt-anchor2", keepFarLoaded: true, farOffsetX: 0, farOffsetZ: 200);

        int nearBefore = near[0];
        int farBefore = far[0];
        await World.Ticks(MeasurementTicks);
        int nearDelta = near[0] - nearBefore;
        int farDelta = far[0] - farBefore;

        Assert.True(nearDelta > MeasurementTicks / 4,
            $"near listener barely fired ({nearDelta}/{MeasurementTicks}) on {ServerFlavor.Name}; setup is broken");

        double ratio = (double)farDelta / nearDelta;
        Assert.True(ratio > 0.8,
            $"force-loaded far listener limited on {ServerFlavor.Name}: far={farDelta} near={nearDelta} ratio={ratio:F2}");
    }

    /// <summary>
    /// Shared setup: a Playing anchor player (Stratum builds its active-column set from
    /// IsPlayingClient positions, see PlayerClientState), one counted listener next to
    /// them, one 200 blocks out, the far column loaded and optionally kept loaded.
    /// Counters are single-cell arrays so the tick lambdas can mutate them.
    /// </summary>
    internal static async Task<(int[] Near, int[] Far)> RegisterProbePair(
        IWorldSession world, string anchorName, bool keepFarLoaded, int farOffsetX, int farOffsetZ)
    {
        ITestPlayer anchor = await world.JoinPlayer(anchorName);
        PlayerClientState.MarkPlaying(world.Api, anchor.Player);
        await world.Ticks(5);

        BlockPos nearPos = world.Spawn.AddCopy(5, 1, 0);
        BlockPos farPos = world.Spawn.AddCopy(farOffsetX, 1, farOffsetZ);

        ChunkLoadOptions? options = keepFarLoaded ? new ChunkLoadOptions { KeepLoaded = true } : null;
        world.Api.WorldManager.LoadChunkColumnPriority(farPos.X / 32, farPos.Z / 32, options);
        await world.Until(
            () => world.Api.World.BlockAccessor.GetChunkAtBlockPos(farPos) != null,
            timeoutTicks: 600);

        int[] near = RegisterCountingListener(world, nearPos);
        int[] far = RegisterCountingListener(world, farPos);

        await world.Ticks(10);
        return (near, far);
    }

    private static int[] RegisterCountingListener(IWorldSession world, BlockPos pos)
    {
        int[] counter = new int[1];
        world.Api.Event.RegisterGameTickListener(
            _ => counter[0]++,
            pos,
            errorHandler: null,
            millisecondInterval: 1,
            initialDelayOffsetMs: 0);
        return counter;
    }
}
