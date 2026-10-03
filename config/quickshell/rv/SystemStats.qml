pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io

// CPU, memory and temperature read straight from /proc and /sys every few
// seconds: no helper processes.
Singleton {
    id: root

    property real cpu: 0
    property real memory: 0
    property real memUsedGiB: 0
    property real memTotalGiB: 0
    property real swapUsedGiB: 0
    property real temperature: 0
    property string uptime: ""
    property int consumers: 0       // stats only poll while something shows them

    property var lastIdle: 0
    property var lastTotal: 0

    Timer {
        interval: 3000
        running: root.consumers > 0
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            stat.reload();
            meminfo.reload();
            thermal.reload();
            uptimeFile.reload();
        }
    }

    FileView {
        id: stat
        path: "/proc/stat"
        onLoaded: {
            const f = text().split("\n")[0].trim().split(/\s+/).slice(1).map(Number);
            const idle = f[3] + (f[4] || 0);
            const total = f.reduce((a, b) => a + b, 0);
            if (root.lastTotal > 0 && total > root.lastTotal)
                root.cpu = 1 - (idle - root.lastIdle) / (total - root.lastTotal);
            root.lastIdle = idle;
            root.lastTotal = total;
        }
    }
    FileView {
        id: meminfo
        path: "/proc/meminfo"
        onLoaded: {
            const v = {};
            for (const line of text().split("\n")) {
                const m = line.match(/^(\w+):\s+(\d+)/);
                if (m) v[m[1]] = Number(m[2]);
            }
            const used = v.MemTotal - v.MemAvailable;
            root.memory = used / v.MemTotal;
            root.memUsedGiB = used / 1048576;
            root.memTotalGiB = v.MemTotal / 1048576;
            root.swapUsedGiB = (v.SwapTotal - v.SwapFree) / 1048576;
        }
    }
    FileView {
        id: thermal
        path: "/sys/class/thermal/thermal_zone0/temp"
        printErrors: false
        onLoaded: root.temperature = Number(text()) / 1000
    }
    FileView {
        id: uptimeFile
        path: "/proc/uptime"
        onLoaded: {
            const s = Math.floor(Number(text().split(" ")[0]));
            const d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60);
            root.uptime = (d ? d + "d " : "") + (h ? h + "h " : "") + m + "m";
        }
    }
}
