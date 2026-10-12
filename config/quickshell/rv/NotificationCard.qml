import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Widgets
import Quickshell.Services.Notifications

// One notification. Used by the toasts and by the history list.
// Click to read all of it; expanded, it offers Copy (and Open, if the app
// has a default action).
Rectangle {
    id: root

    required property var notification
    property bool toast: false
    property bool expanded: false
    property bool copied: false
    signal closed()

    readonly property bool critical: notification.urgency === NotificationUrgency.Critical
    readonly property var actions: notification.actions.filter(a => a.identifier !== "default")
    readonly property var defaultAction: notification.actions.find(a => a.identifier === "default") || null

    implicitWidth: 340
    implicitHeight: layout.implicitHeight + 24
    radius: Config.rounding
    color: toast ? Config.panel : (hover.hovered ? Config.alpha(Config.surface, 0.9) : Config.alpha(Config.surface, 0.6))
    border.width: 1
    border.color: critical ? Config.alpha(Config.bad, 0.7) : Config.line

    HoverHandler { id: hover }

    // Plain text of the notification: markup removed, entities decoded.
    function plainText() {
        const body = (notification.body || "")
            .replace(/<br\s*\/?>/gi, "\n").replace(/<[^>]*>/g, "")
            .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"')
            .replace(/&#39;|&apos;/g, "'").replace(/&nbsp;/g, " ").replace(/&amp;/g, "&");
        return [notification.summary || "", body].filter(t => t.trim() !== "").join("\n\n");
    }
    function copy() {
        Quickshell.execDetached(["sh", "-c", 'printf %s "$1" | wl-copy', "sh", plainText()]);
        copied = true;
        copiedTimer.restart();
    }
    Timer { id: copiedTimer; interval: 1500; onTriggered: root.copied = false }

    // Behind the content, so the close and action buttons keep their clicks.
    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: root.expanded = !root.expanded
    }

    ColumnLayout {
        id: layout
        x: 12
        y: 12
        width: parent.width - 24
        spacing: 6

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            ClippingRectangle {
                id: art
                readonly property string src: root.notification.image || (root.notification.appIcon ? Quickshell.iconPath(root.notification.appIcon, true) : "")
                visible: src !== ""
                Layout.preferredWidth: 36
                Layout.preferredHeight: 36
                Layout.alignment: Qt.AlignTop
                radius: 8
                color: "transparent"
                Image {
                    anchors.fill: parent
                    source: art.src
                    sourceSize: Qt.size(72, 72)
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    cache: false
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                        text: root.notification.appName || "Notification"
                        color: root.critical ? Config.bad : Config.accent
                        font.family: Config.font
                        font.pixelSize: Config.fontSize - 2
                        font.bold: true
                    }
                    Text {
                        text: Notifs.ago(root.notification)
                        color: Config.muted
                        font.family: Config.font
                        font.pixelSize: Config.fontSize - 3
                    }
                    Text {
                        text: Icons.close
                        color: closeArea.containsMouse ? Config.bad : Config.muted
                        font.family: Config.font
                        font.pixelSize: Config.fontSize
                        MouseArea {
                            id: closeArea
                            anchors.fill: parent
                            anchors.margins: -4
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.toast ? root.closed() : root.notification.dismiss()
                        }
                    }
                }
                Text {
                    id: summary
                    Layout.fillWidth: true
                    elide: root.expanded ? Text.ElideNone : Text.ElideRight
                    wrapMode: root.expanded ? Text.Wrap : Text.NoWrap
                    text: root.notification.summary
                    color: Config.text
                    font.family: Config.font
                    font.pixelSize: Config.fontSize
                    font.bold: true
                }
                Text {
                    id: body
                    Layout.fillWidth: true
                    visible: text !== ""
                    // StyledText ignores plain newlines.
                    text: (root.notification.body || "").replace(/\n/g, "<br>")
                    textFormat: Text.StyledText
                    wrapMode: Text.Wrap
                    maximumLineCount: root.expanded ? 10000 : root.toast ? 4 : 3
                    elide: root.expanded ? Text.ElideNone : Text.ElideRight
                    color: Config.muted
                    font.family: Config.font
                    font.pixelSize: Config.fontSize - 1
                    onLinkActivated: link => Qt.openUrlExternally(link)
                }
                Text {
                    visible: !root.expanded && (summary.truncated || body.truncated)
                    text: "click to read all"
                    color: Config.alpha(Config.muted, 0.7)
                    font.family: Config.font
                    font.pixelSize: Config.fontSize - 3
                }
            }
        }

        RowLayout {
            visible: root.expanded
            Layout.fillWidth: true
            spacing: 6
            Repeater {
                model: [
                    { label: root.copied ? "Copied" : "Copy", run: () => root.copy(), show: true },
                    { label: "Open", run: () => { root.defaultAction.invoke(); if (root.toast) root.closed(); }, show: root.defaultAction !== null },
                ].filter(b => b.show)
                Rectangle {
                    required property var modelData
                    Layout.fillWidth: true
                    implicitHeight: 26
                    radius: Config.rounding - 4
                    color: buttonArea.containsMouse ? Config.alpha(Config.accent, 0.25) : Config.hover
                    Text {
                        anchors.centerIn: parent
                        text: parent.modelData.label
                        color: root.copied && parent.modelData.label === "Copied" ? Config.good : Config.text
                        font.family: Config.font
                        font.pixelSize: Config.fontSize - 2
                    }
                    MouseArea {
                        id: buttonArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: parent.modelData.run()
                    }
                }
            }
        }

        RowLayout {
            visible: root.actions.length > 0
            Layout.fillWidth: true
            spacing: 6
            Repeater {
                model: root.actions
                Rectangle {
                    required property var modelData
                    Layout.fillWidth: true
                    implicitHeight: 26
                    radius: Config.rounding - 4
                    color: actionArea.containsMouse ? Config.alpha(Config.accent, 0.25) : Config.hover
                    Text {
                        anchors.centerIn: parent
                        width: parent.width - 12
                        horizontalAlignment: Text.AlignHCenter
                        elide: Text.ElideRight
                        text: parent.modelData.text
                        color: Config.text
                        font.family: Config.font
                        font.pixelSize: Config.fontSize - 2
                    }
                    MouseArea {
                        id: actionArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: parent.modelData.invoke()
                    }
                }
            }
        }
    }
}
