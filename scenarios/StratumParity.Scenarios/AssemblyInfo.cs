using Atlas.XUnit;
using Xunit;

// Required by Atlas: one embedded server per test class, classes must run sequentially.
[assembly: CollectionBehavior(DisableTestParallelization = true)]

// Test-only source mod (compiled by the game's ModLoader): a block that turns to granite
// on every random tick, the observable the random tick probes count. Staged for every
// class; inert unless a scenario places the block.
[assembly: AtlasMods("mods/randomtickprobe")]
