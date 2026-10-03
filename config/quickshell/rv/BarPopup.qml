import QtQuick
import Quickshell
import Quickshell.Hyprland

// A card that opens to the right of a bar item. Hover popups (tooltips,
// previews) close when the pointer leaves the item; interactive popups
// (`interactive: true`) stay until a click lands outside them.
//
// The window only exists while it is shown: content is created on open and
// destroyed on close, so idle popups cost no memory.
Item {
    id: root

    required property Item anchorItem
    property bool interactive: false
    property bool open: false
    property int padding: 12
    default property Component content

    // Hover popups: open after a short delay, close as soon as the pointer
    // leaves both the item and the popup.
    property bool hoverOpen: false
    property bool popupHovered: false
    Timer {
        id: showDelay
        interval: 350
        onTriggered: root.hoverOpen = true
    }
    Timer {
        id: hideDelay
        interval: 120
        onTriggered: if (!root.popupHovered) root.hoverOpen = false
    }
    function hover(on) {
        if (on) { hideDelay.stop(); showDelay.restart(); }
        else { showDelay.stop(); hideDelay.restart(); }
    }

    readonly property bool shown: open || (!interactive && hoverOpen)

    LazyLoader {
        active: root.shown

        PopupWindow {
            id: popup
            visible: true
            color: "transparent"
            anchor.item: root.anchorItem
            anchor.rect.x: root.anchorItem.width + 14
            anchor.rect.y: root.anchorItem.height / 2
            anchor.rect.width: 1
            anchor.rect.height: 1
            anchor.edges: Edges.Left
            anchor.gravity: Edges.Right
            implicitWidth: card.implicitWidth
            implicitHeight: card.implicitHeight

            HyprlandFocusGrab {
                active: root.interactive
                windows: [popup]
                onCleared: root.open = false
            }

            Rectangle {
                id: card
                implicitWidth: loader.implicitWidth + root.padding * 2
                implicitHeight: loader.implicitHeight + root.padding * 2
                radius: Config.rounding
                color: Config.panel
                border.color: Config.line
                border.width: 1
                opacity: 0
                x: -6
                Component.onCompleted: { opacity = 1; x = 0; }
                Behavior on opacity { NumberAnimation { duration: 140 } }
                Behavior on x { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }

                HoverHandler {
                    onHoveredChanged: {
                        root.popupHovered = hovered;
                        if (!hovered && !root.interactive) root.hover(false);
                    }
                }

                Loader {
                    id: loader
                    x: root.padding
                    y: root.padding
                    sourceComponent: root.content
                }
            }
        }
    }
}
