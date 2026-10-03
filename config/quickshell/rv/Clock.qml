import QtQuick
import QtQuick.Layouts
import Quickshell

// Stacked clock. Hover shows a month view with upcoming events; click opens
// the calendar app.
Item {
    id: root

    readonly property bool h24: Config.get("bar", "clock24h", true)
    property date now: clock.date

    SystemClock {
        id: clock
        precision: SystemClock.Minutes
    }

    implicitWidth: Config.barWidth - 12
    implicitHeight: column.implicitHeight + 16

    Rectangle {
        anchors.fill: parent
        radius: Config.rounding
        color: mouse.containsMouse ? Config.hover : "transparent"
    }

    ColumnLayout {
        id: column
        anchors.centerIn: parent
        spacing: -2

        Text {
            Layout.alignment: Qt.AlignHCenter
            text: Qt.formatTime(root.now, root.h24 ? "HH" : "hh")
            color: Config.text
            font.family: Config.font
            font.pixelSize: Config.fontSize + 5
            font.bold: true
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: Qt.formatTime(root.now, "mm")
            color: Config.accent
            font.family: Config.font
            font.pixelSize: Config.fontSize + 5
            font.bold: true
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            visible: !root.h24
            text: Qt.formatTime(root.now, "AP").toLowerCase()
            color: Config.muted
            font.family: Config.font
            font.pixelSize: Config.fontSize - 3
        }
        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 6
            Layout.bottomMargin: 4
            visible: Config.get("bar", "showDate", true)
            width: 14; height: 2; radius: 1
            color: Config.line
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            visible: Config.get("bar", "showDate", true)
            text: Qt.formatDate(root.now, "ddd").toUpperCase()
            color: Config.muted
            font.family: Config.font
            font.pixelSize: Config.fontSize - 3
            font.bold: true
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            visible: Config.get("bar", "showDate", true)
            text: Qt.formatDate(root.now, "dd")
            color: Config.text
            font.family: Config.font
            font.pixelSize: Config.fontSize
        }
    }

    // Small dot when something is on today.
    Rectangle {
        visible: CalendarData.on(root.now).length > 0
        anchors { right: parent.right; top: parent.top; margins: 5 }
        width: 5; height: 5; radius: 2.5
        color: Config.warn
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onContainsMouseChanged: popup.hover(containsMouse)
        onClicked: { popup.hover(false); Config.run(["open", "calendar"]); }
    }

    BarPopup {
        id: popup
        anchorItem: root
        padding: 14

        MonthView { now: root.now }
    }
}
