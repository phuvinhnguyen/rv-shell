import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland
import Quickshell.Services.Pipewire

// Volume / brightness indicator beside the bar. Volume changes are picked up
// from PipeWire; brightness is announced by the key binding (`rv osd`).
Scope {
    id: root

    property string kind: "volume"
    property real value: 0
    property bool muted: false
    property bool shown: false
    property bool ready: false

    readonly property var sink: Pipewire.defaultAudioSink
    PwObjectTracker { objects: [root.sink] }

    function show(what) {
        if (what === "brightness") { brightness.running = true; return; }
        if (!sink || !sink.audio) return;
        kind = "volume";
        value = sink.audio.volume;
        muted = sink.audio.muted;
        shown = true;
        hide.restart();
    }

    // Ignore the burst of change signals while PipeWire objects bind at start.
    Timer { interval: 2000; running: true; onTriggered: root.ready = true }
    Timer { id: hide; interval: 1400; onTriggered: root.shown = false }

    Connections {
        target: root.sink ? root.sink.audio : null
        function onVolumeChanged() { if (root.ready) root.show("volume"); }
        function onMutedChanged() { if (root.ready) root.show("volume"); }
    }

    Process {
        id: brightness
        command: ["brightnessctl", "-m"]
        stdout: StdioCollector {
            onStreamFinished: {
                const f = text.trim().split(",");
                if (f.length < 5) return;
                root.kind = "brightness";
                root.value = Number(f[2]) / Number(f[4]);
                root.muted = false;
                root.shown = true;
                hide.restart();
            }
        }
    }

    LazyLoader {
        active: root.shown

        PanelWindow {
            screen: Quickshell.screens.find(s => s.name === (Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : "")) || Quickshell.screens[0]
            anchors.left: true
            margins.left: 8
            exclusiveZone: 0
            WlrLayershell.namespace: "rv-osd"
            WlrLayershell.layer: WlrLayer.Overlay
            color: "transparent"
            implicitWidth: 52
            implicitHeight: 220
            mask: Region {}

            Rectangle {
                anchors.fill: parent
                radius: Config.rounding + 2
                color: Config.panel
                border.width: 1
                border.color: Config.line

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 10

                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: Math.round(root.value * 100)
                        color: Config.text
                        font.family: Config.font
                        font.pixelSize: Config.fontSize - 1
                        font.bold: true
                    }
                    Rectangle {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.fillHeight: true
                        width: 6
                        radius: 3
                        color: Config.alpha(Config.text, 0.1)
                        Rectangle {
                            anchors.bottom: parent.bottom
                            width: parent.width
                            radius: 3
                            height: parent.height * Math.min(1, root.value)
                            color: root.muted ? Config.muted : Config.accent
                            Behavior on height { NumberAnimation { duration: 120 } }
                        }
                    }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: root.kind === "brightness" ? Icons.brightness
                            : root.muted ? Icons.volumeOff : root.value > 0.5 ? Icons.volumeHigh : Icons.volumeLow
                        color: Config.text
                        font.family: Config.font
                        font.pixelSize: Config.fontSize + 4
                    }
                }
            }
        }
    }
}
