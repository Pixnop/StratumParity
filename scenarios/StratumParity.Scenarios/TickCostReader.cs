using System.Reflection;
using Atlas.Api;

namespace StratumParity.Scenarios;

/// <summary>
/// Reads the embedded server's own per-tick work-time counter, the only cost signal present
/// on both vanilla and Stratum. ServerMain accumulates <c>tickTimeTotal += lastFramePassedTime.
/// ElapsedMilliseconds</c> per pass (after tick work, before the pacing sleep) into a 4-bucket
/// StatsCollector that rotates every ~2 real seconds; the average work-ms per tick over a bucket
/// is <c>tickTimeTotal / ticksTotal</c>. This is the same figure Stratum's own overload path reads.
///
/// Always read the PREVIOUS completed bucket (index-1): the current one is being filled and is
/// zeroed on the wall-clock rotation, so a naive read or a cross-rotation delta is invalid. The
/// counter has 1ms integer resolution, so an idle headless tick floors to 0 and the load must be
/// sized to produce multi-ms work. Reflection on public ServerMain fields (not an Atlas/VS API
/// surface), so it graceful-degrades to NaN if a future engine renames them, exactly like Atlas's
/// own EntitySimulationTicks shell. Runs on the game thread (call between Ticks continuations).
/// </summary>
public static class TickCostReader
{
    private static bool resolved;
    private static FieldInfo? collectorField;
    private static FieldInfo? indexField;
    private static FieldInfo? tickTimeTotalField;
    private static FieldInfo? ticksTotalField;

    private const BindingFlags Flags = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;

    /// <summary>Average work-milliseconds per tick over the last completed bucket, or NaN if the
    /// counter is unavailable or no complete bucket exists yet.</summary>
    public static double AverageMsPerTick(IWorldSession world)
    {
        try
        {
            object server = world.Api.World;
            if (!resolved)
            {
                Resolve(server.GetType());
            }
            if (collectorField == null || indexField == null || tickTimeTotalField == null || ticksTotalField == null)
            {
                return double.NaN;
            }

            var buckets = (Array?)collectorField.GetValue(server);
            if (buckets == null || buckets.Length == 0)
            {
                return double.NaN;
            }
            int idx = (int)indexField.GetValue(server)!;
            int prev = ((idx - 1) % buckets.Length + buckets.Length) % buckets.Length;
            object? bucket = buckets.GetValue(prev);
            if (bucket == null)
            {
                return double.NaN;
            }

            long ms = (long)tickTimeTotalField.GetValue(bucket)!;
            long ticks = (long)ticksTotalField.GetValue(bucket)!;
            return ticks > 0 ? (double)ms / ticks : double.NaN;
        }
        catch (Exception)
        {
            return double.NaN;
        }
    }

    private static void Resolve(Type serverType)
    {
        resolved = true;
        collectorField = serverType.GetField("StatsCollector", Flags);
        indexField = serverType.GetField("StatsCollectorIndex", Flags);
        Type? bucketType = collectorField?.FieldType.GetElementType();
        if (bucketType != null)
        {
            tickTimeTotalField = bucketType.GetField("tickTimeTotal", Flags);
            ticksTotalField = bucketType.GetField("ticksTotal", Flags);
        }
    }
}
