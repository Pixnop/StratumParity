using System.Collections;
using System.Reflection;
using Vintagestory.API.Server;

namespace StratumParity.Scenarios;

/// <summary>
/// Promotes an Atlas fake player's connection to EnumClientState.Playing.
///
/// Atlas fake players deliberately stop at the Connected state (the join handshake's
/// packets 26/29 are never sent). Vanilla ticks entities regardless, but Stratum keys all
/// of its distance-band features on IsPlayingClient: with only Connected clients it sees
/// an empty server and disables entity throttling entirely. Probes that measure those
/// features must first promote their anchor player.
///
/// Uses reflection on public engine members (ServerMain.Clients, ConnectedClient.State)
/// so the project keeps compiling against VintagestoryAPI only.
/// </summary>
public static class PlayerClientState
{
    public static void MarkPlaying(ICoreServerAPI api, IServerPlayer player)
    {
        object serverMain = api.World;
        object clients = GetMember(serverMain, "Clients")
            ?? throw Missing("ServerMain.Clients");

        foreach (DictionaryEntry entry in (IDictionary)clients)
        {
            object client = entry.Value!;
            object? clientPlayer = GetMember(client, "Player");
            if (!ReferenceEquals(clientPlayer, player))
            {
                continue;
            }

            const BindingFlags any = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
            Type clientType = client.GetType();
            FieldInfo? stateField = clientType.GetField("State", any);
            PropertyInfo? stateProperty = clientType.GetProperty("State", any);
            if (stateField != null)
            {
                stateField.SetValue(client, Enum.Parse(stateField.FieldType, "Playing"));
            }
            else if (stateProperty?.SetMethod != null)
            {
                stateProperty.SetValue(client, Enum.Parse(stateProperty.PropertyType, "Playing"));
            }
            else
            {
                throw Missing("ConnectedClient.State");
            }
            return;
        }

        throw new InvalidOperationException(
            $"No ConnectedClient found for player '{player.PlayerName}'.");
    }

    private static object? GetMember(object target, string name)
    {
        Type type = target.GetType();
        const BindingFlags flags = BindingFlags.Instance | BindingFlags.Public;
        return type.GetField(name, flags)?.GetValue(target)
            ?? type.GetProperty(name, flags)?.GetValue(target);
    }

    private static InvalidOperationException Missing(string member) => new(
        $"{member} not found; the game version changed shape and this helper needs updating.");
}
