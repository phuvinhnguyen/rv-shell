pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Services.Pam

// Locking and idle handling. Idle timeouts come from settings → Idle;
// applications that inhibit idle (video players, games) are respected, and
// "keep awake" in the power menu pauses all of it.
Singleton {
    id: root

    property bool locked: false
    property bool keepAwake: false

    function lock() { root.locked = true; }

    // ---- Lock-screen input --------------------------------------------------
    // One buffer shared by every screen's lock surface. Keys are read raw (no
    // text field), so input methods such as fcitx5 never take over: what you
    // type is what the keyboard layout produces.
    property string secret: ""
    property bool checking: false
    property string error: ""
    signal typed(int kind)          // 0 = character, 1 = erase, 2 = clear, 3 = rejected

    function typeKey(event) {
        if (checking) return;
        const ctrl = event.modifiers & Qt.ControlModifier;
        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) { submit(); return; }
        if (event.key === Qt.Key_Escape || (ctrl && event.key === Qt.Key_U)) {
            if (secret !== "") { secret = ""; typed(2); }
            return;
        }
        if (event.key === Qt.Key_Backspace) {
            if (secret !== "") { secret = secret.slice(0, -1); typed(1); }
            return;
        }
        if (ctrl || !event.text || event.text.length !== 1 || event.text < " ") return;
        error = "";
        secret += event.text;
        typed(0);
    }

    function submit() {
        if (secret === "" || checking) return;
        checking = true;
        error = "";
        if (!pam.start()) { checking = false; error = "Authentication unavailable"; }
    }

    PamContext {
        id: pam
        configDirectory: Config.repo + "/config/quickshell/rv/pam"
        config: "rv-lock"
        onResponseRequiredChanged: if (responseRequired) respond(root.secret)
        onCompleted: result => {
            root.checking = false;
            root.secret = "";
            if (result === PamResult.Success) {
                root.error = "";
                root.locked = false;
            } else {
                root.error = "Wrong password";
                root.typed(3);
            }
        }
        onError: err => { root.checking = false; root.secret = ""; root.error = "Authentication unavailable"; }
    }
    onLockedChanged: if (locked) { secret = ""; error = ""; }

    function dpms(on) {
        Quickshell.execDetached(["hyprctl", "eval", `hl.dispatch(hl.dsp.dpms({ action = "${on ? "on" : "off"}" }))`]);
    }

    readonly property int lockMinutes: Config.get("idle", "lockMinutes", 5)
    readonly property int screenOffMinutes: Config.get("idle", "screenOffMinutes", 7)
    readonly property int suspendMinutes: Config.get("idle", "suspendMinutes", 0)

    IdleMonitor {
        enabled: !root.keepAwake && root.lockMinutes > 0
        timeout: root.lockMinutes * 60
        respectInhibitors: true
        onIsIdleChanged: if (isIdle) root.lock()
    }
    IdleMonitor {
        enabled: !root.keepAwake && root.screenOffMinutes > 0
        timeout: root.screenOffMinutes * 60
        respectInhibitors: true
        onIsIdleChanged: root.dpms(!isIdle)
    }
    IdleMonitor {
        enabled: !root.keepAwake && root.suspendMinutes > 0
        timeout: root.suspendMinutes * 60
        respectInhibitors: true
        onIsIdleChanged: if (isIdle) Config.run(["power", "suspend"])
    }

    WlSessionLock {
        id: sessionLock
        locked: root.locked

        WlSessionLockSurface {
            color: Config.bg
            LockScreen { anchors.fill: parent }
        }
    }
}
