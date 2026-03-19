from earth_utils import (
    _violet2Checksum,
    _buildViolet2Header,
    _padApplicationData,
    _fragmentData,
    parseViolet2Response,
    violet2ProtocolBuilder,
    ax25Send as ax25_send_earth,
    VIOLET2_HEADER_LEN,
    VIOLET2_MIN_APP_DATA,
    VIOLET2_MAX_APP_DATA,
    AX25_HEADER_LEN,
    RESP_SINGLE,
    RESP_MULTI_START,
    RESP_MULTI_CONT,
    RESP_MULTI_END,
    MSG_CMD_SINGLE,
    MSG_CMD_MULTI_START,
    MSG_CMD_MULTI_CONT,
    MSG_CMD_MULTI_END,
)

from violet2_utils import (
    parseViolet2Packet,
    violet2ProtocolBuilder as violet2_protocol_builder_v2,
    ax25Send as ax25_send_violet2,
)

# Test Wrapper Functions

def build_ax25_frame(source: str, destination: str, payload: bytes) -> bytes:
    from earth_utils import AX25_CONTROL, AX25_PID

    ssid_by_callsign = {
        EARTH_CALLSIGN: EARTH_SSID_BYTES,
        SATELLITE_CALLSIGN: SATELLITE_SSID_BYTES,
    }
    source_ssid = ssid_by_callsign[source]
    destination_ssid = ssid_by_callsign[destination]
    
    return (
        destination.encode('ascii') +
        destination_ssid +
        source.encode('ascii') +
        source_ssid +
        bytes.fromhex(AX25_CONTROL) +
        bytes.fromhex(AX25_PID) +
        payload
    )

def parse_ax25_frame(frame: bytes) -> dict:
    if len(frame) < AX25_HEADER_LEN:
        return {"error": "Frame too short"}
    
    destination = frame[0:6].decode('ascii', errors='replace')
    dest_ssid = frame[6]
    source = frame[7:13].decode('ascii', errors='replace')
    source_ssid = frame[13]
    control = frame[14]
    pid = frame[15]
    payload = frame[AX25_HEADER_LEN:]
    
    return {
        "destination": destination,
        "dest_ssid": dest_ssid,
        "source": source,
        "source_ssid": source_ssid,
        "control": control,
        "pid": pid,
        "payload": payload,
    }

def validate_ax25_frame(frame: bytes) -> bool:
    if len(frame) < AX25_HEADER_LEN:
        return False
    
    parsed = parse_ax25_frame(frame)
    if "error" in parsed:
        return False
    
    return True

def pad_payload(payload: bytes) -> bytes:
    return _padApplicationData(payload)

def validate_payload(payload: bytes) -> bool:
    return VIOLET2_MIN_APP_DATA <= len(payload) <= VIOLET2_MAX_APP_DATA

def fragment_payload(payload: bytes) -> list[bytes]:
    return _fragmentData(payload)

def reassemble_payload(fragments: list[bytes]) -> bytes:
    return b"".join(fragments)

def build_violet2_packet(payload: bytes, message_type: int = None) -> bytes:
    if message_type is None:
        message_type = MSG_CMD_SINGLE
    
    packets = violet2ProtocolBuilder(payload)
    if packets:
        return packets[0]  # Return first packet for single-packet messages
    return b""

def parse_violet2_packet_safe(raw_data: bytes) -> dict:
    return parseViolet2Response(raw_data)

# Test Constants

EARTH_CALLSIGN = "VE9CNB"
SATELLITE_CALLSIGN = "VE9VLT"
EARTH_SSID_BYTES = bytes.fromhex("E0")
SATELLITE_SSID_BYTES = bytes.fromhex("60")
DEST_SSID_BYTES = SATELLITE_SSID_BYTES
SRC_SSID_BYTES = EARTH_SSID_BYTES
CONTROL_BYTE = bytes.fromhex("03")
PID_BYTE = bytes.fromhex("F0")

__all__ = [
    # wrapper functions
    'build_ax25_frame',
    'parse_ax25_frame',
    'validate_ax25_frame',
    'pad_payload',
    'validate_payload',
    'fragment_payload',
    'reassemble_payload',
    'build_violet2_packet',
    'parse_violet2_packet_safe',
    # imported functions
    '_violet2Checksum',
    '_buildViolet2Header',
    '_padApplicationData',
    '_fragmentData',
    'parseViolet2Response',
    'parseViolet2Packet',
    'violet2ProtocolBuilder',
    # constants
    'VIOLET2_HEADER_LEN',
    'VIOLET2_MIN_APP_DATA',
    'VIOLET2_MAX_APP_DATA',
    'AX25_HEADER_LEN',
    'RESP_SINGLE',
    'RESP_MULTI_START',
    'RESP_MULTI_CONT',
    'RESP_MULTI_END',
    'MSG_CMD_SINGLE',
    'MSG_CMD_MULTI_START',
    'MSG_CMD_MULTI_CONT',
    'MSG_CMD_MULTI_END',
    # test constants
    'EARTH_CALLSIGN',
    'SATELLITE_CALLSIGN',
    'EARTH_SSID_BYTES',
    'SATELLITE_SSID_BYTES',
    'DEST_SSID_BYTES',
    'SRC_SSID_BYTES',
    'CONTROL_BYTE',
    'PID_BYTE',
]
