"""
cli.py — Rich terminal UI for the drone hijack simulator.
"""

import time
import threading
from typing import Optional

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Prompt
from rich import box

from hijacker import (
    PHASE_SCAN, PHASE_ANALYZE, PHASE_JAM,
    PHASE_INJECT, PHASE_CONTROL, PHASE_DONE
)

console = Console()

# ─── ASCII Banner ─────────────────────────────────────────────────────────────

BANNER = r"""
[bold red]
 ██████╗ ██████╗  ██████╗ ███╗  ██╗███████╗    ██╗  ██╗ █████╗  ██████╗██╗  ██╗
 ██╔══██╗██╔══██╗██╔═══██╗████╗ ██║██╔════╝    ██║  ██║██╔══██╗██╔════╝██║ ██╔╝
 ██║  ██║██████╔╝██║   ██║██╔██╗██║█████╗      ███████║███████║██║     █████╔╝
 ██║  ██║██╔══██╗██║   ██║██║╚████║██╔══╝      ██╔══██║██╔══██║██║     ██╔═██╗
 ██████╔╝██║  ██║╚██████╔╝██║ ╚███║███████╗    ██║  ██║██║  ██║╚██████╗██║  ██╗
 ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚══╝╚══════╝   ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝
     ██╗  ██╗██╗     ██╗ █████╗  ██████╗██╗  ██╗███████╗██████╗
     ██║  ██║██║     ██║██╔══██╗██╔════╝██║ ██╔╝██╔════╝██╔══██╗
     ███████║██║     ██║███████║██║     █████╔╝ █████╗  ██████╔╝
     ██╔══██║██║██   ██║██╔══██║██║     ██╔═██╗ ██╔══╝  ██╔══██╗
     ██║  ██║██║╚█████╔╝██║  ██║╚██████╗██║  ██╗███████╗██║  ██║
     ╚═╝  ╚═╝╚═╝ ╚════╝ ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝
[/bold red]
[dim]                   Virtual Drone Penetration Testing Simulator[/dim]
[dim]                   ─────────────────────────────────────────[/dim]
[dim]                       For Educational & Portfolio Use Only[/dim]
"""

# ─── Phase styling ────────────────────────────────────────────────────────────

PHASE_STYLE = {
    PHASE_SCAN:    ("🔵", "blue",   "Passive Scan"),
    PHASE_ANALYZE: ("🟡", "yellow", "Key Analysis"),
    PHASE_JAM:     ("🔴", "red",    "RF Jamming"),
    PHASE_INJECT:  ("🟣", "magenta","Packet Injection"),
    PHASE_CONTROL: ("🟢", "green",  "Full Control"),
    PHASE_DONE:    ("⚪", "white",  "Done"),
}


# ─── Telemetry panel ──────────────────────────────────────────────────────────

def _make_telemetry_panel(telemetry: dict, phase: str) -> Panel:
    emoji, style, label = PHASE_STYLE.get(phase, ("⚪", "white", phase))

    t = Table.grid(padding=(0, 2))
    t.add_column(style="bold dim", justify="right")
    t.add_column()

    telem = telemetry or {}
    state   = telem.get("state", "---")
    owner   = telem.get("owner", "---")
    battery = telem.get("battery", 0)

    owner_style  = "bold red"   if owner == "HIJACKER" else "bold green"
    state_style  = "bold red"   if state == "HIJACKED" else "bold cyan"
    batt_style   = "bold red"   if battery < 20 else "bold yellow" if battery < 50 else "bold green"

    t.add_row("State",    Text(state, style=state_style))
    t.add_row("Owner",    Text(owner, style=owner_style))
    t.add_row("Altitude", Text(f"{telem.get('altitude', 0):.1f} m"))
    t.add_row("Latitude", Text(f"{telem.get('lat', 0):.6f}°"))
    t.add_row("Longitude",Text(f"{telem.get('lon', 0):.6f}°"))
    t.add_row("Heading",  Text(f"{telem.get('heading', 0):.1f}°"))
    t.add_row("Speed",    Text(f"{telem.get('speed', 0):.1f} m/s"))
    t.add_row("Battery",  Text(f"{battery:.1f}%", style=batt_style))
    t.add_row("", "")
    t.add_row("Phase",    Text(f"{emoji}  {label}", style=style))

    return Panel(t, title="[bold cyan]🛸  DRONE TELEMETRY[/bold cyan]",
                 border_style=style, box=box.ROUNDED, padding=(1, 2))


# ─── Attack log panel ─────────────────────────────────────────────────────────

