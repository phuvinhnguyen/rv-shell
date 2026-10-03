#!/usr/bin/env python3
"""rv wifi: NetworkManager in a terminal (nmcli underneath).

Enter connect · d disconnect · f forget · s scan · t Wi-Fi on/off
n hidden network · l change a school/work login · p open a sign-in page
e advanced (nmtui) · q quit

School and work networks (eduroam, "WPA2 802.1X") ask for an account
instead of a password: Enter walks through method, username, password and
the server check. Open networks with a web sign-in page (hotels, guest Wi-Fi)
are detected after connecting and the page opens in the browser.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rvlib  # noqa: E402
from rvlib import Row  # noqa: E402

BARS = ["▂___", "▂▄__", "▂▄▆_", "▂▄▆█"]
SYSTEM_CA = "/etc/ssl/certs/ca-certificates.crt"
# Inner (phase 2) methods for each outer EAP method; the first is the usual one.
EAP_METHODS = {
    "PEAP  (eduroam, most universities and companies)": ("peap", ["mschapv2", "gtc", "md5"]),
    "TTLS  (some universities)": ("ttls", ["pap", "mschapv2", "mschap", "chap"]),
}
# Any page served over plain HTTP; a sign-in portal intercepts it and redirects.
PORTAL_PROBE = "http://neverssl.com"


def enterprise(net: dict) -> bool:
    return "802.1X" in net.get("security", "")


def split_terse(line: str) -> list[str]:
    """nmcli -t escapes ':' inside fields as '\\:'."""
    return [field.replace("\\:", ":").replace("\\\\", "\\") for field in re.split(r"(?<!\\):", line)]


class WifiApp(rvlib.App):
    title = "Wi-Fi"
    interval = 6
    keys_hint = "Enter connect · d disconnect · f forget · l login · p sign-in page · s scan · t on/off · n hidden · e nmtui"

    def __init__(self) -> None:
        super().__init__()
        self.enabled = False
        self.networks: list[dict] = []
        self.saved: set[str] = set()
        self.device = ""
        self.address = ""

    def refresh(self) -> None:
        if not rvlib.have("nmcli"):
            self.flash("nmcli not found: install network-manager", rvlib.BAD, 60)
            return
        self.enabled = rvlib.output(["nmcli", "radio", "wifi"]).strip() == "enabled"
        self.saved = set()
        for line in rvlib.output(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"]).splitlines():
            fields = split_terse(line)
            if len(fields) >= 2 and fields[1] == "802-11-wireless":
                self.saved.add(fields[0])
        self.device, self.address = "", ""
        for line in rvlib.output(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device"]).splitlines():
            fields = split_terse(line)
            if len(fields) >= 3 and fields[1] == "wifi":
                self.device = fields[0]
                if fields[2] == "connected":
                    info = rvlib.output(["nmcli", "-t", "-g", "IP4.ADDRESS", "device", "show", fields[0]])
                    self.address = info.split("|")[0].strip()
        best: dict[str, dict] = {}
        listing = rvlib.output(["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY,CHAN", "device", "wifi", "list"], timeout=15)
        for line in listing.splitlines():
            fields = split_terse(line)
            if len(fields) < 5 or not fields[1]:
                continue
            net = {"active": fields[0] == "*", "ssid": fields[1], "signal": int(fields[2] or 0),
                   "security": fields[3] if fields[3] not in ("", "--") else "", "channel": fields[4]}
            old = best.get(net["ssid"])
            if old is None or net["active"] or (not old["active"] and net["signal"] > old["signal"]):
                best[net["ssid"]] = net
        self.networks = sorted(best.values(), key=lambda n: (not n["active"], n["ssid"] not in self.saved, -n["signal"]))

    def rows(self) -> list[Row]:
        state = "on" if self.enabled else "off"
        rows = [Row(f"Wi-Fi {state}" + (f" · {self.device}" if self.device else ""), header=True)]
        if not self.enabled:
            rows.append(Row("Wi-Fi is off — press t to turn it on", colour=rvlib.DIM, data=None))
            return rows
        for net in self.networks:
            bars = BARS[min(3, net["signal"] // 25)]
            lock = "account " if enterprise(net) else "" if net["security"] else "open "
            value = f"{lock}{bars} {net['signal']:>3}%"
            label = net["ssid"]
            if net["active"]:
                label += "  · connected"
            elif net["ssid"] in self.saved:
                label += "  · saved"
            icon = "\U000f0928" if net["signal"] >= 75 else "\U000f0925" if net["signal"] >= 50 else "\U000f0922" if net["signal"] >= 25 else "\U000f091f"
            rows.append(Row(label, value, data=net, icon=icon,
                            colour=rvlib.GOOD if net["active"] else (rvlib.ACCENT if net["ssid"] in self.saved else 0)))
        if not self.networks:
            rows.append(Row("No networks found yet — press s to scan", colour=rvlib.DIM, data=None))
        return rows

    def detail(self, row: Row | None) -> list[str]:
        if row is None or not row.data:
            return []
        net = row.data
        kind = ("school / work account (802.1X)" if enterprise(net)
                else net["security"] or "open — may need a browser sign-in")
        lines = [f"Security: {kind}   Channel: {net['channel']}   Signal: {net['signal']}%"]
        if net["active"] and self.address:
            lines.append(f"Address: {self.address}")
        return lines

    def act(self, message: str, cmd: list[str], timeout: float = 45) -> bool:
        self.busy(message)
        status, out = rvlib.run(cmd, timeout=timeout)
        lines = [l for l in out.splitlines() if l.strip()]
        self.flash(lines[-1] if lines else ("Done" if status == 0 else "Failed"), rvlib.GOOD if status == 0 else rvlib.BAD, 6)
        self.refresh()
        return status == 0

    def connect(self, net: dict) -> None:
        ssid = net["ssid"]
        if ssid in self.saved:
            if self.act(f"Connecting to {ssid}…", ["nmcli", "connection", "up", "id", ssid]):
                self.check_portal()
                return
            if not net["security"]:
                return
            question = "Saved login failed. Enter it again" if enterprise(net) else "Saved password failed. Enter a new one"
            if not self.confirm(question):
                return
            rvlib.run(["nmcli", "connection", "delete", "id", ssid])
        if enterprise(net):
            self.connect_enterprise(ssid)
            return
        cmd = ["nmcli", "device", "wifi", "connect", ssid]
        if net["security"]:
            password = self.prompt(f"Password for {ssid}", secret=True)
            if not password:
                return
            cmd += ["password", password]
        if self.act(f"Connecting to {ssid}…", cmd) and not net["security"]:
            self.check_portal()

    def connect_enterprise(self, ssid: str) -> None:
        """WPA2/WPA3-Enterprise (802.1X): an account instead of a shared password."""
        method = self.choose(f"{ssid}: sign-in method (ask IT if unsure — PEAP is most common)", list(EAP_METHODS))
        if not method:
            return
        eap, inner_options = EAP_METHODS[method]
        inner = self.choose("Inner authentication", inner_options, inner_options[0])
        if not inner:
            return
        identity = self.prompt("Username (often you@school.edu)")
        if not identity:
            return
        password = self.prompt(f"Password for {identity}", secret=True)
        if not password:
            return
        realm = identity.split("@", 1)[1] if "@" in identity else ""
        anonymous = self.prompt("Outer identity (optional, hides your name; Enter keeps it)",
                                f"anonymous@{realm}" if realm else "")
        if anonymous is None:
            return
        domain = self.prompt("Server domain to trust, e.g. radius.school.edu (Enter = your realm; '-' = don't check)",
                             realm)
        if domain is None:
            return
        cmd = ["nmcli", "connection", "add", "type", "wifi", "con-name", ssid, "ssid", ssid,
               "wifi-sec.key-mgmt", "wpa-eap",
               "802-1x.eap", eap, "802-1x.phase2-auth", inner,
               "802-1x.identity", identity, "802-1x.password", password,
               "802-1x.password-flags", "0"]
        if self.device:
            cmd += ["ifname", self.device]
        if anonymous.strip():
            cmd += ["802-1x.anonymous-identity", anonymous.strip()]
        domain = domain.strip()
        if domain and domain != "-":
            # Check the server's certificate against the system CAs and its
            # name: without this, a fake hotspot named eduroam could collect
            # your password.
            cmd += ["802-1x.ca-cert", SYSTEM_CA, "802-1x.domain-suffix-match", domain]
        else:
            cmd += ["802-1x.system-ca-certs", "no"]
        self.busy(f"Saving {ssid}…")
        status, out = rvlib.run(cmd)
        if status != 0:
            self.flash(out.splitlines()[-1] if out else "Could not save the network", rvlib.BAD, 8)
            return
        if self.act(f"Signing in to {ssid}…", ["nmcli", "connection", "up", "id", ssid], timeout=60):
            return
        hint = "Check username/password"
        if domain and domain != "-":
            hint += f"; if they are right, the server domain may differ from {domain} — press l and try '-' or the domain IT gives"
        self.flash(hint, rvlib.BAD, 15)

    def check_portal(self) -> None:
        """Open the browser when the network wants a web sign-in (captive portal)."""
        self.busy("Checking internet access…")
        state = rvlib.output(["nmcli", "networking", "connectivity", "check"], timeout=20).strip()
        if state == "portal":
            rvlib.spawn(["xdg-open", PORTAL_PROBE])
            self.flash("This network needs a sign-in — opened it in your browser", rvlib.WARN, 10)
        elif state == "limited":
            self.flash("Connected, but no internet yet — p opens a sign-in page if there is one", rvlib.WARN, 10)
        elif state == "full":
            self.flash("Connected · internet OK", rvlib.GOOD)

    def on_key(self, key: int, row: Row | None) -> None:
        net = row.data if row else None
        if key in rvlib.ENTER and net:
            if net["active"]:
                self.flash("Already connected — d disconnects", rvlib.DIM)
            else:
                self.connect(net)
        elif key == ord("d") and net and net["active"]:
            self.act("Disconnecting…", ["nmcli", "connection", "down", "id", net["ssid"]])
        elif key == ord("f") and net and net["ssid"] in self.saved:
            if self.confirm(f"Forget {net['ssid']}"):
                self.act("Forgetting…", ["nmcli", "connection", "delete", "id", net["ssid"]])
        elif key == ord("l") and net and enterprise(net):
            if net["ssid"] in self.saved and not self.confirm(f"Replace the saved login for {net['ssid']}"):
                return
            rvlib.run(["nmcli", "connection", "delete", "id", net["ssid"]])
            self.connect_enterprise(net["ssid"])
        elif key == ord("p"):
            rvlib.spawn(["xdg-open", PORTAL_PROBE])
            self.flash("Opened a page in the browser — a sign-in portal will take it over", rvlib.DIM)
        elif key == ord("s"):
            self.busy("Scanning…")
            rvlib.run(["nmcli", "device", "wifi", "rescan"], timeout=15)
            self.refresh()
            self.flash(f"{len(self.networks)} networks", rvlib.GOOD)
        elif key == ord("t"):
            self.act("Switching Wi-Fi…", ["nmcli", "radio", "wifi", "off" if self.enabled else "on"])
        elif key == ord("n"):
            ssid = self.prompt("Hidden network name")
            if ssid:
                password = self.prompt(f"Password for {ssid} (empty if open)", secret=True)
                cmd = ["nmcli", "device", "wifi", "connect", ssid, "hidden", "yes"]
                if password:
                    cmd += ["password", password]
                self.act(f"Connecting to {ssid}…", cmd)
        elif key == ord("e"):
            import curses
            curses.endwin()
            subprocess.call(["nmtui"])
            self.screen.refresh()
            self.refresh()


if __name__ == "__main__":
    rvlib.guard(WifiApp().start)
