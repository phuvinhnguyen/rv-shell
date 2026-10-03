import QtQuick
import QtQuick.Layouts
import Quickshell.Services.UPower

// Session actions. Destructive ones ask for a second click.
ColumnLayout {
    id: root
    signal done()

    property string armed: ""
    spacing: 2
    width: 210

    Timer { id: disarm; interval: 3000; onTriggered: root.armed = "" }

    // Power mode (power-profiles-daemon): saver · balanced · performance.
    RowLayout {
        Layout.fillWidth: true
        Layout.bottomMargin: 4
        spacing: 4
        Repeater {
            model: [
                { profile: PowerProfile.PowerSaver, label: "Saver" },
                { profile: PowerProfile.Balanced, label: "Balanced" },
                { profile: PowerProfile.Performance, label: "Perform." },
            ]
            Rectangle {
                id: mode
                required property var modelData
                readonly property bool current: PowerProfiles.profile === modelData.profile
                readonly property bool available: modelData.profile !== PowerProfile.Performance || PowerProfiles.hasPerformanceProfile
                Layout.fillWidth: true
                implicitHeight: 30
                radius: Config.rounding - 4
                opacity: available ? 1 : 0.4
                color: current ? Config.alpha(Config.accent, 0.3) : modeArea.containsMouse ? Config.hover : Config.alpha(Config.surface, 0.7)
                Text {
                    anchors.centerIn: parent
                    text: mode.modelData.label
                    color: mode.current ? Config.text : Config.muted
                    font.family: Config.font
                    font.pixelSize: Config.fontSize - 2
                    font.bold: mode.current
                }
                MouseArea {
                    id: modeArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (mode.available) PowerProfiles.profile = mode.modelData.profile
                }
            }
        }
    }

    Repeater {
        model: [
            { id: "lock", icon: Icons.lock, label: "Lock", confirm: false },
            { id: "suspend", icon: Icons.sleep, label: "Suspend", confirm: false },
            { id: "awake", icon: Session.keepAwake ? Icons.coffee : Icons.coffeeOutline,
              label: Session.keepAwake ? "Keep awake: on" : "Keep awake: off", confirm: false },
            { id: "logout", icon: Icons.logout, label: "Log out", confirm: true },
            { id: "reboot", icon: Icons.restart, label: "Restart", confirm: true },
            { id: "poweroff", icon: Icons.power, label: "Shut down", confirm: true },
        ]

        Rectangle {
            id: item
            required property var modelData
            readonly property bool isArmed: root.armed === modelData.id
            Layout.fillWidth: true
            implicitHeight: 34
            radius: Config.rounding - 4
            color: isArmed ? Config.alpha(Config.bad, 0.3) : area.containsMouse ? Config.hover : "transparent"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                spacing: 12
                Text {
                    text: item.modelData.icon
                    color: item.isArmed ? Config.bad : (item.modelData.id === "awake" && Session.keepAwake ? Config.accent : Config.text)
                    font.family: Config.font
                    font.pixelSize: Config.fontSize + 3
                }
                Text {
                    Layout.fillWidth: true
                    text: item.isArmed ? "Click again to " + item.modelData.label.toLowerCase() : item.modelData.label
                    color: item.isArmed ? Config.bad : Config.text
                    font.family: Config.font
                    font.pixelSize: Config.fontSize
                }
            }
            MouseArea {
                id: area
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    const id = item.modelData.id;
                    if (id === "awake") { Session.keepAwake = !Session.keepAwake; return; }
                    if (item.modelData.confirm && root.armed !== id) { root.armed = id; disarm.restart(); return; }
                    root.done();
                    if (id === "lock") Session.lock();
                    else Config.run(["power", id]);
                }
            }
        }
    }
}