def _make_log_panel(event_log: list) -> Panel:
    lines = event_log[-22:]   # last 22 lines
    text  = Text()
    for tag, msg in lines:
        if tag == "[HACK]":
            color = "bright_red"
        elif tag == "[DRONE]":
            color = "cyan"
        else:
            color = "white"
        text.append(f"{tag} ", style=f"bold {color}")
        text.append(msg + "\n", style=color)
    return Panel(text, title="[bold red]💀  ATTACK LOG[/bold red]",
                 border_style="red", box=box.ROUNDED, padding=(0, 1))


# ─── Layout builder ───────────────────────────────────────────────────────────

def _build_layout(telemetry: dict, event_log: list, phase: str) -> Layout:
    layout = Layout()
    layout.split_row(
        Layout(_make_telemetry_panel(telemetry, phase), name="left",  ratio=2),
        Layout(_make_log_panel(event_log),              name="right", ratio=3),
    )
    return layout


# ─── Main simulator UI ────────────────────────────────────────────────────────

class SimulatorUI:
    def __init__(self, drone, hijacker):
        self._drone    = drone
        self._hijacker = hijacker
        self._phase    = PHASE_SCAN
        self._progress = 0.0
        self._lock     = threading.Lock()

    def on_phase_update(self, phase: str, progress: float):
        with self._lock:
            self._phase    = phase
            self._progress = progress

    def show_banner(self):
        console.clear()
        console.print(BANNER)
        time.sleep(1.5)

    def run_attack_ui(self):
        """Run the live dashboard during the attack phases."""
        event_log = self._drone._event_log

        with Live(console=console, refresh_per_second=8, screen=False) as live:
            while self._hijacker.phase not in (PHASE_CONTROL, PHASE_DONE):
                with self._lock:
                    phase = self._phase
                telem = self._drone.get_telemetry()
                live.update(_build_layout(telem, event_log, phase))
                time.sleep(0.13)

            # Render one last frame in control phase
            telem = self._drone.get_telemetry()
            live.update(_build_layout(telem, event_log, PHASE_CONTROL))
            time.sleep(0.5)

    def run_control_repl(self):
        """Interactive control REPL once drone is hijacked."""
        event_log = self._drone._event_log
        console.print()
        console.rule("[bold green]🟢  DRONE HIJACKED — YOU HAVE FULL CONTROL[/bold green]")
        console.print("[dim]Commands: takeoff [alt]  |  goto <lat> <lon>  |  land  |  rtb  |  status  |  exit[/dim]")
        console.print()

        while True:
            # Live mini-telemetry refresh
            telem = self._drone.get_telemetry()
            try:
                raw = Prompt.ask("[bold red]HIJACKER[/bold red][dim]>[/dim]")
            except (KeyboardInterrupt, EOFError):
                break

            parts = raw.strip().split()
            if not parts:
                continue
            cmd_name = parts[0].lower()

            if cmd_name == "exit":
                console.print("[bold yellow]Severing connection...[/bold yellow]")
                break

            elif cmd_name == "status":
                telem = self._drone.get_telemetry()
                t = Table(box=box.SIMPLE, show_header=False)
                t.add_column(style="bold dim", justify="right")
                t.add_column()
                for k, v in telem.items():
                    t.add_row(k.upper(), str(v))
                console.print(t)

            elif cmd_name == "takeoff":
                alt = float(parts[1]) if len(parts) > 1 else 50.0
                self._hijacker.send_command({"action": "TAKEOFF", "alt": alt})
                event_log.append(("[HACK]", f"→ Sending TAKEOFF to {alt}m"))

            elif cmd_name == "goto":
                if len(parts) < 3:
                    console.print("[red]Usage: goto <lat> <lon>[/red]")
                    continue
                lat, lon = float(parts[1]), float(parts[2])
                self._hijacker.send_command({"action": "GOTO", "lat": lat, "lon": lon})
                event_log.append(("[HACK]", f"→ Sending GOTO ({lat}, {lon})"))

            elif cmd_name == "land":
                self._hijacker.send_command({"action": "LAND"})
                event_log.append(("[HACK]", "→ Sending LAND command"))

            elif cmd_name == "rtb":
                self._hijacker.send_command({"action": "RTB"})
                event_log.append(("[HACK]", "→ Sending RTB (Return to Base)"))

            else:
                console.print(f"[red]Unknown command:[/red] {cmd_name}")

        console.print()
        console.rule("[bold dim]Session terminated[/bold dim]")
