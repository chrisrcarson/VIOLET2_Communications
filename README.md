# VIOLET2 Communications

## Overview

This repository contains the communication software for the **VIOLET2** CubeSat mission. It implements a two-layer radio protocol stack using AX.25 (Layer 1) over an FSK RF link which enables a ground station (Earth PC) to send shell commands to the satellite's on-board computer (OBC, referred to as VIOLET2 or Space PC) and receive their output back.

The RF link is handled by **GNU Radio** running on each computer alongside two **LimeSDR** software-defined radios (LimeSDR v1.3 and LimeSDR Mini). The Python scripts communicate with GNU Radio over local UDP sockets. This means Python never talks directly across the network. The cross-machine link is pure RF.

```
[EARTH.py] <--UDP--> [Lime_Big.grc / GNU Radio] <--RF--> [Lime_Mini.grc / GNU Radio] <--UDP--> [VIOLET2.py]
```

## Python Requirements

To run the Python communication scripts (e.g., EARTH.py):

1. Install Python 3.7 or higher
2. Install dependencies from the repository root:
```bash
pip install -r requirements.txt
```

## Protocol Stack

### Layer 1: AX.25

Every packet is wrapped in a 16-byte AX.25 header before being handed to GNU Radio:

| Bytes | Field | Value |
|-------|-------|-------|
| 0–5 | Destination callsign | `VE9VLT` (satellite) |
| 6 | Destination SSID | `0x60` |
| 7–12 | Source callsign | `VE9CNB` (Earth) |
| 13 | Source SSID | `0xE0` |
| 14 | Control | `0x00` |
| 15 | PID | `0xF0` |

`isAx25Packet()` in `violet2_utils.py` validates incoming frames against these expected values and rejects anything that does not match.

### Layer 2: VIOLET2

Immediately after the AX.25 header sits an 8-byte VIOLET2 header:

| Byte | Field | Description |
|------|-------|-------------|
| 0 | `msg_type` | Message type (see table below) |
| 1 | `seq_num` | Sequence number (0–255, wraps) |
| 2 | `total_pkt` | Total packets in this message |
| 3 | `pkt_idx` | Index of this packet (0-based) |
| 4–5 | `payload_len` | Length of application data (big-endian) |
| 6 | `checksum` | XOR of bytes 0–5 |
| 7 | *(reserved)* | Always `0x00` |

**Message types:**

| Hex | Constant | Direction | Meaning |
|-----|----------|-----------|---------|
| `0x01` | `MSG_CMD_SINGLE` | Earth → VIOLET2 | Single-packet shell command |
| `0x02` | `MSG_CMD_MULTI_START` | Earth → VIOLET2 | First fragment of a multi-packet command |
| `0x03` | `MSG_CMD_MULTI_CONT` | Earth → VIOLET2 | Middle fragment |
| `0x04` | `MSG_CMD_MULTI_END` | Earth → VIOLET2 | Final fragment |
| `0x05` | `RESP_SINGLE` | VIOLET2 → Earth | Single-packet response |
| `0x06` | `RESP_MULTI_START` | VIOLET2 → Earth | First fragment of a multi-packet response |
| `0x07` | `RESP_MULTI_CONT` | VIOLET2 → Earth | Middle fragment |
| `0x08` | `RESP_MULTI_END` | VIOLET2 → Earth | Final fragment |
| `0xA0` | `MSG_ACK` | Both | Acknowledgement |
| `0xA1` | `MSG_NACK` | Both | Negative acknowledgement |
| `0xB0` | `MSG_PING` | Both | Ping |
| `0xB1` | `MSG_PONG` | Both | Pong |

**Payload sizing rules:**
- Minimum application data per packet: **92 bytes** (padded with alternating `0xAA / 0x55` if shorter)
- Maximum application data per packet: **248 bytes**
- Commands longer than 248 bytes are automatically fragmented across multiple packets by `violet2ProtocolBuilder()`

## UDP Port Map

Python and GNU Radio always communicate over **localhost** (`127.0.0.1`). The ports are mirrored between the two sides:

| Computer | Script → GNU Radio (TX) | GNU Radio → Script (RX) |
|----------|------------------------|------------------------|
| **Earth PC** | `earth_utils.py`: `UDP_PORT = 27001` | `earth_utils.py`: `RECEIVE_PORT = 27000` |
| **Space PC** | `violet2_utils.py`: `UDP_PORT = 27000` | `violet2_utils.py`: `RECEIVE_PORT = 27001` |

The Earth `Lime_Big.grc` flowgraph matches these ports exactly. The Space `Lime_Mini.grc` flowgraph currently only has the TX socket (port `52001` — needs updating to `27000`) and is missing an RX socket to deliver received packets back to `VIOLET2.py`.

## Running the Software

### Earth PC (ground station)

1. Open and run `Lime_Big.grc` in GNU Radio Companion.
2. In a separate terminal, run:
   ```bash
   python EARTH.py
   ```
3. A `VIOLET2> ` prompt will appear. Type any shell command to send it to the satellite OBC. Results print when a response is received. Type `quit` to exit.

