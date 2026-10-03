import QtQuick
import Quickshell
import Quickshell.Services.SystemTray
import Quickshell.Widgets

// System tray, stacked vertically. Left click activates, right click opens
// the item's menu (drawn here, so the shell needs no QtWidgets), middle
// click is the secondary action, scrolling is passed to the item.
// More than `limit` items fold behind a chevron.
Column {
    id: root

    property int limit: 4
    property bool expanded: false
    readonly property var items: SystemTray.items.values
    spacing: 2

    Repeater {
        model: root.expanded ? root.items : root.items.slice(0, root.limit)

        Item {
            id: cell
            required property var modelData
            width: Config.barWidth - 12
            height: width - 8

            Rectangle {
                anchors.fill: parent
                radius: Config.rounding
                color: area.containsMouse || menu.open ? Config.hover : "transparent"
            }
            IconImage {
                anchors.centerIn: parent
                implicitSize: 18
                source: {
                    const icon = cell.modelData.icon;
                    // Some apps hand over a path query; strip it to a themed name.
                    if (icon.includes("?path=")) {
                        const [name, path] = icon.split("?path=");
                        return `file://${path}/${name.slice(name.lastIndexOf("/") + 1)}`;
                    }
                    return icon;
                }
            }
            MouseArea {
                id: area
                anchors.fill: parent
                hoverEnabled: true
                acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
                cursorShape: Qt.PointingHandCursor
                onContainsMouseChanged: if (!menu.open) tip.hover(containsMouse)
                onClicked: event => {
                    tip.hover(false);
                    const item = cell.modelData;
                    if (event.button === Qt.MiddleButton) item.secondaryActivate();
                    else if (event.button === Qt.RightButton || item.onlyMenu) { if (item.hasMenu) menu.open = true; }
                    else item.activate();
                }
                onWheel: event => cell.modelData.scroll(event.angleDelta.y, false)
            }
            BarPopup {
                id: tip
                anchorItem: cell
                Tip { title: cell.modelData.tooltipTitle || cell.modelData.title || cell.modelData.id }
            }
            BarPopup {
                id: menu
                anchorItem: cell
                interactive: true
                padding: 6
                TrayMenu {
                    handle: cell.modelData.menu
                    onDone: menu.open = false
                }
            }
        }
    }

    BarButton {
        visible: root.items.length > root.limit
        icon: root.expanded ? Icons.chevronUp : Icons.chevronDown
        iconColor: Config.muted
        iconScale: 1
        implicitHeight: 20
        onClicked: root.expanded = !root.expanded
    }
}
