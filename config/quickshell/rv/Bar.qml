import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland

// The left bar: launcher, workspaces, clock, then media, stats, tray,
// status, notifications and power at the bottom.
PanelWindow {
    id: bar

    required property var modelData
    screen: modelData

    readonly property int margin: 6
    property alias powerPopup: powerPopup
    property alias notificationPopup: notificationPopup

    anchors { left: true; top: true; bottom: true }
    implicitWidth: Config.barWidth + margin
    exclusiveZone: Config.barVisible ? Config.barWidth + margin : 0
    visible: Config.barVisible
    color: "transparent"
    WlrLayershell.namespace: "rv-bar"
    WlrLayershell.layer: WlrLayer.Top

    Rectangle {
        id: body
        anchors { fill: parent; leftMargin: bar.margin; topMargin: bar.margin; bottomMargin: bar.margin }
        radius: Config.rounding + 2
        color: Config.panel
        border.width: 1
        border.color: Config.line

        // ---- Top ---------------------------------------------------------------
        ColumnLayout {
            id: top
            anchors { top: parent.top; horizontalCenter: parent.horizontalCenter; topMargin: 6 }
            spacing: 8

            BarButton {
                id: launcherButton
                Layout.alignment: Qt.AlignHCenter
                icon: Icons.debian
                iconColor: Config.accent
                iconScale: 1.45
                active: Launcher.open
                onHoveredChanged: launcherTip.hover(hovered)
                onClicked: button => { launcherTip.hover(false); Launcher.toggle(button === Qt.RightButton ? "tools" : "apps"); }
                BarPopup {
                    id: launcherTip
                    anchorItem: launcherButton
                    Tip { title: "Launcher"; lines: ["click: apps · right: utilities", "Super+A · Super+V clipboard"] }
                }
            }

            Workspaces {
                Layout.alignment: Qt.AlignHCenter
                screen: bar.modelData
            }
        }

        // ---- Middle ------------------------------------------------------------
        Clock {
            anchors.centerIn: parent
            // Keep clear of the top and bottom groups on short screens.
            anchors.verticalCenterOffset: {
                const free = body.height - top.height - bottom.height - 24;
                return free < height ? (top.height - bottom.height) / 2 : 0;
            }
        }

        // ---- Bottom ------------------------------------------------------------
        ColumnLayout {
            id: bottom
            anchors { bottom: parent.bottom; horizontalCenter: parent.horizontalCenter; bottomMargin: 6 }
            spacing: 6

            Media { Layout.alignment: Qt.AlignHCenter }

            Item {
                id: stats
                visible: Config.get("bar", "showStats", true)
                Layout.alignment: Qt.AlignHCenter
                implicitWidth: Config.barWidth - 12
                implicitHeight: statsColumn.implicitHeight + 8
                Component.onCompleted: SystemStats.consumers++
                Component.onDestruction: SystemStats.consumers--

                Rectangle {
                    anchors.fill: parent
                    radius: Config.rounding
                    color: statsArea.containsMouse ? Config.hover : "transparent"
                }
                Column {
                    id: statsColumn
                    anchors.centerIn: parent
                    spacing: 5
                    Ring { value: SystemStats.cpu }
                    Ring { value: SystemStats.memory }
                }
                MouseArea {
                    id: statsArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onContainsMouseChanged: statsTip.hover(containsMouse)
                    onClicked: { statsTip.hover(false); Config.run(["app", "monitor"]); }
                }
                BarPopup {
                    id: statsTip
                    anchorItem: stats
                    Tip {
                        title: "System"
                        lines: [
                            `CPU      ${Math.round(SystemStats.cpu * 100)}%` + (SystemStats.temperature ? `  ${Math.round(SystemStats.temperature)}°C` : ""),
                            `Memory   ${SystemStats.memUsedGiB.toFixed(1)} / ${SystemStats.memTotalGiB.toFixed(1)} GiB`,
                            `Swap     ${SystemStats.swapUsedGiB.toFixed(1)} GiB`,
                            `Uptime   ${SystemStats.uptime}`,
                            "click: system monitor",
                        ]
                    }
                }
            }

            Rectangle {
                visible: tray.visible && tray.implicitHeight > 0
                Layout.alignment: Qt.AlignHCenter
                width: 16; height: 1
                color: Config.line
            }
            Tray {
                id: tray
                visible: Config.get("bar", "showTray", true)
                Layout.alignment: Qt.AlignHCenter
            }

            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                width: 16; height: 1
                color: Config.line
            }
            Status { Layout.alignment: Qt.AlignHCenter }

            BarButton {
                id: bell
                Layout.alignment: Qt.AlignHCenter
                icon: Notifs.dnd ? Icons.bellOff : Notifs.history.length ? Icons.bell : Icons.bellOutline
                iconColor: Notifs.dnd ? Config.muted : Config.text
                badge: Notifs.history.length > 0 ? String(Math.min(99, Notifs.history.length)) : ""
                active: notificationPopup.open
                onClicked: button => {
                    if (button === Qt.RightButton) Notifs.setDnd(!Notifs.dnd);
                    else if (button === Qt.MiddleButton) Notifs.clear();
                    else notificationPopup.open = !notificationPopup.open;
                }
                BarPopup {
                    id: notificationPopup
                    anchorItem: bell
                    interactive: true
                    NotificationList {}
                }
            }

            BarButton {
                id: settingsButton
                Layout.alignment: Qt.AlignHCenter
                icon: Icons.cog
                onHoveredChanged: settingsTip.hover(hovered)
                onClicked: { settingsTip.hover(false); Config.run(["open", "settings"]); }
                BarPopup {
                    id: settingsTip
                    anchorItem: settingsButton
                    Tip { title: "Settings"; lines: ["Super+N"] }
                }
            }

            BarButton {
                id: powerButton
                Layout.alignment: Qt.AlignHCenter
                icon: Icons.power
                iconColor: powerPopup.open ? Config.bad : Config.text
                active: powerPopup.open
                onClicked: powerPopup.open = !powerPopup.open
                BarPopup {
                    id: powerPopup
                    anchorItem: powerButton
                    interactive: true
                    padding: 6
                    PowerMenu { onDone: powerPopup.open = false }
                }
            }
        }
    }
}
