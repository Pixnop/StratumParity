namespace StratumParity.Scenarios;

/// <summary>
/// Detects which server flavor the suite is running against. Stratum ships a rebuilt
/// VintagestoryLib that contains its runtime type; vanilla does not.
/// </summary>
public static class ServerFlavor
{
    public static bool IsStratum { get; } =
        Type.GetType("Vintagestory.Server.StratumRuntime, VintagestoryLib") != null;

    public static string Name => IsStratum ? "stratum" : "vanilla";
}
