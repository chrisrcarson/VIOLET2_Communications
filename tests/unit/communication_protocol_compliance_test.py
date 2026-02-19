# Communication Protocol Compliance Tests
# Associated Requirement: R-G0G-001

# Verifies that AX.25 protocol is used for all communications between the
# Earth ground station and VIOLET2, including uplink and downlink.

import pytest
import socket
import threading
import time

# Constants 
EARTH_CALLSIGN      = "VE9CNB"
SATELLITE_CALLSIGN  = "VE9VLT"
DEST_SSID           = bytes.fromhex("60")
SRC_SSID            = bytes.fromhex("E0")
CONTROL             = bytes.fromhex("00")
PID                 = bytes.fromhex("F0")

AX25_HEADER_SIZE    = 16  # 6 + 1 + 6 + 1 + 1 + 1 bytes

# Placeholder functions (remove once utils.py exists)
def build_ax25_frame(source: str, destination: str, payload: bytes) -> bytes: # build a complete AX.25 frame
    raise NotImplementedError("build_ax25_frame() not yet implemented in packet_utils.py")

def parse_ax25_frame(frame: bytes) -> dict: # parse an AX.25 frame into its components.
    raise NotImplementedError("parse_ax25_frame() not yet implemented in packet_utils.py")

def validate_ax25_frame(frame: bytes) -> bool: # return true if the frame conforms to AX.25 standard.
    raise NotImplementedError("validate_ax25_frame() not yet implemented in packet_utils.py")

# Helper: manually build a frame the same way the existing code does
def _build_raw_frame(dest_callsign: str, src_callsign: str, payload: bytes) -> bytes:
    return (
        dest_callsign.encode('ascii') +
        DEST_SSID +
        src_callsign.encode('ascii') +
        SRC_SSID +
        CONTROL +
        PID +
        payload
    )

# Test 1: Frame Structure
class TestAX25FrameStructure:

    def test_frame_has_correct_header_size(self): # AX.25 frame header should be exactly 16 bytes.
        payload = b"test"
        frame = _build_raw_frame(SATELLITE_CALLSIGN, EARTH_CALLSIGN, payload)
        assert len(frame) == AX25_HEADER_SIZE + len(payload), (
            f"Expected frame length {AX25_HEADER_SIZE + len(payload)}, got {len(frame)}"
        )

    def test_destination_callsign_in_frame(self): # destination callsign should appear at the start of the frame.
        payload = b"test"
        frame = _build_raw_frame(SATELLITE_CALLSIGN, EARTH_CALLSIGN, payload)
        assert frame[:6] == SATELLITE_CALLSIGN.encode('ascii'), (
            "Destination callsign not found at expected position in frame"
        )

    def test_source_callsign_in_frame(self): # source callsign should appear at bytes 7-12 of the frame.
        payload = b"test"
        frame = _build_raw_frame(SATELLITE_CALLSIGN, EARTH_CALLSIGN, payload)
        assert frame[7:13] == EARTH_CALLSIGN.encode('ascii'), (
            "Source callsign not found at expected position in frame"
        )

    def test_control_byte_correct(self): # control byte should be 0x00.
        payload = b"test"
        frame = _build_raw_frame(SATELLITE_CALLSIGN, EARTH_CALLSIGN, payload)
        assert frame[14:15] == CONTROL, (
            f"Expected control byte {CONTROL.hex()}, got {frame[14:15].hex()}"
        )

    def test_pid_byte_correct(self): # PID byte should be 0xF0.
        payload = b"test"
        frame = _build_raw_frame(SATELLITE_CALLSIGN, EARTH_CALLSIGN, payload)
        assert frame[15:16] == PID, (
            f"Expected PID byte {PID.hex()}, got {frame[15:16].hex()}"
        )

    def test_payload_appended_after_header(self):
        """Payload should appear immediately after the 16-byte header."""
        payload = b"hello VIOLET2"
        frame = _build_raw_frame(SATELLITE_CALLSIGN, EARTH_CALLSIGN, payload)
        assert frame[AX25_HEADER_SIZE:] == payload, (
            "Payload not found at expected position in frame"
        )


