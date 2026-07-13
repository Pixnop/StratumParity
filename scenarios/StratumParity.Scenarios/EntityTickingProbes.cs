using Atlas.Api;
using Atlas.XUnit;
using Vintagestory.API.Common;
using Vintagestory.API.Common.Entities;
using Vintagestory.API.MathTools;
using Xunit;

namespace StratumParity.Scenarios;

/// <summary>
/// Probes Stratum's distance-banded entity ticking (Performance.EntityTicking, enabled by
/// default). Two identical item entities are spawned: one near the only player (near band,
/// ticks every server tick on both flavors) and one 200 blocks away (beyond the far band).
/// Vanilla ticks both at full rate; Stratum ticks the far one every VeryFarTickInterval
/// (10 by default). The near entity doubles as the tick clock, so assertions are ratios
/// and stay robust against wall-clock noise.
/// </summary>
public class EntityTickingProbes : AtlasScenarioBase
{
    private const int MeasurementTicks = 150;

    [AtlasScenario(TimeoutMs = 120_000)]
    public async Task FarEntity_Should_TickFullRateOnVanillaAndThrottledOnStratum_When_DefaultsActive()
    {
        (TickCounterBehavior near, TickCounterBehavior far) = await SpawnProbePair(World);

        int nearBefore = near.Ticks;
        int farBefore = far.Ticks;
        await World.Ticks(MeasurementTicks);
        int nearDelta = near.Ticks - nearBefore;
        int farDelta = far.Ticks - farBefore;

        // The near probe is the tick clock, not an absolute-rate assertion: observed rates
        // differ between flavors even in the near band (Stratum ticks entities at roughly
        // half the harness tick rate across the board). The sanity floor only catches a
        // dead clock.
        Assert.True(nearDelta > MeasurementTicks / 4,
            $"near probe barely ticked ({nearDelta}/{MeasurementTicks}) on {ServerFlavor.Name}; setup is broken");

        double ratio = (double)farDelta / nearDelta;
        if (ServerFlavor.IsStratum)
        {
            // Default far throttling is 1 tick in 10; anything under half rate proves the
            // throttle is active without being brittle about the exact stride.
            Assert.True(ratio < 0.5,
                $"far probe not throttled on stratum: far={farDelta} near={nearDelta} ratio={ratio:F2}");
        }
        else
        {
            Assert.True(ratio > 0.8,
                $"far probe throttled on vanilla: far={farDelta} near={nearDelta} ratio={ratio:F2}");
        }
    }

    /// <summary>
    /// Shared setup for the ticking probes: a player as the distance anchor, one counted
    /// item entity next to them, one far beyond every Stratum band, both settled to rest
    /// (Stratum does not throttle moving entities, so measurement starts once stationary).
    /// </summary>
    internal static async Task<(TickCounterBehavior Near, TickCounterBehavior Far)> SpawnProbePair(
        IWorldSession world)
    {
        const int farDistanceBlocks = 200;

        // The player is the reference point of every distance band. Without one, Stratum
        // has no anchor and vanilla tracking deactivates entities too. Stratum only
        // counts IsPlayingClient clients; since Atlas 0.9.0, JoinPlayer completes the
        // real join sequence and the player reaches Playing on its own.
        await world.JoinPlayer("tick-anchor");
        await world.Ticks(5);

        BlockPos nearPos = world.Spawn.AddCopy(5, 1, 0);
        BlockPos farPos = world.Spawn.AddCopy(farDistanceBlocks, 1, 0);

        // Keep the far column loaded server-side; there is no player near it to do so.
        world.Api.WorldManager.LoadChunkColumnPriority(farPos.X / 32, farPos.Z / 32);
        await world.Until(
            () => world.Api.World.BlockAccessor.GetChunkAtBlockPos(farPos) != null,
            timeoutTicks: 600);

        TickCounterBehavior near = SpawnCountedDummy(world, nearPos);
        TickCounterBehavior far = SpawnCountedDummy(world, farPos);

        await world.Ticks(60);
        return (near, far);
    }

    private static TickCounterBehavior SpawnCountedDummy(IWorldSession world, BlockPos pos)
    {
        // A straw dummy stands perfectly still. That matters: Stratum exempts moving
        // entities from throttling (SkipMovingEntities, threshold 0.01 blocks/tick), and
        // even a dropped item keeps enough residual motion to stay exempt forever.
        Entity dummy = world.SpawnEntity("game:strawdummy", pos);

        var counter = new TickCounterBehavior(dummy);
        dummy.SidedProperties.Behaviors.Add(counter);
        return counter;
    }
}
