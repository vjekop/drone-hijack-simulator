#  Drone Hijack Simulator

> A Python-based virtual drone penetration testing simulator demonstrating real-world UAV communication attack vectors — built for educational and portfolio purposes.

---

## Overview

This project simulates the process of identifying, analyzing, and exploiting vulnerabilities in an unencrypted drone communication protocol — modeled after real weaknesses found in MAVLink v1, the protocol used by many commercial and hobbyist drones.

The attacker progressively executes a 5-phase RF/network attack against a simulated drone, ultimately gaining full command authority over the vehicle.

**This is a fully self-contained simulator. No real hardware, drones, or external services are involved.**

---

## What This Demonstrates

| Skill Area | Specifics |
|---|---|
| Network programming | Custom UDP socket communication with send/receive channels |
| Packet engineering | Binary packet framing — magic bytes, sys ID, sequence, payload, XOR checksum |
| Cryptanalysis | Brute-force frequency analysis to recover a weak XOR obfuscation key |
| RF attack concepts | Passive sniffing, signal jamming simulation, packet injection / replay |
| Concurrent programming | 3 background threads — heartbeat loop, command listener, physics engine |
| State machine design | Drone FSM: `IDLE → ARMED → FLYING → HIJACKED → LANDED` |
| Terminal UI | Live split-panel dashboard using Python `rich` (telemetry + attack log) |

---

## Real-World Context

The attack chain simulated here maps directly to documented vulnerabilities in UAV communication:

- **CVE-2018-1000156** — Command injection in MAVLink-based systems
- **[SkyJack (2013)](https://samy.pl/skyjack/)** — Samy Kamkar's drone hijacking tool that deauthenticated and re-paired commercial drones over WiFi
- **[MAVLink v1 has no authentication or encryption](https://mavlink.io/en/guide/security.html)** — making it trivially vulnerable to packet forgery on unprotected RF channels

This simulator models the attacker's workflow against a MAVLink v1-style protocol: passive reconnaissance → cryptanalysis → denial of service → command injection.

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                      main.py                         │
│                                                      │
│   ┌─────────────────┐       ┌──────────────────────┐ │
│   │    drone.py     │       │     hijacker.py      │ │
│   │                 │       │                      │ │
│   │  • Heartbeat    │       │  Phase 1: Scan       │ │
│   │    broadcast    │       │  Phase 2: Key crack  │ │
│   │  • CMD listener │◄──────│  Phase 3: Jam        │ │
│   │  • Physics loop │       │  Phase 4: Inject     │ │
│   │  • UDP :14550   │       │  Phase 5: Control    │ │
│   └─────────────────┘       └──────────────────────┘ │
│            │                          │               │
│            └────────── network.py ────┘               │
│                  (packet encoding / UDP)               │
│                                                      │
│                      cli.py                          │
│              (Rich live dashboard + REPL)            │
└──────────────────────────────────────────────────────┘
```

---

## Packet Protocol

Each packet follows a custom binary structure modeled after MAVLink v1:

```
[ MAGIC (2B) ][ SYS_ID (1B) ][ MSG_TYPE (1B) ][ SEQ (1B) ][ LEN (1B) ][ PAYLOAD (NB) ][ CHECKSUM (1B) ]
```

- **MAGIC**: `0xFE 0xA0` — frame synchronization bytes
- **XOR obfuscation**: payload bytes are XOR'd with a single-byte key (intentionally weak, for demonstration)
- **Checksum**: XOR of all preceding bytes — integrity validation

---

## Attack Phases

| Phase | Technique | Description |
|---|---|---|
| 🔵 Scan | Passive RF sniffing | Captures heartbeat broadcasts, identifies drone sys_id |
| 🟡 Analyze | Brute-force cryptanalysis | Tests all 256 XOR keys; validates against known heartbeat structure |
| 🔴 Jam | Denial of Service | Simulates flooding the GCS uplink, severing legitimate controller |
| 🟣 Inject | Packet forgery | Forges ARM, CLAIM, and TAKEOFF commands using recovered key |
| 🟢 Control | Full command authority | Interactive REPL to fly the hijacked drone |

---

## Installation & Usage

```bash
# Clone the repo
git clone https://github.com/<your-username>/drone-hijack-simulator
cd drone-hijack-simulator

# Install dependencies
pip install -r requirements.txt

# Run the simulator
python main.py
```

### Control Commands (during Control phase)

| Command | Description |
|---|---|
| `takeoff [alt]` | Take off to altitude in metres |
| `goto <lat> <lon>` | Navigate to GPS coordinates |
| `land` | Land the drone |
| `rtb` | Return to base |
| `status` | Print full telemetry |
| `exit` | End session |

---

## Project Structure

```
drone-hijack-simulator/
├── main.py          # Entry point — wires drone, hijacker, and UI
├── drone.py         # Virtual drone — state machine, physics, UDP server
├── hijacker.py      # Attacker engine — 5-phase hijack sequence
├── network.py       # Simulated RF channel — packet encoding, noise, loss
├── cli.py           # Rich terminal UI — live dashboard + control REPL
└── requirements.txt
```

---

## Disclaimer

This project is strictly for **educational and portfolio purposes**. It operates entirely in software on localhost. No real drones, RF hardware, or external networks are involved or affected.

---

## Skills Demonstrated

`Python` `UDP Sockets` `Binary Packet Engineering` `Multithreading` `Cryptanalysis` `RF Security Concepts` `State Machines` `Terminal UI (Rich)` `MAVLink Protocol` `Cybersecurity`