# Test 2: Callsign Validity
class TestCallsignValidity:

    def test_earth_callsign_is_valid_length(self): # earth station callsign should be 6 characters.
        assert len(EARTH_CALLSIGN) == 6, (
            f"Expected callsign length 6, got {len(EARTH_CALLSIGN)}"
        )

    def test_satellite_callsign_is_valid_length(self): # satellite callsign should be 6 characters.
        assert len(SATELLITE_CALLSIGN) == 6, (
            f"Expected callsign length 6, got {len(SATELLITE_CALLSIGN)}"
        )

    def test_earth_callsign_is_ascii(self): # earth station callsign should be valid ASCII.
        assert EARTH_CALLSIGN.isascii(), "Earth callsign contains non-ASCII characters"

    def test_satellite_callsign_is_ascii(self): # satellite callsign should be valid ASCII.
        assert SATELLITE_CALLSIGN.isascii(), "Satellite callsign contains non-ASCII characters"

# Test 3: Uplink and Downlink (will require utils.py)
class TestUplinkDownlink:

    def test_uplink_frame_conforms_to_ax25(self): # a frame sent from Earth PC to VIOLET2 OBC should conform to AX.25.
        payload = b"A" * 100
        frame = build_ax25_frame(EARTH_CALLSIGN, SATELLITE_CALLSIGN, payload)
        assert validate_ax25_frame(frame), "Uplink frame does not conform to AX.25 standard"

    def test_downlink_frame_conforms_to_ax25(self): # a frame sent from VIOLET2 OBC to Earth PC should conform to AX.25.
        payload = b"A" * 100
        frame = build_ax25_frame(SATELLITE_CALLSIGN, EARTH_CALLSIGN, payload)
        assert validate_ax25_frame(frame), "Downlink frame does not conform to AX.25 standard"

    def test_uplink_frame_can_be_parsed(self): # a parsed uplink frame should contain the correct source and destination.
        payload = b"A" * 100
        frame = build_ax25_frame(EARTH_CALLSIGN, SATELLITE_CALLSIGN, payload)
        parsed = parse_ax25_frame(frame)
        assert parsed["source"] == EARTH_CALLSIGN, "Parsed source callsign mismatch"
        assert parsed["destination"] == SATELLITE_CALLSIGN, "Parsed destination callsign mismatch"

    def test_downlink_frame_can_be_parsed(self): # a parsed downlink frame should contain the correct source and destination.
        payload = b"A" * 100
        frame = build_ax25_frame(SATELLITE_CALLSIGN, EARTH_CALLSIGN, payload)
        parsed = parse_ax25_frame(frame)
        assert parsed["source"] == SATELLITE_CALLSIGN, "Parsed source callsign mismatch"
        assert parsed["destination"] == EARTH_CALLSIGN, "Parsed destination callsign mismatch"

# Test 4: Loopback Communication (no hardware)
class TestLoopbackCommunication:

    def test_frame_survives_udp_loopback(self): # a frame sent over UDP loopback should be received intact.
        send_host = "127.0.0.1"
        send_port = 29000
        payload = b"A" * 100
        frame = _build_raw_frame(SATELLITE_CALLSIGN, EARTH_CALLSIGN, payload)

        received = []

        def listen():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((send_host, send_port))
            sock.settimeout(3)
            try:
                data, _ = sock.recvfrom(1024)
                received.append(data)
            except socket.timeout:
                pass
            finally:
                sock.close()

        listener = threading.Thread(target=listen)
        listener.start()
        time.sleep(0.1)

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(frame, (send_host, send_port))
        sock.close()

        listener.join(timeout=4)

        assert len(received) == 1, "No frame received over UDP loopback"
        assert received[0] == frame, "Received frame does not match sent frame"

    def test_payload_extractable_from_loopback_frame(self): # payload should be extractable from a frame received over UDP loopback.
        send_host = "127.0.0.1"
        send_port = 29001
        payload = b"hello VIOLET2" + b"\x00" * 87  # pad to 100 bytes
        frame = _build_raw_frame(SATELLITE_CALLSIGN, EARTH_CALLSIGN, payload)

        received = []

        def listen():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((send_host, send_port))
            sock.settimeout(3)
            try:
                data, _ = sock.recvfrom(1024)
                received.append(data)
            except socket.timeout:
                pass
            finally:
                sock.close()

        listener = threading.Thread(target=listen)
        listener.start()
        time.sleep(0.1)

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(frame, (send_host, send_port))
        sock.close()

        listener.join(timeout=4)

        assert len(received) == 1, "No frame received over UDP loopback"
        extracted_payload = received[0][AX25_HEADER_SIZE:]
        assert extracted_payload == payload, "Extracted payload does not match original"
