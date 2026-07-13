using Vintagestory.API.Common;
using Vintagestory.API.Common.Entities;

namespace StratumParity.Scenarios;

/// <summary>
/// Counts how many times the server ticks an entity. Attached at runtime from scenarios;
/// Entity.OnGameTick drives behavior ticks, so when Stratum's distance-band throttling
/// skips an entity's tick, this counter freezes with it.
/// </summary>
public sealed class TickCounterBehavior : EntityBehavior
{
    public int Ticks;

    public TickCounterBehavior(Entity entity) : base(entity)
    {
    }

    public override void OnGameTick(float deltaTime) => Ticks++;

    public override string PropertyName() => "stratumparity:tickcounter";
}
