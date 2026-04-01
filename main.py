"""
main.py — Entry point for the Virtual Drone Hijack Simulator.

Usage:
    python main.py

Spawns the virtual drone in a background thread, then runs the hijacker
attack sequence with a live Rich terminal dashboard.
"""

import threading
import time
import sys

from drone import VirtualDrone
from hijacker import Hijacker
from cli import SimulatorUI, console


def main():
    # ── Shared event log ───────────────────────────────────────────────────────
    event_log = []

    # ── Create components ─────────────────────────────────────────────────────
    drone    = VirtualDrone(event_log=event_log)
    hijacker = Hijacker(event_log=event_log)
    ui       = SimulatorUI(drone, hijacker)

    hijacker._on_phase = ui.on_phase_update

    # ── Show banner ───────────────────────────────────────────────────────────
    ui.show_banner()

    # ── Start the virtual drone (background thread) ───────────────────────────
    console.print("[bold cyan]  [*] Starting virtual drone...[/bold cyan]")
    drone.start()
    time.sleep(1.2)   # let the drone get ready and broadcast first heartbeat
    console.print("[bold cyan]  [*] Drone online — beginning attack sequence...[/bold cyan]")
    time.sleep(0.8)

    # ── Run hijacker in a background thread so UI can render live ─────────────
    attack_done = threading.Event()

    def run_attack():
        hijacker.run()
        attack_done.set()

    attack_thread = threading.Thread(target=run_attack, daemon=True)
    attack_thread.start()

    # ── Live dashboard (blocks until CONTROL phase reached) ───────────────────
    ui.run_attack_ui()

    # Wait for attack thread to fully finish
    attack_done.wait(timeout=30)

    # ── Interactive control REPL ──────────────────────────────────────────────
    ui.run_control_repl()

    # ── Cleanup ───────────────────────────────────────────────────────────────
    drone.stop()
    console.print("[bold dim]\n  Drone shutdown. Simulator exited.[/bold dim]")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Interrupted by user.[/bold yellow]")
        sys.exit(0)
