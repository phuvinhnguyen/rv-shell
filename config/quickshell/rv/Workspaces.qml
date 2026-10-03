import QtQuick
import Quickshell
import Quickshell.Hyprland

// Vertical workspace strip. The active workspace of this screen is an accent
// pill that slides between slots; occupied workspaces show their number,
// empty ones a dot. Scroll to move through workspaces.
Item {
    id: root

    required property var screen
    readonly property var monitor: Hyprland.monitorFor(screen)
    readonly property int activeId: monitor && monitor.activeWorkspace ? monitor.activeWorkspace.id : 1
    readonly property int slot: Config.barWidth - 16
    readonly property int gap: 4

    // Always show the configured count, more when higher ones are in use.
    readonly property int count: {
        let highest = Config.get("bar", "workspaces", 5);
        for (const ws of Hyprland.workspaces.values)
            if (ws.id > highest && ws.id <= 30) highest = ws.id;
        return Math.max(highest, activeId > 0 ? activeId : 1);
    }

    function workspace(id) {
        for (const ws of Hyprland.workspaces.values)
            if (ws.id === id) return ws;
        return null;
    }
    function go(id) { Hyprland.dispatch(`hl.dsp.focus({ workspace = ${id} })`); }

    implicitWidth: slot
    implicitHeight: count * (slot + gap) - gap

    Rectangle {
        id: pill
        width: root.slot
        height: root.slot
        radius: Math.min(Config.rounding, width / 2)
        color: Config.accent
        visible: root.activeId > 0 && root.activeId <= root.count
        y: (root.activeId - 1) * (root.slot + root.gap)
        Behavior on y { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
    }

    Repeater {
        model: root.count

        Item {
            id: cell
            required property int index
            readonly property int wsId: index + 1
            readonly property var ws: root.workspace(wsId)
            readonly property int windows: ws ? ws.toplevels.values.length : 0
            readonly property bool current: wsId === root.activeId
            readonly property bool urgent: ws ? ws.urgent : false
            // Shown on another monitor right now.
            readonly property bool elsewhere: ws !== null && ws.active && !current && ws.monitor !== root.monitor

            y: index * (root.slot + root.gap)
            width: root.slot
            height: root.slot

            Rectangle {
                anchors.fill: parent
                radius: pill.radius
                color: hover.hovered && !cell.current ? Config.hover : "transparent"
                border.width: cell.elsewhere ? 1 : 0
                border.color: Config.alpha(Config.accent, 0.5)
            }

            Text {
                anchors.centerIn: parent
                visible: cell.windows > 0 || cell.current
                text: cell.wsId
                color: cell.current ? Config.bg : (cell.urgent ? Config.bad : Config.text)
                font.family: Config.font
                font.pixelSize: Config.fontSize
                font.bold: true
            }
            Rectangle {
                anchors.centerIn: parent
                visible: cell.windows === 0 && !cell.current
                width: 5
                height: 5
                radius: 2.5
                color: Config.alpha(Config.muted, 0.7)
            }

            HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
            TapHandler { onTapped: root.go(cell.wsId) }
        }
    }

    WheelHandler {
        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
        onWheel: event => {
            const step = event.angleDelta.y > 0 ? -1 : 1;
            const next = root.activeId + step;
            if (next >= 1) root.go(next);
        }
    }
}
