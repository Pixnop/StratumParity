using Atlas.Api;
using Atlas.XUnit;
using Vintagestory.API.MathTools;
using Xunit;

namespace StratumParity.Scenarios;

/// <summary>
/// Baseline parity: the fundamentals a Stratum server must do exactly like vanilla.
/// Every scenario here asserts the same thing on both flavors; a failure on Stratum
/// only is a behavior regression.
/// </summary>
public class SmokeParityScenarios : AtlasScenarioBase
{
    [AtlasScenario]
    public async Task Server_Should_BootAndAdvanceClock_When_Ticked()
    {
        // The game calendar pauses on an empty server (same on both flavors), so the boot
        // check reads the server clock instead.
        long before = World.Api.World.ElapsedMilliseconds;
        await World.Ticks(30);
        Assert.True(World.Api.World.ElapsedMilliseconds > before,
            $"server clock did not advance on {ServerFlavor.Name}");
    }

    [AtlasScenario]
    public async Task SetBlock_Should_ReadBackSameCode_When_Placed()
    {
        BlockPos pos = World.Spawn.AddCopy(2, 1, 2);
        World.SetBlock("game:rock-granite", pos);
        await World.Ticks(5);
        Assert.Equal("game:rock-granite", World.BlockAt(pos).Code.ToString());
    }

    [AtlasScenario]
    public async Task JoinedPlayer_Should_StayConnected_When_ServerTicks()
    {
        // On Stratum this doubles as a packet-policing check: StratumPacketLimiter has no
        // single-player exemption, so a kicked fake player would show up as IsConnected false.
        ITestPlayer player = await World.JoinPlayer("parity-smoke");
        await World.Ticks(100);
        Assert.True(player.IsConnected,
            $"fake player was disconnected on {ServerFlavor.Name}");
    }
}
