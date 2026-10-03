import QtQuick

// A square bar button: one glyph, a hover wash, an optional badge and a
// tooltip shown by the bar beside it.
Item {
    id: root

    property string icon: ""
    property color iconColor: Config.text
    property real iconScale: 1.25
    property string tip: ""
    property string badge: ""
    property bool active: false
    readonly property bool hovered: mouse.containsMouse

    signal clicked(int button)
    signal scrolled(int delta)

    implicitWidth: Config.barWidth - 12
    implicitHeight: implicitWidth - 4

    Rectangle {
        anchors.fill: parent
        radius: Math.min(Config.rounding, height / 2)
        color: root.active ? Config.alpha(Config.accent, 0.16) : (mouse.containsMouse ? Config.hover : "transparent")
        Behavior on color { ColorAnimation { duration: 120 } }
    }

    Text {
        anchors.centerIn: parent
        text: root.icon
        color: root.iconColor
        font.family: Config.font
        font.pixelSize: Math.round(Config.fontSize * root.iconScale)
        Behavior on color { ColorAnimation { duration: 150 } }
    }

    Rectangle {
        visible: root.badge !== ""
        anchors { right: parent.right; top: parent.top; rightMargin: 2; topMargin: 1 }
        height: 14
        width: Math.max(14, badgeText.implicitWidth + 6)
        radius: 7
        color: Config.accent
        Text {
            id: badgeText
            anchors.centerIn: parent
            text: root.badge
            color: Config.bg
            font.family: Config.font
            font.pixelSize: 9
            font.bold: true
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
        cursorShape: Qt.PointingHandCursor
        onClicked: event => root.clicked(event.button)
        onWheel: event => root.scrolled(event.angleDelta.y)
    }
}
