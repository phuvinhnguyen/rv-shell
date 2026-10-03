import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland

// On-screen notifications in the top-right corner of the focused screen.
// The window exists only while there is something to show.
LazyLoader {
    id: root
    active: Notifs.toasts.length > 0

    PanelWindow {
        screen: Quickshell.screens.find(s => s.name === (Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : "")) || Quickshell.screens[0]
        anchors { top: true; right: true }
        margins { top: 8; right: 8 }
        exclusiveZone: 0
        WlrLayershell.namespace: "rv-notifications"
        WlrLayershell.layer: WlrLayer.Overlay
        color: "transparent"
        implicitWidth: 340
        implicitHeight: column.implicitHeight

        Column {
            id: column
            width: parent.width
            spacing: 8

            Repeater {
                model: Notifs.toasts

                NotificationCard {
                    id: card
                    required property var modelData
                    notification: modelData
                    toast: true
                    width: column.width
                    onClosed: Notifs.dropToast(modelData)

                    Connections {
                        target: card.modelData
                        function onClosed() { Notifs.dropToast(card.modelData); }
                    }
                    Timer {
                        // Pause while the pointer rests on the toast.
                        interval: Notifs.timeoutFor(card.modelData)
                        running: interval > 0 && !hover.hovered
                        onTriggered: Notifs.dropToast(card.modelData)
                    }
                    HoverHandler { id: hover }
                }
            }
        }
    }
}
