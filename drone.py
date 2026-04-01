"""
drone.py — Virtual MAVLink-style drone that runs in a background thread.

States: IDLE → ARMED → FLYING → HIJACKED → LANDED
"""

import socket
import struct
import threading
import time
import random
import json
import math

from network import (
    DRONE_HOST, DRONE_PORT, BROADCAST_PORT,
    XOR_KEY, MSG_HEARTBEAT, MSG_TELEMETRY, MSG_CMD, MSG_ACK,
    build_packet, parse_packet, DroneChannel
)

# ─── Drone State ──────────────────────────────────────────────────────────────

class DroneState:
    IDLE     = "IDLE"
    ARMED    = "ARMED"
    FLYING   = "FLYING"
    HIJACKED = "HIJACKED"
    LANDED   = "LANDED"


class VirtualDrone:
    """
    Simulates a MAVLink-style drone over UDP.
    - Broadcasts heartbeat every 1 second on BROADCAST_PORT
    - Accepts command packets on DRONE_PORT
    """

    SYS_ID = 0x01   # Drone's system ID

    def __init__(self, event_log=None):
        self.state       = DroneState.IDLE
        self.armed       = False
        self.altitude    = 0.0       # metres
        self.lat         = 37.7749   # San Francisco
        self.lon         = -122.4194
        self.heading     = 0.0       # degrees
        self.speed       = 0.0       # m/s
        self.battery     = 100.0     # percent
        self.seq         = 0
        self.owner       = "GCS"     # "GCS" or "HIJACKER"
        self._running    = False
        self._lock       = threading.Lock()
        self._event_log  = event_log or []   # shared list for UI log messages

        # Sockets
        self._cmd_channel  = DroneChannel(DRONE_HOST, DRONE_PORT)
        self._bcast_sock   = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # ── Public API ─────────────────────────────────────────────────────────────

    def start(self):
        self._running = True
        threading.Thread(target=self._heartbeat_loop, daemon=True).start()
        threading.Thread(target=self._cmd_listener,   daemon=True).start()
        threading.Thread(target=self._physics_loop,   daemon=True).start()
        self._log("Drone online — broadcasting on port {}".format(BROADCAST_PORT))

    def stop(self):
        self._running = False
        self._cmd_channel.close()
        self._bcast_sock.close()

    def get_telemetry(self) -> dict:
        with self._lock:
            return {
                "state":    self.state,
                "armed":    self.armed,
                "altitude": round(self.altitude, 1),
                "lat":      round(self.lat, 6),
                "lon":      round(self.lon, 6),
                "heading":  round(self.heading, 1),
                "speed":    round(self.speed, 1),
                "battery":  round(self.battery, 1),
                "owner":    self.owner,
            }

    # ── Private loops ──────────────────────────────────────────────────────────

    def _heartbeat_loop(self):
        """Broadcast heartbeat every second."""
        while self._running:
            payload = json.dumps({
                "sys_id": self.SYS_ID,
                "state":  self.state,
                "armed":  self.armed,
            }).encode()
            pkt = build_packet(self.SYS_ID, MSG_HEARTBEAT, self._next_seq(), payload)
            try:
                self._bcast_sock.sendto(pkt, (DRONE_HOST, BROADCAST_PORT))
            except Exception:
                pass
            time.sleep(1.0)

    def _cmd_listener(self):
        """Listen for incoming command packets."""
        while self._running:
            data, addr = self._cmd_channel.recv()
            if data is None:
                continue
            parsed = parse_packet(data, XOR_KEY)
            if parsed is None:
                continue
            sys_id, msg_type, seq, payload_bytes = parsed
            if msg_type == MSG_CMD:
                self._handle_command(payload_bytes, addr)

    def _physics_loop(self):
        """Update drone physics ~10 Hz."""
        while self._running:
            with self._lock:
                if self.state == DroneState.FLYING or self.state == DroneState.HIJACKED:
                    # Drain battery
                    self.battery = max(0.0, self.battery - 0.01)
                    # Gentle drift
                    rad = math.radians(self.heading)
                    self.lat += math.cos(rad) * self.speed * 0.000001
                    self.lon += math.sin(rad) * self.speed * 0.000001
                    # Heading wobble
                    self.heading = (self.heading + random.uniform(-0.5, 0.5)) % 360
            time.sleep(0.1)

    def _handle_command(self, payload_bytes: bytes, addr):
        """Process a decoded command payload."""
        try:
            cmd = json.loads(payload_bytes.decode())
        except Exception:
            return

        action  = cmd.get("action", "")
        issuer  = cmd.get("issuer", "GCS")

        with self._lock:
            if action == "ARM" and self.state == DroneState.IDLE:
                self.state  = DroneState.ARMED
                self.armed  = True
                self._log(f"[{issuer}] Command: ARM — drone armed", issuer)

            elif action == "TAKEOFF" and self.state in (DroneState.ARMED, DroneState.LANDED):
                self.state    = DroneState.FLYING if issuer == "GCS" else DroneState.HIJACKED
                self.altitude = float(cmd.get("alt", 50.0))
                self.speed    = 5.0
                self._log(f"[{issuer}] Command: TAKEOFF → {self.altitude}m", issuer)

            elif action == "GOTO" and self.state in (DroneState.FLYING, DroneState.HIJACKED):
                self.lat     = float(cmd.get("lat", self.lat))
                self.lon     = float(cmd.get("lon", self.lon))
                self.heading = float(cmd.get("heading", random.uniform(0, 360)))
                self.speed   = 8.0
                if issuer != "GCS":
                    self.state = DroneState.HIJACKED
                self._log(f"[{issuer}] Command: GOTO ({self.lat:.4f}, {self.lon:.4f})", issuer)

            elif action == "LAND":
                self.state    = DroneState.LANDED
                self.altitude = 0.0
                self.speed    = 0.0
                self._log(f"[{issuer}] Command: LAND", issuer)

            elif action == "RTB":
                self.lat     = 37.7749
                self.lon     = -122.4194
                self.heading = 180.0
                self.speed   = 10.0
                self._log(f"[{issuer}] Command: RTB (Return to Base)", issuer)

            elif action == "CLAIM":
                # Hijacker claiming the drone
                self.owner = "HIJACKER"
                self.state = DroneState.HIJACKED
                self._log("⚠  DRONE HIJACKED — GCS control severed!", issuer)

    def _next_seq(self) -> int:
        self.seq = (self.seq + 1) & 0xFF
        return self.seq

    def _log(self, msg: str, issuer: str = "DRONE"):
        self._event_log.append(("[DRONE]", msg))
