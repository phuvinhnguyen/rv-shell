pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Services.Mpris

// The MPRIS player the bar and media keys act on: whichever is playing,
// otherwise the first one that exists.
Singleton {
    readonly property var players: Mpris.players.values
    readonly property var player: players.find(p => p.isPlaying) || players[0] || null

    function toggle() { if (player && player.canTogglePlaying) player.togglePlaying(); }
    function next() { if (player && player.canGoNext) player.next(); }
    function previous() { if (player && player.canGoPrevious) player.previous(); }
    function stop() { if (player) player.stop(); }
}
