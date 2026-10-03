import QtQuick
import QtQuick.Layouts
import Quickshell.Widgets

// Shown only while an MPRIS player exists. Click play/pause, scroll to skip;
// hovering shows the track with controls.
BarButton {
    id: root

    readonly property var player: MediaState.player
    visible: player !== null && Config.get("bar", "showMedia", true)
    icon: player && player.isPlaying ? Icons.pause : Icons.music
    iconColor: player && player.isPlaying ? Config.accent : Config.muted
    onHoveredChanged: popup.hover(hovered)
    onClicked: button => button === Qt.RightButton ? MediaState.next() : MediaState.toggle()
    onScrolled: delta => delta > 0 ? MediaState.previous() : MediaState.next()

    BarPopup {
        id: popup
        anchorItem: root

        RowLayout {
            spacing: 12
            ClippingRectangle {
                visible: root.player && root.player.trackArtUrl !== ""
                Layout.preferredWidth: 56
                Layout.preferredHeight: 56
                radius: Config.rounding - 4
                color: Config.surface
                Image {
                    anchors.fill: parent
                    source: root.player ? root.player.trackArtUrl : ""
                    sourceSize: Qt.size(112, 112)
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    cache: false
                }
            }
            ColumnLayout {
                spacing: 2
                Text {
                    Layout.maximumWidth: 220
                    elide: Text.ElideRight
                    text: root.player ? (root.player.trackTitle || root.player.identity) : ""
                    color: Config.text
                    font.family: Config.font
                    font.pixelSize: Config.fontSize
                    font.bold: true
                }
                Text {
                    Layout.maximumWidth: 220
                    elide: Text.ElideRight
                    text: root.player ? (root.player.trackArtist || root.player.identity) : ""
                    color: Config.muted
                    font.family: Config.font
                    font.pixelSize: Config.fontSize - 1
                }
                RowLayout {
                    spacing: 14
                    Repeater {
                        model: [
                            { icon: Icons.previous, run: () => MediaState.previous() },
                            { icon: root.player && root.player.isPlaying ? Icons.pause : Icons.play, run: () => MediaState.toggle() },
                            { icon: Icons.next, run: () => MediaState.next() },
                        ]
                        Text {
                            required property var modelData
                            text: modelData.icon
                            color: control.containsMouse ? Config.accent : Config.text
                            font.family: Config.font
                            font.pixelSize: Config.fontSize + 4
                            MouseArea {
                                id: control
                                anchors.fill: parent
                                anchors.margins: -4
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: parent.modelData.run()
                            }
                        }
                    }
                }
            }
        }
    }
}
