import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Widgets

// A tray item's DBus menu rendered as plain QML. Submenus expand in place.
ColumnLayout {
    id: root

    required property var handle
    property int depth: 0
    signal done()

    spacing: 0

    QsMenuOpener {
        id: opener
        menu: root.handle
    }

    Repeater {
        model: opener.children

        Item {
            id: entry
            required property var modelData
            property bool expanded: false
            Layout.fillWidth: true
            Layout.minimumWidth: 200
            implicitWidth: row.implicitWidth + 20
            implicitHeight: modelData.isSeparator ? 9 : (row.implicitHeight + 12 + (sub.item ? sub.item.implicitHeight : 0))

            Rectangle {
                visible: entry.modelData.isSeparator
                anchors.centerIn: parent
                width: parent.width - 12
                height: 1
                color: Config.line
            }

            Rectangle {
                visible: !entry.modelData.isSeparator
                width: parent.width
                height: row.implicitHeight + 12
                radius: Config.rounding - 4
                color: area.containsMouse && entry.modelData.enabled ? Config.hover : "transparent"
            }

            RowLayout {
                id: row
                visible: !entry.modelData.isSeparator
                x: 10 + root.depth * 12
                y: 6
                width: parent.width - 20 - root.depth * 12
                spacing: 8

                Text {
                    // Check boxes and radio items.
                    visible: entry.modelData.buttonType !== QsMenuButtonType.None
                    text: entry.modelData.checkState === Qt.Checked
                          ? (entry.modelData.buttonType === QsMenuButtonType.RadioButton ? "●" : Icons.check) : "○"
                    color: Config.accent
                    font.family: Config.font
                    font.pixelSize: Config.fontSize
                }
                IconImage {
                    visible: entry.modelData.icon !== ""
                    source: entry.modelData.icon
                    implicitSize: 16
                }
                Text {
                    Layout.fillWidth: true
                    text: entry.modelData.text.replace(/_(?!_)/g, "")
                    color: entry.modelData.enabled ? Config.text : Config.muted
                    font.family: Config.font
                    font.pixelSize: Config.fontSize
                }
                Text {
                    visible: entry.modelData.hasChildren
                    text: entry.expanded ? Icons.chevronUp : Icons.chevronDown
                    color: Config.muted
                    font.family: Config.font
                    font.pixelSize: Config.fontSize
                }
            }

            MouseArea {
                id: area
                visible: !entry.modelData.isSeparator
                width: parent.width
                height: row.implicitHeight + 12
                hoverEnabled: true
                onClicked: {
                    if (!entry.modelData.enabled) return;
                    if (entry.modelData.hasChildren) {
                        entry.expanded = !entry.expanded;
                        if (entry.expanded)
                            sub.setSource("TrayMenu.qml", { handle: entry.modelData, depth: root.depth + 1 });
                        else
                            sub.source = "";
                        return;
                    }
                    entry.modelData.triggered();
                    root.done();
                }
            }

            Loader {
                id: sub
                y: row.implicitHeight + 12
                width: parent.width
                onLoaded: item.done.connect(root.done)
            }
        }
    }
}