Special local commands available at the prompt:
- History can be toggled by using the `up` and `down` arrows on your keyboard.
- `clear` — clear the terminal
- `download <remote_path> [local_path]` — download a file from the OBC. Files are downloaded in chunks over multiple packets. If interrupted (via Ctrl+C), a `.partial` file is saved so the download can be resumed later.
- `resume <remote_path> [local_path]` — resume a previously interrupted download from the OBC. A `.partial` file must exist for the original download. Upon successful completion, the `.partial` file is automatically cleaned up.
- `ping` — send a ping to VIOLET2 and print the round-trip time in milliseconds

> Note: the RTT will always be at least ~2 seconds because `VIOLET2.py` introduces a built-in 2-second transmit delay (`sleep(2)` in `ax25Send`). This delay exists for RF link timing. The ping will time out after 5 seconds if no pong is received.
>
> **Resumable Downloads**: If a download is interrupted (Ctrl+C), EARTH automatically saves received fragments to a `.partial` file. To resume, use `resume <remote_path> [local_path]` with the same path. The `resume` command requires the `.partial` file to exist; it will not create a new download. 

### Space PC / PocketBeagle 2 (OBC)

1. Open and run `Lime_Mini.grc` in GNU Radio Companion.
2. In a separate terminal, run:
   ```bash
   python VIOLET2.py
   ```
3. `VIOLET2.py` listens for incoming AX.25 frames, decodes the shell command, runs it via `subprocess`, and transmits the output back to Earth.

## Running the Tests

### Prerequisites

Install `pytest` if you haven't already (it is not in `requirements.txt` because it is a dev dependency only):

```bash
pip install pytest
```

### Common Commands

```bash
# Run all unit tests with verbose output
python -m pytest tests/unit/ -v

# Run all unit tests, short summary only (faster to read)
python -m pytest tests/unit/ --tb=short -q

# Run a single test file
python -m pytest tests/unit/communication_protocol_compliance_test.py -v

# Run a single test class
python -m pytest tests/unit/packet_payload_test.py::TestAtMaximumPayload -v

# Run a single test by name
python -m pytest tests/unit/packet_payload_test.py::TestAtMaximumPayload::test_payload_at_maximum_passes_validation -v

# Run hardware tests (requires LimeSDR + GNU Radio running)
python -m pytest tests/hardware/ -m hardware -v

# Run everything except hardware tests
python -m pytest tests/unit/ -v
```

All commands should be run from the **repository root** (`VIOLET2_Communications/`).

## Testing

Tests live in the `tests/` directory and are split into two groups:

### Unit Tests (no hardware required)

Unit tests exercise the protocol logic entirely in Python — no GNU Radio, no LimeSDR, and no network connection between the two computers is needed. They can be run on any machine that has the Python dependencies installed.

```bash
python -m pytest tests/unit/ -v
```

### Integration Tests (dual-terminal UDP simulation)

Integration tests exercise the full uplink/downlink command flow by spawning background Earth and VIOLET2 worker processes on separate UDP ports. These tests do not require GNU Radio or LimeSDR and can run on any system with Python.

```bash
# Run the dual-terminal command flow test
python -m pytest tests/unit/udp_dual_terminal_command_flow_test.py -v
```

The test simulates real command scenarios (ping, ls, download) with multi-packet fragmentation and response reassembly. Execution logs are written to `tests/unit/logs/udp_dual_terminal_command_flow_test.log` for inspection.

**Test data files:**
- `test_data/test.txt` — Small reference file (13 bytes)
- `test_data/ten_packets.txt` — 2480-byte file (exactly 10 × 248-byte VIOLET2 packets) used for multi-packet download testing

### Hardware Tests (require LimeSDR + GNU Radio)

Hardware tests live in `tests/hardware/` and talk to real UDP ports (`27000`/`27001`), meaning GNU Radio must be running and a LimeSDR must be connected on both PCs.

```bash
# Run only hardware tests
python -m pytest tests/hardware/ -m hardware -v

# Run unit tests only, skipping hardware
python -m pytest tests/unit/ -v
```

> Note: To write a hardware test, place it in `tests/hardware/`, import from `violet2_utils` or `earth_utils` directly, and decorate the class or file with `@pytest.mark.hardware`.

## PocketBeagle 2 Setup and Dependencies:
- Radio Conda
- Space PC hier blocks
- BeagleBoard-DeviceTrees https://github.com/beagleboard/BeagleBoard-DeviceTrees
- CAN-Utils https://github.com/linux-can/can-utils
- Implement ArduPilot Device Tree Overlays for CAN interface (use this guide to implement overlays only) https://github.com/juvinski/ardupilot_wiki/blob/pocket2/common/source/docs/common-pocketbeagle-2.rst
- Enabled service to setup CAN that runs:

``
sudo ip link set can0 type can bitrate 500000
``

``
sudo ifconfig can0 up
``

- CAN Interface Up:

``
sudo canup.sh
``

- CAN Interface Down:

``
sudo candown.sh
``


- CAN Receive:

``
candump -cae can0,0:0,#FFFFFFFF
``

- CAN Send:

``
cansend can0 123#DEADBEEF
``

- LimeSDR Mini Tx sweep test:

``
LimeUtil --cal --start 145915000 --stop 145915000
``
