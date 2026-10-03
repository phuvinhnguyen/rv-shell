pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Services.Notifications

// Notification daemon. Keeps a short history (newest first, capped) and a
// list of on-screen toasts. Do-not-disturb hides toasts except critical ones.
Singleton {
    id: root

    readonly property int historyLimit: 50
    readonly property bool dnd: Config.get("notifications", "doNotDisturb", false)
    property var receivedAt: ({})
    property bool listOpen: false
    readonly property var history: server.trackedNotifications.values.slice().reverse()
    property var toasts: []

    function timeoutFor(n) {
        if (n.urgency === NotificationUrgency.Critical) return 0;
        if (n.expireTimeout > 0) return Math.min(n.expireTimeout, 15000);
        return Config.get("notifications", "timeoutSeconds", 5) * 1000;
    }

    function dropToast(n) { toasts = toasts.filter(t => t !== n); }
    // Stored in settings.json, so the choice survives restarts.
    function setDnd(on) {
        Quickshell.execDetached(["python3", Config.repo + "/tui/rvlib.py", "set", "notifications.doNotDisturb", on ? "true" : "false"]);
    }
    function ago(n) {
        const t = receivedAt[n.id];
        if (!t) return "";
        const m = Math.floor((Date.now() - t) / 60000);
        return m < 1 ? "now" : m < 60 ? `${m}m` : `${Math.floor(m / 60)}h`;
    }
    function clear() {
        for (const n of server.trackedNotifications.values.slice()) n.dismiss();
        toasts = [];
    }

    NotificationServer {
        id: server
        keepOnReload: true
        bodySupported: true
        bodyMarkupSupported: true
        actionsSupported: true
        imageSupported: true
        persistenceSupported: true

        onNotification: n => {
            n.tracked = true;
            root.receivedAt[n.id] = Date.now();
            const tracked = server.trackedNotifications.values;
            if (tracked.length > root.historyLimit) tracked[0].dismiss();
            if (!root.dnd || n.urgency === NotificationUrgency.Critical)
                root.toasts = [n].concat(root.toasts).slice(0, 4);
        }
    }
}
