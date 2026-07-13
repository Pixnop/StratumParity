using System.Reflection;
using Atlas.Api;

namespace StratumParity.Scenarios;

/// <summary>
/// Best-effort wait for the server's background assets packet build to settle.
///
/// The build enumerates every block and item off-thread; scenario activity that mutates
/// world state while it runs can fire "Collection was modified" inside
/// ItemTypeNet.GetItemTypePacket, which kills the whole test process from a pool thread.
/// The staged probe mod lengthens the build enough for that race to hit slow CI runners.
///
/// In Atlas hosts the packet is only built once a player join needs it, so callers wait
/// AFTER JoinPlayer and BEFORE mass world mutation. The wait is soft on purpose: it polls
/// the serverAssetsPacket box (the shape Atlas itself reads at dispose time) and returns
/// as soon as the packet reports built, but if the signal never comes (engine shape
/// drift, or a send path that bypasses the box) it settles for a grace period instead of
/// failing the scenario.
/// </summary>
public static class ServerAssets
{
    private const int PollBatches = 30;
    private const int TicksPerBatch = 10;

    public static async Task WaitUntilSettled(IWorldSession world)
    {
        object serverMain = world.Api.World;
        FieldInfo? boxField = serverMain.GetType()
            .GetField("serverAssetsPacket", BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public);
        PropertyInfo? lengthProperty = boxField?.FieldType
            .GetProperty("Length", BindingFlags.Instance | BindingFlags.Public);
        FieldInfo? lengthField = boxField?.FieldType
            .GetField("Length", BindingFlags.Instance | BindingFlags.Public);

        int ReadLength()
        {
            object? box = boxField?.GetValue(serverMain);
            if (box == null)
            {
                return 0;
            }
            object? value = lengthProperty != null ? lengthProperty.GetValue(box) : lengthField?.GetValue(box);
            return value is int length ? length : 0;
        }

        bool canObserve = boxField != null && (lengthProperty != null || lengthField != null);
        for (int batch = 0; batch < PollBatches; batch++)
        {
            if (canObserve && ReadLength() > 0)
            {
                return;
            }
            await world.Ticks(TicksPerBatch);
        }
    }
}
