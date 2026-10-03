import QtQuick
import QtQuick.Layouts

// Month grid plus the next week's events. Arrows change month.
ColumnLayout {
    id: root

    property date now: new Date()
    property int offset: 0
    readonly property date month: new Date(now.getFullYear(), now.getMonth() + offset, 1)
    // Monday-first grid start.
    readonly property date first: {
        const lead = (month.getDay() + 6) % 7;
        return new Date(month.getFullYear(), month.getMonth(), 1 - lead);
    }
    readonly property var upcoming: CalendarData.upcoming(8)

    spacing: 8
    width: 7 * 30

    RowLayout {
        Layout.fillWidth: true
        Text {
            Layout.fillWidth: true
            text: Qt.formatDate(root.now, "dddd, d MMMM yyyy")
            color: Config.text
            font.family: Config.font
            font.pixelSize: Config.fontSize
            font.bold: true
        }
    }

    RowLayout {
        Layout.fillWidth: true
        Text {
            text: "‹"
            color: prevArea.containsMouse ? Config.accent : Config.muted
            font.pixelSize: Config.fontSize + 6
            MouseArea { id: prevArea; anchors.fill: parent; anchors.margins: -6; hoverEnabled: true; onClicked: root.offset-- }
        }
        Text {
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            text: Qt.formatDate(root.month, "MMMM yyyy")
            color: Config.accent
            font.family: Config.font
            font.pixelSize: Config.fontSize - 1
            font.bold: true
            MouseArea { anchors.fill: parent; onClicked: root.offset = 0 }
        }
        Text {
            text: "›"
            color: nextArea.containsMouse ? Config.accent : Config.muted
            font.pixelSize: Config.fontSize + 6
            MouseArea { id: nextArea; anchors.fill: parent; anchors.margins: -6; hoverEnabled: true; onClicked: root.offset++ }
        }
    }

    Grid {
        columns: 7
        columnSpacing: 0
        rowSpacing: 2

        Repeater {
            model: ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
            Text {
                required property string modelData
                width: 30
                horizontalAlignment: Text.AlignHCenter
                text: modelData
                color: Config.muted
                font.family: Config.font
                font.pixelSize: Config.fontSize - 3
            }
        }
        Repeater {
            model: 42
            Item {
                id: day
                required property int index
                readonly property date d: new Date(root.first.getFullYear(), root.first.getMonth(), root.first.getDate() + index)
                readonly property bool inMonth: d.getMonth() === root.month.getMonth()
                readonly property bool today: CalendarData.iso(d) === CalendarData.iso(root.now)
                readonly property bool busy: CalendarData.on(d).length > 0
                width: 30
                height: 24

                Rectangle {
                    anchors.centerIn: parent
                    width: 24; height: 22
                    radius: 7
                    color: day.today ? Config.accent : "transparent"
                }
                Text {
                    anchors.centerIn: parent
                    text: day.d.getDate()
                    color: day.today ? Config.bg : day.inMonth ? Config.text : Config.alpha(Config.muted, 0.5)
                    font.family: Config.font
                    font.pixelSize: Config.fontSize - 1
                    font.bold: day.today
                }
                Rectangle {
                    visible: day.busy
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottom: parent.bottom
                    width: 4; height: 4; radius: 2
                    color: day.today ? Config.bg : Config.warn
                }
            }
        }
    }

    Rectangle { Layout.fillWidth: true; height: 1; color: Config.line }

    Text {
        visible: root.upcoming.length === 0
        text: "No events this week"
        color: Config.muted
        font.family: Config.font
        font.pixelSize: Config.fontSize - 1
    }
    Repeater {
        model: root.upcoming.slice(0, 6)
        RowLayout {
            required property var modelData
            Layout.fillWidth: true
            spacing: 8
            Text {
                Layout.preferredWidth: 58
                text: CalendarData.iso(modelData.date) === CalendarData.iso(root.now)
                      ? (modelData.event.time || "today") : Qt.formatDate(modelData.date, "ddd d")
                color: Config.accent
                font.family: Config.font
                font.pixelSize: Config.fontSize - 2
            }
            Text {
                Layout.fillWidth: true
                Layout.maximumWidth: 150
                elide: Text.ElideRight
                text: modelData.event.title || "(untitled)"
                color: Config.text
                font.family: Config.font
                font.pixelSize: Config.fontSize - 1
            }
        }
    }
    Text {
        text: "click: open calendar"
        color: Config.alpha(Config.muted, 0.7)
        font.family: Config.font
        font.pixelSize: Config.fontSize - 3
    }
}
