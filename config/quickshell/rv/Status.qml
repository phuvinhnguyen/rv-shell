import QtQuick
import Quickshell
import Quickshell.Bluetooth
import Quickshell.Networking
import Quickshell.Services.Pipewire
import Quickshell.Services.UPower

// Network, Bluetooth, volume and battery. All state comes from DBus and
// PipeWire signals, so nothing here polls. Clicks open the matching
// terminal app; the volume button also scrolls and mutes.
Column {
    id: root
    spacing: 2

    function values(model) { return model ? (model.values !== undefined ? model.values : model) : []; }

    // ---- Network -------------------------------------------------------------
    readonly property var devices: values(Networking.devices)
    readonly property var wired: devices.find(d => d.type === DeviceType.Wired && d.connected) || null
    readonly property var wifiDevice: devices.find(d => d.type === DeviceType.Wifi) || null
    readonly property var wifiNetwork: wifiDevice ? (values(wifiDevice.networks).find(n => n.connected) || null) : null
    readonly property real wifiStrength: wifiNetwork ? wifiNetwork.signalStrength : 0
    // Hotel / guest Wi-Fi that wants a web sign-in before giving internet.
    readonly property bool needsSignIn: Networking.connectivity === NetworkConnectivity.Portal
    readonly property bool limited: Networking.connectivity === NetworkConnectivity.Limited

    BarButton {
        id: net
        icon: root.wired ? Icons.ethernet
            : root.wifiNetwork ? Icons.wifi[Math.max(0, Math.min(3, Math.floor(root.wifiStrength * 4)))]
            : Icons.wifiOff
        iconColor: root.needsSignIn || root.limited ? Config.warn : root.wired || root.wifiNetwork ? Config.text : Config.muted
        badge: root.needsSignIn ? "!" : ""
        onHoveredChanged: netTip.hover(hovered)
        onClicked: button => {
            netTip.hover(false);
            // A plain-HTTP page: the portal intercepts it and shows its sign-in.
            if (root.needsSignIn && button === Qt.LeftButton) Quickshell.execDetached(["xdg-open", "http://neverssl.com"]);
            else Config.run(["open", "wifi"]);
        }
        BarPopup {
            id: netTip
            anchorItem: net
            Tip {
                title: root.wired ? "Wired" : root.wifiNetwork ? root.wifiNetwork.name : (Networking.wifiEnabled ? "Not connected" : "Wi-Fi off")
                lines: root.needsSignIn ? ["Sign-in required", "click: open the sign-in page · right: Wi-Fi settings"]
                       : root.wired ? [root.wired.name].concat(root.limited ? ["No internet"] : [])
                       : root.wifiNetwork
                       ? [`Signal ${Math.round(root.wifiStrength * 100)}%`].concat(root.limited ? ["Connected, no internet"] : []).concat(["click: Wi-Fi settings"])
                       : ["click: Wi-Fi settings"]
            }
        }
    }

    // ---- Bluetooth -----------------------------------------------------------
    readonly property var adapter: Bluetooth.defaultAdapter
    readonly property var btConnected: values(Bluetooth.devices).filter(d => d.connected)

    BarButton {
        id: bt
        visible: root.adapter !== null
        icon: !root.adapter || !root.adapter.enabled ? Icons.bluetoothOff
            : root.btConnected.length > 0 ? Icons.bluetoothConnected : Icons.bluetooth
        iconColor: root.adapter && root.adapter.enabled ? (root.btConnected.length ? Config.accent : Config.text) : Config.muted
        onHoveredChanged: btTip.hover(hovered)
        onClicked: button => {
            btTip.hover(false);
            if (button === Qt.RightButton && root.adapter) root.adapter.enabled = !root.adapter.enabled;
            else Config.run(["open", "bluetooth"]);
        }
        BarPopup {
            id: btTip
            anchorItem: bt
            Tip {
                title: root.adapter && root.adapter.enabled ? "Bluetooth on" : "Bluetooth off"
                lines: root.btConnected.map(d => d.name + (d.batteryAvailable ? `  ${Math.round(d.battery * 100)}%` : ""))
                       .concat(["click: devices · right: on/off"])
            }
        }
    }

    // ---- Volume --------------------------------------------------------------
    readonly property var sink: Pipewire.defaultAudioSink
    readonly property real volume: sink && sink.audio ? sink.audio.volume : 0
    readonly property bool muted: sink && sink.audio ? sink.audio.muted : true

    PwObjectTracker { objects: [root.sink] }

    BarButton {
        id: vol
        icon: root.muted || root.volume === 0 ? Icons.volumeOff
            : root.volume > 0.66 ? Icons.volumeHigh : root.volume > 0.33 ? Icons.volumeMedium : Icons.volumeLow
        iconColor: root.muted ? Config.muted : Config.text
        onHoveredChanged: volTip.hover(hovered)
        onClicked: button => {
            if (button === Qt.LeftButton) { volTip.hover(false); Config.run(["open", "audio"]); }
            else if (root.sink && root.sink.audio) root.sink.audio.muted = !root.sink.audio.muted;
        }
        onScrolled: delta => {
            if (!root.sink || !root.sink.audio) return;
            root.sink.audio.muted = false;
            root.sink.audio.volume = Math.max(0, Math.min(1, root.volume + (delta > 0 ? 0.05 : -0.05)));
        }
        BarPopup {
            id: volTip
            anchorItem: vol
            Tip {
                title: root.muted ? "Muted" : `Volume ${Math.round(root.volume * 100)}%`
                lines: [root.sink ? (root.sink.description || root.sink.name) : "No output", "scroll: adjust · right: mute"]
            }
        }
    }

    // ---- Battery -------------------------------------------------------------
    readonly property var battery: UPower.displayDevice
    readonly property bool hasBattery: battery && battery.ready && battery.isLaptopBattery && Config.get("bar", "showBattery", true)
    readonly property bool charging: battery && (battery.state === UPowerDeviceState.Charging || battery.state === UPowerDeviceState.FullyCharged)

    Item {
        id: bat
        visible: root.hasBattery
        width: Config.barWidth - 12
        height: batColumn.implicitHeight + 8

        Column {
            id: batColumn
            anchors.centerIn: parent
            spacing: 0
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: root.charging ? Icons.batteryCharging : Icons.battery(root.battery ? root.battery.percentage : 0)
                color: root.charging ? Config.good : (root.battery && root.battery.percentage < 0.15 ? Config.bad : Config.text)
                font.family: Config.font
                font.pixelSize: Math.round(Config.fontSize * 1.25)
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: root.battery ? Math.round(root.battery.percentage * 100) : ""
                color: Config.muted
                font.family: Config.font
                font.pixelSize: Config.fontSize - 3
                font.bold: true
            }
        }
        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onContainsMouseChanged: batTip.hover(containsMouse)
            // Click cycles the power mode: saver → balanced → performance.
            onClicked: {
                const order = [PowerProfile.PowerSaver, PowerProfile.Balanced]
                    .concat(PowerProfiles.hasPerformanceProfile ? [PowerProfile.Performance] : []);
                PowerProfiles.profile = order[(order.indexOf(PowerProfiles.profile) + 1) % order.length];
            }
        }
        BarPopup {
            id: batTip
            anchorItem: bat
            Tip {
                function duration(s) {
                    if (!s) return "";
                    const h = Math.floor(s / 3600), m = Math.round(s % 3600 / 60);
                    return h ? `${h}h ${m}m` : `${m}m`;
                }
                title: root.battery ? `Battery ${Math.round(root.battery.percentage * 100)}%` : "Battery"
                readonly property string mode: PowerProfiles.profile === PowerProfile.PowerSaver ? "Power saver"
                    : PowerProfiles.profile === PowerProfile.Performance ? "Performance" : "Balanced"
                lines: (!root.battery ? [] : root.charging
                       ? [root.battery.timeToFull ? `${duration(root.battery.timeToFull)} until full` : "Charging"]
                       : [root.battery.timeToEmpty ? `${duration(root.battery.timeToEmpty)} remaining` : "Discharging"])
                       .concat([`Mode: ${mode}`, "click: change power mode"])
            }
        }
    }
}
