# VIOLET2 Configuration Constants

# UDP Configuration
# Set the UDP receive address and port
RECEIVE_HOST = "127.0.0.1"
RECEIVE_PORT = 27000

# Set the UDP server addresses and ports (transmit)
UDP_HOST = "127.0.0.1" 
UDP_PORT = 27001

# AX.25 Layer 1
AX25_HEADER_LEN     = 16
AX25_CONTROL        = "00"
AX25_FCS            = "0000"
AX25_PID            = "F0"

SOURCE_CALLSIGN     = "VE9CNB"
SOURCE_SSID         = "E0"   # Bit 7 = 1, destination SSID
DEST_CALLSIGN       = "VE9VLT"
DEST_SSID           = "60"   # Bit 7 = 0, source SSID

# VIOLET2 Layer 2
VIOLET2_HEADER_LEN  = 8
VIOLET2_MIN_APP_DATA = 92
VIOLET2_MAX_APP_DATA = 248

PAD_BYTE_A           = 0xAA
PAD_BYTE_B           = 0x55
INTER_PACKET_DELAY   = 0.5  # seconds between packets in a multi-packet response

# Message Types
MSG_CMD_SINGLE      = 0x01
MSG_CMD_MULTI_START = 0x02
MSG_CMD_MULTI_CONT  = 0x03
MSG_CMD_MULTI_END   = 0x04
RESP_SINGLE         = 0x05
RESP_MULTI_START    = 0x06
RESP_MULTI_CONT     = 0x07
RESP_MULTI_END      = 0x08
MSG_ACK             = 0xA0
MSG_NACK            = 0xA1
MSG_PING            = 0xB0
MSG_PONG            = 0xB1

# VIOLET2 Protocol Utilities

import socket

_sequenceNumber = 0

def _getNextSequenceNumber(): # increments and returns a global sequence number for VIOLET2 packets, wraps at 256.
    global _sequenceNumber
    value = _sequenceNumber
    _sequenceNumber = (_sequenceNumber + 1) % 256 # wrap
    return value

def _violet2Checksum(headerWithoutChecksum: bytes) -> int: # XOR checksum over the first 6 VIOLET2 header bytes.
    checksum = 0
    for byte in headerWithoutChecksum:
        checksum ^= byte
    return checksum

def _buildViolet2Header(
    messageType: int,
    sequenceNumber: int,
    totalPackets: int,
    packetIndex: int,
    payloadLength: int,
) -> bytes:
    headerCore = bytes([
        messageType,
        sequenceNumber,
        totalPackets,
        packetIndex,
        (payloadLength >> 8) & 0xFF,
        payloadLength & 0xFF,
    ])
    checksum = _violet2Checksum(headerCore)
    return headerCore + bytes([checksum, 0x00])

def _padApplicationData(data: bytes) -> bytes: # pad application data using alternating 0xAA 0x55 pattern.
    if len(data) >= VIOLET2_MIN_APP_DATA:
        return data
    padNeeded = VIOLET2_MIN_APP_DATA - len(data)
    pattern = bytes([
        PAD_BYTE_A if i % 2 == 0 else PAD_BYTE_B
        for i in range(padNeeded)
    ])
    return data + pattern

def _fragmentData(data: bytes) -> list: # split data into chunks of at most VIOLET2_MAX_APP_DATA bytes.
    fragments = []
    offset = 0
    while offset < len(data):
        fragments.append(
            data[offset:offset + VIOLET2_MAX_APP_DATA]
        )
        offset += VIOLET2_MAX_APP_DATA
    return fragments

def parseViolet2Packet(rawData: bytes) -> dict: # parse VIOLET2 Layer 2 header and extract application data (AX.25 header already stripped)
    if len(rawData) < VIOLET2_HEADER_LEN:
        return {"error": "Packet too short for VIOLET2 header"}

    messageType    = rawData[0]
    sequenceNumber = rawData[1]
    totalPackets   = rawData[2]
    packetIndex    = rawData[3]
    payloadLength  = (rawData[4] << 8) | rawData[5]
    checksum       = rawData[6]

    expectedChecksum = _violet2Checksum(rawData[0:6])
    if checksum != expectedChecksum:
        return {
            "error": f"Checksum mismatch: got 0x{checksum:02X}, "
                     f"expected 0x{expectedChecksum:02X}"
        }

    applicationData = rawData[VIOLET2_HEADER_LEN:VIOLET2_HEADER_LEN + payloadLength]

    return {
        "msg_type":    messageType,
        "seq_num":     sequenceNumber,
        "total_pkt":   totalPackets,
        "pkt_idx":     packetIndex,
        "payload_len": payloadLength,
        "checksum_ok": True,
        "payload":     applicationData,
    }

def isAx25Packet(rawData: bytes) -> bool: # validate AX.25 header for expected callsigns/control/pid
    if len(rawData) < AX25_HEADER_LEN:
        return False
    dest_ok = rawData[0:6] == DEST_CALLSIGN.encode('ascii')
    dest_ssid_ok = rawData[6:7] == bytes.fromhex(DEST_SSID)
    src_ok = rawData[7:13] == SOURCE_CALLSIGN.encode('ascii')
    src_ssid_ok = rawData[13:14] == bytes.fromhex(SOURCE_SSID)
    control_ok = rawData[14:15] == bytes.fromhex(AX25_CONTROL)
    pid_ok = rawData[15:16] == bytes.fromhex(AX25_PID)
    return dest_ok and dest_ssid_ok and src_ok and src_ssid_ok and control_ok and pid_ok

def violet2ProtocolBuilder(payload: bytes) -> list:
    sequenceNumber = _getNextSequenceNumber()

    if len(payload) <= VIOLET2_MAX_APP_DATA:
        payloadLength = len(payload)
        applicationData = _padApplicationData(payload)
        header = _buildViolet2Header(
            messageType=RESP_SINGLE,
            sequenceNumber=sequenceNumber,
            totalPackets=1,
            packetIndex=0,
            payloadLength=payloadLength,
        )
        return [header + applicationData]

    fragments = _fragmentData(payload)
    totalPackets = len(fragments)
    packets = []
    for index, chunk in enumerate(fragments):
        if index == 0:
            messageType = RESP_MULTI_START
        elif index == totalPackets - 1:
            messageType = RESP_MULTI_END
        else:
            messageType = RESP_MULTI_CONT

        header = _buildViolet2Header(
            messageType=messageType,
            sequenceNumber=sequenceNumber,
            totalPackets=totalPackets,
            packetIndex=index,
            payloadLength=len(chunk),
        )
        packets.append(header + _padApplicationData(chunk))
    return packets

def ax25Send(payload: bytes) -> bytes: # combine into a single byte string
    ax25Packet = (
        DEST_CALLSIGN.encode('ascii') +
        bytes.fromhex(DEST_SSID) +
        SOURCE_CALLSIGN.encode('ascii') +
        bytes.fromhex(SOURCE_SSID) +
        bytes.fromhex(AX25_CONTROL) +
        bytes.fromhex(AX25_PID) +
        payload
    )

    print(f"VIOLET2 TRANSMISSION: {ax25Packet.hex()}\n")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(ax25Packet, (UDP_HOST, UDP_PORT))
    sock.close()
    return ax25Packet
