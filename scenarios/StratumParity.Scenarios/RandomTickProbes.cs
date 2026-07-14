using Atlas.XUnit;
using Vintagestory.API.MathTools;
using Xunit;

namespace StratumParity.Scenarios;

/// <summary>
/// Statistical probes for Stratum's random tick limiting
/// (Performance.SimulationDistance.LimitRandomTicks, enabled by default, radius 96
/// blocks). The staged stratumparityprobe mod supplies a block that turns to granite on
/// every random tick it receives, so coverage becomes countable world state: a platform
/// of probe blocks near the player converts steadily on both flavors, a platform 200
/// blocks out converts on vanilla and must stay untouched on Stratum.
///
/// Random ticks are sampled (a handful of random positions per chunk per pass), so
/// assertions are statistical: platforms are large enough that the expected conversion
/// count is far from the floors, and the Stratum far-platform assertion is exact zero
/// (outside the radius the chunk is never sampled at all).
/// </summary>
[AtlasWorld(Mods = new[] { "mods/randomtickprobe" })]
public class RandomTickProbes : AtlasScenarioBase
{
    // Random ticks sample very few positions per chunk per pass (measured on vanilla:
    // about 1 conversion per 128 probe blocks per 150 ticks), so the platform is a
    // 16x16x4 slab (1024 blocks in a single column) and the window 450 ticks: expected
    // conversions land around 12, far from the floor of 3.
    private const int MeasurementTicks = 450;
    private const int PlatformEdge = 16;
    private const int PlatformLayers = 4;

    [AtlasScenario(TimeoutMs = 120_000)]
    public async Task FarPlatform_Should_ConvertOnVanillaAndStayUntouchedOnStratum_When_DefaultsActive()
    {
        (List<BlockPos> near, List<BlockPos> far) = await PlacePlatforms(World, "rt-anchor");

        await World.Ticks(MeasurementTicks);

        AssertColumnStillLoaded(World, far[0]);
        int nearConverted = CountConverted(World, near);
        int farConverted = CountConverted(World, far);

        Assert.True(nearConverted > 3,
            $"near platform barely converted ({nearConverted}/{near.Count}) on {ServerFlavor.Name}; setup is broken");

        if (ServerFlavor.IsStratum)
        {
            Assert.True(farConverted == 0,
                $"far platform received random ticks on stratum: {farConverted}/{far.Count} converted");
        }
        else
        {
            Assert.True(farConverted > 3,
                $"far platform barely converted on vanilla: {farConverted}/{far.Count}");
        }
    }

    internal static async Task<(List<BlockPos> Near, List<BlockPos> Far)> PlacePlatforms(
        Atlas.Api.IWorldSession world, string anchorName)
    {
        // The anchor player centers the 96-block random tick radius on spawn. Since
        // Atlas 0.9.1, JoinPlayer itself waits for the server assets packet build to
        // complete (issue #84, born from this suite's CI crash), so the mass SetBlock
        // below no longer races the build's off-thread item enumeration.
        await world.JoinPlayer(anchorName);
        await world.Ticks(5);

        // Vanilla gates random ticks itself: only chunks within BlockTickChunkRange
        // (5 chunks by default) of a Playing client are sampled at all. Stratum's
        // LimitRandomTicks merely clamps that range down to RandomTickDistanceBlocks
        // (96 blocks = 3 chunks by default). The far platform therefore sits at chunk
        // distance 4: inside the vanilla range, outside the Stratum clamp. An offset of
        // exactly 128 guarantees distance 4 whatever the spawn's chunk alignment.
        BlockPos nearAnchor = world.Spawn.AddCopy(8, 1, 8);
        BlockPos farAnchor = world.Spawn.AddCopy(128, 1, 0);

        // KeepLoaded: the 450-tick window outlives the unload timer for a column with no
        // player nearby. Safe for the measurement: Stratum's random tick limiting has no
        // force-loaded exemption (unlike the block listener limit), it gates purely on
        // player distance, and vanilla random-ticks every loaded column regardless.
        world.Api.WorldManager.LoadChunkColumnPriority(farAnchor.X / 32, farAnchor.Z / 32,
            new Vintagestory.API.Server.ChunkLoadOptions { KeepLoaded = true });
        await world.Until(
            () => world.Api.World.BlockAccessor.GetChunkAtBlockPos(farAnchor) != null,
            timeoutTicks: 600);

        return (PlacePlatform(world, nearAnchor), PlacePlatform(world, farAnchor));
    }

    private static List<BlockPos> PlacePlatform(Atlas.Api.IWorldSession world, BlockPos corner)
    {
        var positions = new List<BlockPos>(PlatformEdge * PlatformEdge * PlatformLayers);
        for (int x = 0; x < PlatformEdge; x++)
        {
            for (int z = 0; z < PlatformEdge; z++)
            {
                for (int y = 0; y < PlatformLayers; y++)
                {
                    BlockPos pos = corner.AddCopy(x, y, z);
                    world.SetBlock("stratumparityprobe:probe", pos);
                    positions.Add(pos);
                }
            }
        }
        return positions;
    }

    internal static int CountConverted(Atlas.Api.IWorldSession world, List<BlockPos> platform)
    {
        int converted = 0;
        foreach (BlockPos pos in platform)
        {
            if (world.BlockAt(pos).Code.ToString() == "game:rock-granite")
            {
                converted++;
            }
        }
        return converted;
    }

    internal static void AssertColumnStillLoaded(Atlas.Api.IWorldSession world, BlockPos pos)
    {
        Assert.True(world.Api.World.BlockAccessor.GetChunkAtBlockPos(pos) != null,
            "far column unloaded mid-measurement; the probe window is too long for the unload timer");
    }
}
