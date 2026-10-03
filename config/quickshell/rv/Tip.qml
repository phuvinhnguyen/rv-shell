import QtQuick

// Plain text tooltip body for BarPopup: a bold title and optional lines.
Column {
    property string title: ""
    property var lines: []
    spacing: 3

    Text {
        text: parent.title
        visible: text !== ""
        color: Config.text
        font.family: Config.font
        font.pixelSize: Config.fontSize
        font.bold: true
    }
    Repeater {
        model: parent.lines
        Text {
            required property var modelData
            text: modelData
            color: Config.muted
            font.family: Config.font
            font.pixelSize: Config.fontSize - 1
        }
    }
}
