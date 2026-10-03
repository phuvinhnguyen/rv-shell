import QtQuick
import Quickshell
import Quickshell.Wayland

// Optional wallpaper (settings → Wallpaper). With no path set nothing is
// created and Hyprland's background colour shows instead: zero memory.
// The image is decoded at the screen's size, never at its file size.
Variants {
    model: Config.get("wallpaper", "path", "") !== "" ? Quickshell.screens : []

    PanelWindow {
        required property var modelData
        screen: modelData
        anchors { left: true; right: true; top: true; bottom: true }
        exclusiveZone: -1
        WlrLayershell.layer: WlrLayer.Background
        WlrLayershell.namespace: "rv-wallpaper"
        color: Config.bg

        Image {
            anchors.fill: parent
            source: "file://" + Config.get("wallpaper", "path", "").replace(/^~/, Quickshell.env("HOME"))
            fillMode: Config.get("wallpaper", "fill", "crop") === "fit" ? Image.PreserveAspectFit : Image.PreserveAspectCrop
            sourceSize: Qt.size(parent.width * modelData.devicePixelRatio, parent.height * modelData.devicePixelRatio)
            asynchronous: true
            cache: false
            smooth: true
        }
    }
}
