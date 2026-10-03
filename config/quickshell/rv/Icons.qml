pragma Singleton

import QtQuick
import Quickshell

// Nerd Font (Material Design) glyphs used across the shell. Any font with
// Nerd Font symbols works; set it in `rv settings` → Theme → font.
Singleton {
    function g(code) { return String.fromCodePoint(code); }

    readonly property string debian: g(0xf306)
    readonly property string apps: g(0xf003b)
    readonly property string search: g(0xf0349)
    readonly property string clipboard: g(0xf0a38)
    readonly property string tools: g(0xf1064)
    readonly property string terminal: g(0xf018d)
    readonly property string calculator: g(0xf00ec)
    readonly property string web: g(0xf059f)
    readonly property string answer: g(0xf06e9)
    readonly property string openExternal: g(0xf03cc)
    readonly property string application: g(0xf08c6)
    readonly property string cog: g(0xf0493)
    readonly property string calendar: g(0xf00ed)
    readonly property string close: g(0xf0156)
    readonly property string check: g(0xf012c)
    readonly property string trash: g(0xf09e7)
    readonly property string chevronUp: g(0xf0143)
    readonly property string chevronDown: g(0xf0140)
    readonly property string monitor: g(0xf0379)
    readonly property string keyboard: g(0xf030c)
    readonly property string emoji: g(0xf01f2)

    readonly property string wifiOff: g(0xf092e)
    readonly property var wifi: [g(0xf091f), g(0xf0922), g(0xf0925), g(0xf0928)]
    readonly property string ethernet: g(0xf0200)
    readonly property string bluetooth: g(0xf00af)
    readonly property string bluetoothOff: g(0xf00b2)
    readonly property string bluetoothConnected: g(0xf00b1)

    readonly property string volumeHigh: g(0xf057e)
    readonly property string volumeMedium: g(0xf0580)
    readonly property string volumeLow: g(0xf057f)
    readonly property string volumeOff: g(0xf0581)
    readonly property string microphone: g(0xf036c)
    readonly property string brightness: g(0xf00df)

    readonly property string batteryFull: g(0xf0079)
    readonly property string batteryCharging: g(0xf0084)
    readonly property string batteryAlert: g(0xf0083)
    function battery(fraction) {
        if (fraction >= 0.95) return batteryFull;
        if (fraction < 0.1) return batteryAlert;
        return g(0xf007a + Math.min(8, Math.floor(fraction * 10) - 1));
    }

    readonly property string power: g(0xf0425)
    readonly property string lock: g(0xf033e)
    readonly property string sleep: g(0xf04b2)
    readonly property string logout: g(0xf0343)
    readonly property string restart: g(0xf0709)
    readonly property string coffee: g(0xf0176)
    readonly property string coffeeOutline: g(0xf06ca)

    readonly property string bell: g(0xf009a)
    readonly property string bellOutline: g(0xf009c)
    readonly property string bellOff: g(0xf0a91)

    readonly property string music: g(0xf075a)
    readonly property string play: g(0xf040a)
    readonly property string pause: g(0xf03e4)
    readonly property string next: g(0xf04ad)
    readonly property string previous: g(0xf04ae)

    readonly property string cpu: g(0xf061a)
    readonly property string memory: g(0xf035b)
}
