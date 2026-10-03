import QtQuick
import QtQuick.Layouts

// History list shown from the bar's bell.
ColumnLayout {
    spacing: 8
    width: 340

    RowLayout {
        Layout.fillWidth: true
        Text {
            Layout.fillWidth: true
            text: "Notifications"
            color: Config.text
            font.family: Config.font
            font.pixelSize: Config.fontSize + 1
            font.bold: true
        }
        Repeater {
            model: [
                { label: Notifs.dnd ? "DND on" : "DND off", run: () => Notifs.setDnd(!Notifs.dnd), on: Notifs.dnd },
                { label: "Clear", run: () => Notifs.clear(), on: false },
            ]
            Rectangle {
                required property var modelData
                implicitWidth: label.implicitWidth + 16
                implicitHeight: 24
                radius: 12
                color: modelData.on ? Config.alpha(Config.accent, 0.3) : (area.containsMouse ? Config.hover : Config.alpha(Config.surface, 0.7))
                Text {
                    id: label
                    anchors.centerIn: parent
                    text: parent.modelData.label
                    color: Config.text
                    font.family: Config.font
                    font.pixelSize: Config.fontSize - 2
                }
                MouseArea {
                    id: area
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: parent.modelData.run()
                }
            }
        }
    }

    Text {
        visible: Notifs.history.length === 0
        Layout.topMargin: 10
        Layout.bottomMargin: 10
        Layout.alignment: Qt.AlignHCenter
        text: "All caught up"
        color: Config.muted
        font.family: Config.font
        font.pixelSize: Config.fontSize
    }

    Flickable {
        Layout.fillWidth: true
        Layout.preferredHeight: Math.min(contentHeight, 520)
        visible: Notifs.history.length > 0
        contentHeight: list.implicitHeight
        clip: true

        Column {
            id: list
            width: parent.width
            spacing: 6
            Repeater {
                model: Notifs.history
                NotificationCard {
                    required property var modelData
                    notification: modelData
                    width: list.width
                }
            }
        }
    }
}
