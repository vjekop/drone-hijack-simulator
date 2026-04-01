"""
hijacker.py — Attacker engine that hijacks the virtual drone.

Phases:
  1. SCAN    — Sniff heartbeat packets, identify drone sys_id & channel
  2. ANALYZE — Crack the weak XOR key via frequency analysis
  3. JAM     — Simulate flooding the GCS frequency
  4. INJECT  — Send forged command packets with cracked key
  5. CONTROL — Interactive REPL to fly the hijacked drone
"""

import socket
import struct
import time
import random
import json
import threading
from typing import Callable, Optional

from network import (
    DRONE_HOST, BROADCAST_PORT, DRONE_PORT,
    XOR_KEY, MSG_HEARTBEAT, MSG_CMD, MAGIC,
    build_packet, parse_packet, DroneChannel
)

# ─── Phase names ──────────────────────────────────────────────────────────────
PHASE_SCAN    = "SCANNING"
PHASE_ANALYZE = "ANALYZING"
PHASE_JAM     = "JAMMING"
PHASE_INJECT  = "INJECTING"
PHASE_CONTROL = "CONTROL"
PHASE_DONE    = "DONE"


class Hijacker:
    """
    Orchestrates the drone hijack sequence.

    Parameters
    ----------
    event_log : list
        Shared list — append (tag, message) tuples for the UI to display.
    phase_callback : callable(phase: str, progress: float)
        Called whenever the phase or progress changes (0.0–1.0).
    """

    ATTACKER_SYS_ID = 0x99    # Spoofed system ID

    def __init__(self, event_log: list, phase_callback: Optional[Callable] = None):
        self._log      = event_log
        self._on_phase = phase_callback or (lambda p, v: None)
        self.phase     = PHASE_SCAN
        self.cracked_key: Optional[int] = None
        self.drone_sys_id: Optional[int] = None
        self._seq      = 0
        self._running  = False

        self._listen_channel = DroneChannel(DRONE_HOST, BROADCAST_PORT)
        self._cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # ── Main entry point ───────────────────────────────────────────────────────

    def run(self) -> bool:
        """
        Execute all hijack phases sequentially.
        Returns True when CONTROL phase is reached.
        """
        self._running = True
        self._emit_phase(PHASE_SCAN, 0.0)

        ok = self._phase_scan()
        if not ok:
            return False

        self._emit_phase(PHASE_ANALYZE, 0.0)
        ok = self._phase_analyze()
        if not ok:
            return False

        self._emit_phase(PHASE_JAM, 0.0)
        self._phase_jam()

        self._emit_phase(PHASE_INJECT, 0.0)
        ok = self._phase_inject()
        if not ok:
            return False

        self._emit_phase(PHASE_CONTROL, 1.0)
        return True

    # ── Phase 1: Scan ─────────────────────────────────────────────────────────

    def _phase_scan(self) -> bool:
        self._add_log("Initialising passive scan on 127.0.0.1:{}...".format(BROADCAST_PORT))
        time.sleep(0.4)

        captured_packets = []
        deadline = time.time() + 6.0
        steps = 10
        for i in range(steps):
            self._emit_phase(PHASE_SCAN, i / steps)
            self._add_log(f"  [{i+1}/{steps}] Sniffing channel... signal {random.randint(60,95)}%  RSSI -{random.randint(40,65)} dBm")
            data, addr = self._listen_channel.recv()
            if data and len(data) > 6 and data[:2] == MAGIC:
                captured_packets.append(data)
                self._add_log(f"  ✓ Packet captured ({len(data)} bytes) from {addr[0] if addr else '?'}")
            time.sleep(0.45)

        if not captured_packets:
            self._add_log("✗ No packets captured — is the drone running?")
            return False

        # Try to parse any captured packet
        for pkt in captured_packets:
            # Try all 256 XOR keys to find a valid heartbeat
            for key in range(256):
                parsed = parse_packet(pkt, key)
                if parsed:
                    sys_id, msg_type, seq, payload = parsed
                    if msg_type == MSG_HEARTBEAT:
                        self.drone_sys_id = sys_id
                        self._add_log(f"  ✓ Decoded heartbeat! SYS_ID=0x{sys_id:02X}  MSG_TYPE=HEARTBEAT")
                        self._emit_phase(PHASE_SCAN, 1.0)
                        time.sleep(0.3)
                        return True

        self.drone_sys_id = 0x01   # fallback
        self._add_log("  ~ Partial decode — assuming SYS_ID=0x01")
        self._emit_phase(PHASE_SCAN, 1.0)
        time.sleep(0.3)
        return True

    # ── Phase 2: Analyze / Key Crack ─────────────────────────────────────────

    def _phase_analyze(self) -> bool:
        self._add_log("Running frequency analysis to crack XOR obfuscation key...")
        time.sleep(0.3)

        # Simulated brute-force with dramatic output
        total = 256
        for i in range(0, total, 16):
            self._emit_phase(PHASE_ANALYZE, i / total)
            tested = ", ".join(f"0x{k:02X}" for k in range(i, min(i + 16, total)))
            self._add_log(f"  Testing keys: {tested}")
            time.sleep(0.12)

        self.cracked_key = XOR_KEY
        self._add_log(f"")
        self._add_log(f"  ★ XOR Key cracked: 0x{self.cracked_key:02X} ({self.cracked_key})")
        self._add_log(f"  ★ All future packets will be decrypted and forged with this key.")
        self._emit_phase(PHASE_ANALYZE, 1.0)
        time.sleep(0.5)
        return True

    # ── Phase 3: Jam ──────────────────────────────────────────────────────────

    def _phase_jam(self):
        self._add_log("Initiating RF jamming on GCS uplink frequency...")
        time.sleep(0.3)
        steps = 12
        for i in range(steps):
            strength = int(100 * (1 - i / steps))
            bar = "█" * int(20 * (1 - i / steps)) + "░" * int(20 * i / steps)
            self._add_log(f"  GCS Signal: [{bar}] {strength}%  — flooding channel...")
            self._emit_phase(PHASE_JAM, i / steps)
            time.sleep(0.2)

        self._add_log("  ✓ GCS signal fully suppressed — drone is deaf to legitimate controller")
        self._emit_phase(PHASE_JAM, 1.0)
        time.sleep(0.5)

    # ── Phase 4: Inject ───────────────────────────────────────────────────────

    def _phase_inject(self) -> bool:
        self._add_log("Forging command packets with cracked key...")
        time.sleep(0.3)

        steps = 6
        cmds_to_send = [
            ("ARM",     {"action": "ARM",    "issuer": "HIJACKER"}),
            ("CLAIM",   {"action": "CLAIM",  "issuer": "HIJACKER"}),
            ("TAKEOFF", {"action": "TAKEOFF","issuer": "HIJACKER", "alt": 80}),
        ]

        for i, (name, cmd) in enumerate(cmds_to_send):
            self._emit_phase(PHASE_INJECT, i / steps)
            payload = json.dumps(cmd).encode()
            pkt = build_packet(self.ATTACKER_SYS_ID, MSG_CMD, self._next_seq(), payload, self.cracked_key)
            self._add_log(f"  → Injecting [{name}] packet ({len(pkt)} bytes)...")
            try:
                self._cmd_sock.sendto(pkt, (DRONE_HOST, DRONE_PORT))
            except Exception as e:
                self._add_log(f"    ✗ Send failed: {e}")
            time.sleep(0.6)

        self._add_log("")
        self._add_log("  ✓ DRONE SUCCESSFULLY HIJACKED")
        self._add_log("  ✓ Full command authority acquired")
        self._emit_phase(PHASE_INJECT, 1.0)
        time.sleep(0.5)
        return True

    # ── Phase 5: Send control command ────────────────────────────────────────

    def send_command(self, cmd: dict) -> bool:
        """Send a single command dict to the drone during CONTROL phase."""
        cmd["issuer"] = "HIJACKER"
        payload = json.dumps(cmd).encode()
        pkt = build_packet(self.ATTACKER_SYS_ID, MSG_CMD, self._next_seq(), payload, self.cracked_key or XOR_KEY)
        try:
            self._cmd_sock.sendto(pkt, (DRONE_HOST, DRONE_PORT))
            return True
        except Exception:
            return False

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _next_seq(self) -> int:
        self._seq = (self._seq + 1) & 0xFF
        return self._seq

    def _add_log(self, msg: str):
        self._log.append(("[HACK]", msg))

    def _emit_phase(self, phase: str, progress: float):
        self.phase = phase
        self._on_phase(phase, progress)
