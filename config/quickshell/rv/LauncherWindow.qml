import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland
import Quickshell.Widgets

// The launcher panel. Created on open and destroyed on close.
LazyLoader {
    active: Launcher.open

    PanelWindow {
        id: win
        screen: Quickshell.screens.find(s => s.name === (Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : "")) || Quickshell.screens[0]
        anchors.top: true
        margins.top: Math.round(screen.height * 0.16)
        exclusiveZone: 0
        implicitWidth: 560
        implicitHeight: card.implicitHeight
        color: "transparent"
        WlrLayershell.namespace: "rv-launcher"
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

        HyprlandFocusGrab {
            active: true
            windows: [win]
            onCleared: Launcher.open = false
        }

        Rectangle {
            id: card
            width: parent.width
            implicitHeight: column.implicitHeight + 24
            radius: Config.rounding + 4
            color: Config.panel
            border.width: 1
            border.color: Config.line

            ColumnLayout {
                id: column
                x: 12; y: 12
                width: parent.width - 24
                spacing: 10

                // Search field.
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 44
                    radius: Config.rounding
                    color: Config.alpha(Config.surface, 0.8)

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 14
                        anchors.rightMargin: 14
                        spacing: 10
                        Text {
                            text: Icons.search
                            color: Config.accent
                            font.family: Config.font
                            font.pixelSize: 18
                        }
                        TextInput {
                            id: input
                            Layout.fillWidth: true
                            color: Config.text
                            font.family: Config.font
                            font.pixelSize: 16
                            focus: true
                            clip: true
                            text: Launcher.query
                            onTextChanged: { Launcher.query = text; Launcher.selected = 0; }
                            Component.onCompleted: forceActiveFocus()

                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                visible: input.text === ""
                                text: ({ apps: "Search apps and tools · = calc", tools: "Search utilities…",
                                         clipboard: "Search clipboard…", run: "Command to run…",
                                         web: "Search the web, then Enter…" })[Launcher.mode]
                                color: Config.muted
                                font: input.font
                            }

                            Keys.onPressed: event => {
                                const n = Launcher.results.length;
                                const ctrl = event.modifiers & Qt.ControlModifier;
                                if (event.key === Qt.Key_Escape) { Launcher.open = false; }
                                else if (event.key === Qt.Key_Down || (ctrl && event.key === Qt.Key_J) || (ctrl && event.key === Qt.Key_N))
                                    Launcher.selected = Math.min(n - 1, Launcher.selected + 1);
                                else if (event.key === Qt.Key_Up || (ctrl && event.key === Qt.Key_K) || (ctrl && event.key === Qt.Key_P))
                                    Launcher.selected = Math.max(0, Launcher.selected - 1);
                                else if (event.key === Qt.Key_PageDown) Launcher.selected = Math.min(n - 1, Launcher.selected + 8);
                                else if (event.key === Qt.Key_PageUp) Launcher.selected = Math.max(0, Launcher.selected - 8);
                                else if (event.key === Qt.Key_Tab) Launcher.cycle(1);
                                else if (event.key === Qt.Key_Backtab) Launcher.cycle(-1);
                                else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter)
                                    Launcher.activate(Launcher.selected, event.modifiers & Qt.ShiftModifier);
                                else if (event.key === Qt.Key_Delete && (event.modifiers & Qt.ShiftModifier))
                                    Launcher.remove(Launcher.selected);
                                else return;
                                event.accepted = true;
                            }
                        }
                    }
                }

                // Mode chips.
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    Repeater {
                        model: [
                            { id: "apps", label: "Apps", glyph: Icons.apps },
                            { id: "tools", label: "Tools ;", glyph: Icons.tools },
                            { id: "clipboard", label: "Clipboard :", glyph: Icons.clipboard },
                            { id: "run", label: "Run >", glyph: Icons.terminal },
                            { id: "web", label: "Web ?", glyph: Icons.web },
                        ]
                        Rectangle {
                            required property var modelData
                            readonly property bool current: Launcher.effectiveMode === modelData.id
                            implicitWidth: chip.implicitWidth + 18
                            implicitHeight: 26
                            radius: 13
                            color: current ? Config.alpha(Config.accent, 0.22) : chipArea.containsMouse ? Config.hover : "transparent"
                            Row {
                                id: chip
                                anchors.centerIn: parent
                                spacing: 6
                                Text { text: parent.parent.modelData.glyph; color: parent.parent.current ? Config.accent : Config.muted; font.family: Config.font; font.pixelSize: Config.fontSize }
                                Text { text: parent.parent.modelData.label; color: parent.parent.current ? Config.text : Config.muted; font.family: Config.font; font.pixelSize: Config.fontSize - 2 }
                            }
                            MouseArea { id: chipArea; anchors.fill: parent; hoverEnabled: true; onClicked: { Launcher.query = Launcher.text; Launcher.show(parent.modelData.id, true); input.forceActiveFocus(); } }
                        }
                    }
                }

                // Results.
                ListView {
                    id: list
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(contentHeight, 9 * 48)
                    visible: count > 0
                    clip: true
                    model: Launcher.results
                    currentIndex: Launcher.selected
                    highlightMoveDuration: 0
                    boundsBehavior: Flickable.StopAtBounds
                    onCurrentIndexChanged: positionViewAtIndex(currentIndex, ListView.Contain)

                    delegate: Rectangle {
                        id: row
                        required property var modelData
                        required property int index
                        readonly property bool current: index === Launcher.selected
                        readonly property bool tall: modelData.kind === "answer"
                        width: list.width
                        height: tall ? Math.max(48, rowColumn.implicitHeight + 16) : 48
                        radius: Config.rounding
                        color: current ? Config.alpha(Config.accent, 0.16) : rowArea.containsMouse ? Config.hover : "transparent"

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 12
                            anchors.rightMargin: 12
                            spacing: 12

                            Item {
                                Layout.preferredWidth: 28
                                Layout.preferredHeight: 28
                                IconImage {
                                    anchors.fill: parent
                                    implicitSize: 28
                                    visible: row.modelData.kind === "app"
                                    source: row.modelData.kind === "app" ? Quickshell.iconPath(row.modelData.icon || "", "application-x-executable") : ""
                                    asynchronous: true
                                }
                                Text {
                                    anchors.centerIn: parent
                                    visible: row.modelData.kind !== "app"
                                    text: row.modelData.glyph || ""
                                    color: row.current ? Config.accent : Config.text
                                    font.family: Config.font
                                    font.pixelSize: 20
                                }
                            }
                            ColumnLayout {
                                id: rowColumn
                                Layout.fillWidth: true
                                spacing: 0
                                Text {
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                    maximumLineCount: 1
                                    text: row.modelData.title.replace(/\s+/g, " ")
                                    color: Config.text
                                    font.family: Config.font
                                    font.pixelSize: Config.fontSize + 1
                                    font.bold: row.current
                                }
                                Text {
                                    Layout.fillWidth: true
                                    visible: text !== ""
                                    elide: Text.ElideRight
                                    wrapMode: row.tall ? Text.Wrap : Text.NoWrap
                                    maximumLineCount: row.tall ? 5 : 1
                                    text: row.modelData.subtitle || ""
                                    color: row.tall ? Config.text : Config.muted
                                    font.family: Config.font
                                    font.pixelSize: Config.fontSize - 2
                                }
                                Text {
                                    visible: row.tall && (row.modelData.host || "") !== ""
                                    text: row.modelData.host || ""
                                    color: Config.accent
                                    font.family: Config.font
                                    font.pixelSize: Config.fontSize - 3
                                }
                            }
                            Text {
                                visible: row.current
                                text: row.modelData.kind === "clip" ? "⏎ copy  ⇧Del delete"
                                    : row.modelData.kind === "url" || row.modelData.kind === "answer" ? "⏎ open"
                                    : row.modelData.kind === "websearch" ? "⏎ search" : "⏎"
                                color: Config.muted
                                font.family: Config.font
                                font.pixelSize: Config.fontSize - 2
                            }
                        }
                        MouseArea {
                            id: rowArea
                            anchors.fill: parent
                            hoverEnabled: true
                            onClicked: Launcher.activate(row.index, false)
                        }
                    }
                }

                Text {
                    visible: list.count === 0
                    Layout.alignment: Qt.AlignHCenter
                    Layout.topMargin: 6
                    Layout.bottomMargin: 6
                    text: Launcher.effectiveMode === "clipboard" ? "Clipboard history is empty"
                        : Launcher.effectiveMode === "calc" ? "Type an expression, e.g. =2^10/3"
                        : Launcher.effectiveMode === "web" ? "Type what to look up, then Enter"
                        : "No matches"
                    color: Config.muted
                    font.family: Config.font
                    font.pixelSize: Config.fontSize
                }
            }
        }
    }
}
