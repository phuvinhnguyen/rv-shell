import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Networking
import Quickshell.Services.UPower

// Lock surface: a large clock, then a fastfetch-style summary (logo + system
// info). There is no password field: typing is read as raw keys (so no input
// method interferes), each key sparks a star that fades out, and the
// "Password" line only says whether something has been typed.
// State and authentication live in Session, shared by every screen.
Item {
    id: root

    SystemClock { id: clock; precision: SystemClock.Seconds }

    // Stars and text use the background's opposite colour.
    readonly property color ink: Qt.rgba(1 - Config.bg.r, 1 - Config.bg.g, 1 - Config.bg.b, 1)

    Component.onCompleted: SystemStats.consumers++
    Component.onDestruction: SystemStats.consumers--

    // ---- Background -----------------------------------------------------------
    Rectangle { anchors.fill: parent; color: Config.bg }
    Image {
        anchors.fill: parent
        visible: source !== ""
        source: Config.get("wallpaper", "path", "") ? "file://" + Config.get("wallpaper", "path", "").replace(/^~/, Quickshell.env("HOME")) : ""
        fillMode: Image.PreserveAspectCrop
        sourceSize: Qt.size(root.width, root.height)
        asynchronous: true
        cache: false
        opacity: 0.25
    }

    // ---- Keyboard: a plain item, not a text field ---------------------------------
    // Text fields switch on the input method (fcitx5 etc.); a bare key handler
    // gets the keyboard layout's characters directly.
    Item {
        id: keys
        anchors.fill: parent
        focus: true
        Component.onCompleted: forceActiveFocus()
        Keys.onPressed: event => { Session.typeKey(event); event.accepted = true; }
    }
    MouseArea { anchors.fill: parent; onClicked: keys.forceActiveFocus() }

    // ---- Stars ------------------------------------------------------------------
    Connections {
        target: Session
        function onTyped(kind) {
            if (kind === 0) {
                star.createObject(sky, { x: Math.random() * (root.width - 40) + 20, y: Math.random() * (root.height - 40) + 20 });
            } else if (kind === 3) {
                shake.restart();
            }
        }
    }
    Item { id: sky; anchors.fill: parent }
    Component {
        id: star
        Text {
            id: spark
            text: "✦"
            color: root.ink
            font.pixelSize: 10 + Math.random() * 14
            rotation: Math.random() * 90
            scale: 0.4
            opacity: 1
            ParallelAnimation {
                running: true
                NumberAnimation { target: spark; property: "scale"; to: 1.4; duration: 900; easing.type: Easing.OutCubic }
                NumberAnimation { target: spark; property: "opacity"; to: 0; duration: 900; easing.type: Easing.InQuad }
                NumberAnimation { target: spark; property: "rotation"; to: spark.rotation + 45; duration: 900 }
                onFinished: spark.destroy()
            }
        }
    }

    // ---- System facts (read once per lock) ------------------------------------------
    property string osName: "Linux"
    property string kernel: ""
    property string host: ""
    property string cpuModel: ""
    FileView { path: "/etc/os-release"; onLoaded: { const m = text().match(/^PRETTY_NAME="?([^"\n]*)/m); if (m) root.osName = m[1]; } }
    FileView { path: "/proc/sys/kernel/osrelease"; onLoaded: root.kernel = text().trim() }
    FileView { path: "/proc/sys/kernel/hostname"; onLoaded: root.host = text().trim() }
    FileView {
        path: "/proc/cpuinfo"
        onLoaded: {
            const m = text().match(/^model name\s*:\s*(.*)$/m);
            if (m) root.cpuModel = m[1].replace(/\s+with Radeon.*| CPU| Processor|\(R\)|\(TM\)/g, "").replace(/\s+/g, " ").trim();
        }
    }

    function values(model) { return model ? (model.values !== undefined ? model.values : model) : []; }
    readonly property string network: {
        for (const d of values(Networking.devices)) {
            if (d.type === DeviceType.Wired && d.connected) return "Wired";
            if (d.type === DeviceType.Wifi) {
                const n = values(d.networks).find(x => x.connected);
                if (n) return `${n.name} (${Math.round(n.signalStrength * 100)}%)`;
            }
        }
        return "offline";
    }
    readonly property var battery: UPower.displayDevice
    readonly property string power: !battery || !battery.ready || !battery.isLaptopBattery ? "" :
        `${Math.round(battery.percentage * 100)}%` +
        (battery.state === UPowerDeviceState.Charging ? " · charging" :
         battery.state === UPowerDeviceState.FullyCharged ? " · full" : "")

    readonly property string passwordState: Session.checking ? "◌ checking…"
        : Session.error !== "" ? "✕ " + Session.error.toLowerCase()
        : Session.secret === "" ? "○ empty" : "● typed — Enter unlocks"
    readonly property color passwordColour: Session.checking ? Config.warn
        : Session.error !== "" ? Config.bad : Session.secret === "" ? Config.muted : Config.good

    readonly property var facts: [
        ["Password", passwordState, passwordColour],
        ["OS", osName, Config.text],
        ["Host", host, Config.text],
        ["Kernel", kernel, Config.text],
        ["WM", "Hyprland", Config.text],
        ["Uptime", SystemStats.uptime, Config.text],
        ["CPU", cpuModel + (SystemStats.cpu > 0 ? `  ${Math.round(SystemStats.cpu * 100)}%` : "")
                + (SystemStats.temperature ? `  ${Math.round(SystemStats.temperature)}°C` : ""), Config.text],
        ["Memory", `${SystemStats.memUsedGiB.toFixed(1)} / ${SystemStats.memTotalGiB.toFixed(1)} GiB`, Config.text],
        ["Network", network, Config.text],
    ].concat(power ? [["Battery", power, Config.text]] : [])
     .concat(MediaState.player && MediaState.player.trackTitle
             ? [["Playing", MediaState.player.trackTitle + (MediaState.player.trackArtist ? " — " + MediaState.player.trackArtist : ""), Config.text]] : [])
     .concat(Notifs.history.length ? [["Unread", `${Notifs.history.length} notification${Notifs.history.length > 1 ? "s" : ""}`, Config.text]] : [])

    // Debian logo, as drawn by neofetch/fastfetch.
    readonly property string logo: [
        "       _,met$$$$$gg.",
        "    ,g$$$$$$$$$$$$$$$P.",
        "  ,g$$P\"\"       \"\"\"Y$$.\".",
        " ,$$P'              `$$$.",
        "',$$P       ,ggs.     `$$b:",
        "`d$$'     ,$P\"'   .    $$$",
        " $$P      d$'     ,    $$P",
        " $$:      $$.   -    ,d$$'",
        " $$;      Y$b._   _,d$P'",
        " Y$$.    `.`\"Y$$$$P\"'",
        " `$$b      \"-.__",
        "  `Y$$",
        "   `Y$$.",
        "     `$$b.",
        "       `Y$$b.",
        "          `\"Y$b._",
        "              `\"\"\"",
    ].join("\n")

    // ---- Layout -----------------------------------------------------------------------
    ColumnLayout {
        id: content
        anchors.centerIn: parent
        spacing: 28

        SequentialAnimation {
            id: shake
            NumberAnimation { target: content; property: "anchors.horizontalCenterOffset"; to: 18; duration: 50 }
            NumberAnimation { target: content; property: "anchors.horizontalCenterOffset"; to: -18; duration: 80 }
            NumberAnimation { target: content; property: "anchors.horizontalCenterOffset"; to: 10; duration: 70 }
            NumberAnimation { target: content; property: "anchors.horizontalCenterOffset"; to: 0; duration: 60 }
        }

        ColumnLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: 0
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: Qt.formatTime(clock.date, Config.get("bar", "clock24h", true) ? "HH:mm" : "h:mm AP")
                color: Config.text
                font.family: Config.font
                font.pixelSize: 104
                font.bold: true
            }
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: Qt.formatDate(clock.date, "dddd, d MMMM yyyy")
                color: Config.accent
                font.family: Config.font
                font.pixelSize: 20
            }
        }

        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: 36

            Text {
                Layout.alignment: Qt.AlignTop
                text: root.logo
                color: Config.accent
                font.family: Config.font
                font.pixelSize: 13
                lineHeight: 1.05
                textFormat: Text.PlainText
            }

            ColumnLayout {
                Layout.alignment: Qt.AlignTop
                spacing: 3

                Text {
                    text: `<b><font color="${Config.accent}">${Quickshell.env("USER")}</font></b>`
                          + `@<b><font color="${Config.accent}">${root.host}</font></b>`
                    textFormat: Text.StyledText
                    color: Config.text
                    font.family: Config.font
                    font.pixelSize: 16
                }
                Text {
                    text: "─".repeat(Math.max(8, (Quickshell.env("USER") || "").length + root.host.length + 1))
                    color: Config.muted
                    font.family: Config.font
                    font.pixelSize: 16
                }
                Repeater {
                    model: root.facts
                    RowLayout {
                        required property var modelData
                        required property int index
                        spacing: 0
                        Text {
                            Layout.preferredWidth: 96
                            text: parent.modelData[0]
                            color: Config.accent
                            font.family: Config.font
                            font.pixelSize: 15
                            font.bold: true
                        }
                        Text {
                            Layout.maximumWidth: 460
                            elide: Text.ElideRight
                            text: parent.modelData[1]
                            color: parent.modelData[2]
                            font.family: Config.font
                            font.pixelSize: 15
                            font.bold: parent.index === 0
                        }
                    }
                }
                // Colour blocks, as fastfetch ends with.
                Row {
                    Layout.topMargin: 10
                    spacing: 0
                    Repeater {
                        model: [Config.surface, Config.bad, Config.good, Config.warn, Config.accent, Config.muted, Config.text, root.ink]
                        Rectangle { required property color modelData; width: 26; height: 16; color: modelData }
                    }
                }
            }
        }
    }

    Text {
        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 28 }
        text: Session.secret === "" ? "type your password · Enter unlocks · Esc clears" : "Enter unlocks · Esc clears"
        color: Config.alpha(Config.muted, 0.8)
        font.family: Config.font
        font.pixelSize: 12
    }
}
