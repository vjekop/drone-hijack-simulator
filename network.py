"""
network.py — Simulated RF/UDP communication channel for the drone hijack simulator.

Packet structure: [MAGIC(2)][SYS_ID(1)][MSG_TYPE(1)][SEQ(1)][PAYLOAD_LEN(1)][PAYLOAD(N)][CHECKSUM(1)]
"""

import socket
import struct
import random
import time
import threading

# ─── Constants ────────────────────────────────────────────────────────────────
DRONE_HOST     = "127.0.0.1"
DRONE_PORT     = 14550      # Drone listens here (like MAVLink default)
GCS_PORT       = 14551      # Ground Control Station port
BROADCAST_PORT = 14552      # Drone heartbeat broadcast port

MAGIC          = b"\xFE\xA0"   # Packet magic bytes
XOR_KEY        = 0x5A          # Weak "encryption" key (intentionally crackable)

MSG_HEARTBEAT  = 0x00
MSG_TELEMETRY  = 0x01
MSG_CMD        = 0x02
MSG_ACK        = 0x03
MSG_JAM        = 0xFF

# ─── Packet helpers ───────────────────────────────────────────────────────────

def _checksum(data: bytes) -> int:
    """Simple XOR checksum over all bytes."""
    cs = 0
    for b in data:
        cs ^= b
    return cs & 0xFF


def _xor_payload(payload: bytes, key: int = XOR_KEY) -> bytes:
    """Apply XOR 'encryption' to payload bytes."""
    return bytes(b ^ key for b in payload)


def build_packet(sys_id: int, msg_type: int, seq: int, payload: bytes, key: int = XOR_KEY) -> bytes:
    """Build an obfuscated packet."""
    enc_payload = _xor_payload(payload, key)
    header = struct.pack("BBBB", sys_id, msg_type, seq, len(enc_payload))
    body = MAGIC + header + enc_payload
    cs = _checksum(body)
    return body + bytes([cs])


def parse_packet(data: bytes, key: int = XOR_KEY):
    """
    Parse a raw packet. Returns (sys_id, msg_type, seq, payload) or None on error.
    """
    if len(data) < 8:
        return None
    if data[:2] != MAGIC:
        return None
    sys_id, msg_type, seq, payload_len = struct.unpack("BBBB", data[2:6])
    if len(data) < 6 + payload_len + 1:
        return None
    enc_payload = data[6: 6 + payload_len]
    cs_received = data[6 + payload_len]
    cs_expected = _checksum(data[:6 + payload_len])
    if cs_received != cs_expected:
        return None
    payload = _xor_payload(enc_payload, key)
    return sys_id, msg_type, seq, payload


# ─── Channel ──────────────────────────────────────────────────────────────────

class DroneChannel:
    """Wraps a UDP socket with simulated signal noise."""

    def __init__(self, bind_host: str = DRONE_HOST, bind_port: int = None,
                 signal_strength: float = 1.0, packet_loss: float = 0.0):
        self.signal_strength = signal_strength   # 0.0–1.0
        self.packet_loss     = packet_loss       # probability of drop
        self._lock           = threading.Lock()
        self._sock           = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if bind_port:
            self._sock.bind((bind_host, bind_port))
            self._sock.settimeout(0.5)

    # ── send ──
    def send(self, host: str, port: int, data: bytes) -> bool:
        if random.random() < self.packet_loss:
            return False  # simulate drop
        noise = random.random() > self.signal_strength
        if noise:
            data = self._corrupt(data)
        try:
            self._sock.sendto(data, (host, port))
            return True
        except Exception:
            return False

    # ── receive ──
    def recv(self, bufsize: int = 4096):
        try:
            data, addr = self._sock.recvfrom(bufsize)
            return data, addr
        except socket.timeout:
            return None, None
        except Exception:
            return None, None

    # ── helpers ──
    @staticmethod
    def _corrupt(data: bytes) -> bytes:
        """Flip a random bit to simulate RF noise."""
        if not data:
            return data
        lst = bytearray(data)
        idx = random.randint(0, len(lst) - 1)
        lst[idx] ^= (1 << random.randint(0, 7))
        return bytes(lst)

    def close(self):
        self._sock.close()
