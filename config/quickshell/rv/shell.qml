//@ pragma Env QS_NO_RELOAD_POPUP=1
//@ pragma IconTheme Papirus-Dark

// rv shell: one Quickshell process for the bar, launcher, notifications,
// OSD, lock and idle handling. Windows that are not on screen are not
// created, so an idle session holds just the bar.
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland

ShellRoot {
    id: shell

    Variants {
        id: bars
        model: Config.get("bar", "allMonitors", true) ? Quickshell.screens : [Quickshell.screens[0]]
        Bar {}
    }

    Wallpaper {}
    Toasts {}
    LauncherWindow {}
    Osd { id: osd }

    // Touch the session singleton so idle handling starts with the shell.
    readonly property bool sessionReady: Session.locked || true

    function focusedBar() {
        const name = Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : "";
        return bars.instances.find(b => b.screen && b.screen.name === name) || bars.instances[0];
    }

    // ---- IPC: `rv <command>` lands here -------------------------------------
    IpcHandler {
        target: "shell"
        function ping(): string { return "pong"; }
        function quit(): void { Qt.quit(); }
        function lock(): void { Session.lock(); }
        function powerMenu(): void {
            const bar = shell.focusedBar();
            if (bar) bar.powerPopup.open = !bar.powerPopup.open;
        }
    }
    IpcHandler {
        target: "bar"
        function toggle(): void { Config.barVisible = !Config.barVisible; }
        function show(): void { Config.barVisible = true; }
        function hide(): void { Config.barVisible = false; }
    }
    IpcHandler {
        target: "launcher"
        function open(mode: string): void { Launcher.toggle(mode); }
        function web(text: string): void {
            Launcher.show("web");
            Launcher.query = text;
            Launcher.webSearch(text);
        }
    }
    IpcHandler {
        target: "notifications"
        function toggleList(): void {
            const bar = shell.focusedBar();
            if (bar) bar.notificationPopup.open = !bar.notificationPopup.open;
        }
        function clear(): void { Notifs.clear(); }
        function toggleDnd(): void { Notifs.setDnd(!Notifs.dnd); }
        function count(): int { return Notifs.history.length; }
    }
    IpcHandler {
        target: "osd"
        function show(kind: string): void { osd.show(kind); }
    }
    IpcHandler {
        target: "media"
        function toggle(): void { MediaState.toggle(); }
        function next(): void { MediaState.next(); }
        function previous(): void { MediaState.previous(); }
        function stop(): void { MediaState.stop(); }
    }
}
