import socket
import os
from time import sleep
from ax25_utils import validate_ax25_header

# UDP Configuration
RECEIVE_HOST = "127.0.0.1"
RECEIVE_PORT = int(os.environ.get("VIOLET2_RECEIVE_PORT", "27001"))

UDP_HOST = "127.0.0.1" 
UDP_PORT = int(os.environ.get("VIOLET2_UDP_PORT", "27000"))

# AX.25 Layer 1
AX25_HEADER_LEN     = 16
AX25_CONTROL        = "03"
AX25_FCS            = "0000"
AX25_PID            = "F0"

EARTH_CALLSIGN      = "VE9CNB"
EARTH_SSID          = "E0"
SATELLITE_CALLSIGN  = "VE9VLT"
SATELLITE_SSID      = "60"

SOURCE_CALLSIGN     = SATELLITE_CALLSIGN
SOURCE_SSID         = SATELLITE_SSID   
DEST_CALLSIGN       = EARTH_CALLSIGN
DEST_SSID           = EARTH_SSID       

# VIOLET2 Layer 2
VIOLET2_HEADER_LEN          = 8 # Bytes
VIOLET2_MIN_APP_DATA        = 92
VIOLET2_MAX_APP_DATA        = 248
VIOLET2_RECEIVE_BUFFER_SIZE = 2048

# Padding Bytes
PAD_BYTE_A  = 0xAA
PAD_BYTE_B  = 0x55

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

_sequenceNumber = 0

def _getNextSequenceNumber():
    """
    Get the next sequence number for VIOLET2 packets, wrapping around at 256.
    Returns: the next sequence number as an integer (0-255)
    """
    global _sequenceNumber
    value = _sequenceNumber
    _sequenceNumber = (_sequenceNumber + 1) % 256 # wrap
    return value

def _violet2Checksum(headerWithoutChecksum: bytes) -> int:
    """
    Calculate the XOR checksum for the VIOLET2 header.
    Returns: the checksum as an integer (0-255)
    """
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
    """
    Build the VIOLET2 Layer 2 header with the given parameters and calculate the checksum.
    Returns: the complete VIOLET2 header as bytes (8 bytes total)
    """
    headerCore = bytes([
        messageType,
        sequenceNumber,
        totalPackets,
        packetIndex,
        (payloadLength >> 8) & 0xFF,
        payloadLength & 0xFF,
    ])
    checksum = _violet2Checksum(headerCore)
    return headerCore + bytes([checksum, 0x00]) # reserved byte set to 0x00 for future implementation and clean 8 byte header length

def _padApplicationData(data: bytes) -> bytes:
    """
    Pad the application data to ensure it is at least VIOLET2_MIN_APP_DATA bytes long.
    If the data is shorter than the minimum, it will be padded with an alternating pattern of 0xAA and 0x55 bytes.
    Returns: the original data if it meets the minimum length, or the padded data if it was too short.
    """
    if len(data) >= VIOLET2_MIN_APP_DATA: # if data is already long enough, return as is
        return data

    padNeeded = VIOLET2_MIN_APP_DATA - len(data) # calculate how many padding bytes are needed
    pattern = bytes([ # create the alternating pattern of 0xAA and 0x55 for padding
        PAD_BYTE_A if i % 2 == 0 else PAD_BYTE_B
        for i in range(padNeeded)
    ])
    return data + pattern # append the padding to the original data and return

def _fragmentData(data: bytes) -> list[bytes]:
    """
    Split data into chunks of at most VIOLET2_MAX_APP_DATA bytes.
    Returns: a list of byte strings, each containing at most VIOLET2_MAX_APP_DATA bytes.
    """
    fragments = [] # create a list to hold the fragments
    offset = 0 # start at the beginning of the data

    while offset < len(data): # loop through all data
        fragments.append(data[offset:offset + VIOLET2_MAX_APP_DATA]) # take a chunk of data and add to fragments list
        offset += VIOLET2_MAX_APP_DATA # move the offset forward by the chunk size for the next iteration
    
    return fragments

def parseViolet2Packet(rawData: bytes) -> dict:
    """
    Parse a raw byte string as a VIOLET2 packet, extracting the header fields and application data.
    Returns: a dict containing the parsed VIOLET2 packet information, or an error message if parsing fails.
    """
    if len(rawData) < VIOLET2_HEADER_LEN: # if the raw data is too short to even contain a full VIOLET2 header, return an error
        return {"error": "Packet too short for VIOLET2 header"}

    # Extract header fields from the first 8 bytes of rawData
    messageType    = rawData[0]
    sequenceNumber = rawData[1]
    totalPackets   = rawData[2]
    packetIndex    = rawData[3]
    payloadLength  = (rawData[4] << 8) | rawData[5]
    checksum       = rawData[6]

    # Validate that the payload length matches the actual data length
    expectedChecksum = _violet2Checksum(rawData[0:6]) # calculate expected checksum from the header fields (excluding the checksum byte itself)
    if checksum != expectedChecksum: # if the checksum does not match the expected value, return an error
        return {
            "error": f"Checksum mismatch: got 0x{checksum:02X}, "
                     f"expected 0x{expectedChecksum:02X}"
        }

    # Extract the application data based on the payload length specified in the header
    applicationData = rawData[VIOLET2_HEADER_LEN:VIOLET2_HEADER_LEN + payloadLength]

    return { # return a dict with all the parsed information from the VIOLET2 packet
        "msg_type":    messageType,
        "seq_num":     sequenceNumber,
        "total_pkt":   totalPackets,
        "pkt_idx":     packetIndex,
        "payload_len": payloadLength,
        "checksum_ok": True,
        "payload":     applicationData,
    }

def isAx25UplinkPacket(rawData: bytes) -> bool:
    """
    Validate that the raw data conforms to the expected AX.25 header for an uplink packet from Earth to VIOLET2.
    Returns: True if the AX.25 header is valid and matches the expected values for an incoming uplink packet, False otherwise.
    """
    return validate_ax25_header(
        raw_data=rawData,
        expected_dest_callsign=SATELLITE_CALLSIGN,
        expected_dest_ssid_hex=SATELLITE_SSID,
        expected_src_callsign=EARTH_CALLSIGN,
        expected_src_ssid_hex=EARTH_SSID,
        expected_control_hex=AX25_CONTROL,
        expected_pid_hex=AX25_PID,
        header_len=AX25_HEADER_LEN,
    )

def violet2ProtocolBuilder(payload: bytes) -> list[bytes]:
    """
    Build VIOLET2 Layer 2 packets from the given application data payload, handling fragmentation based on the maximum allowed size.
    Returns: a list of byte strings, each representing a complete VIOLET2 packet.
    """
    sequenceNumber = _getNextSequenceNumber() # get the next available seq_num for the VIOLET2 header

    # if payload fits in a single packet, use RESP_SINGLE message type
    if len(payload) <= VIOLET2_MAX_APP_DATA: 
        payloadLength = len(payload) # calculate the actual payload length (before padding)
        applicationData = _padApplicationData(payload) # pad the application data
        header = _buildViolet2Header( # build the VIOLET2 header for a single packet response
            messageType=RESP_SINGLE,
            sequenceNumber=sequenceNumber,
            totalPackets=1,
            packetIndex=0,
            payloadLength=payloadLength,
        )
        return [header + applicationData] 

    # if payload is too large for a single packet, fragment it and use RESP_MULTI_START, RESP_MULTI_CONT, and RESP_MULTI_END message types
    fragments = _fragmentData(payload) # split payload into fragments 
    totalPackets = len(fragments) # calculate how many packets will be needed to send the full payload
    
    # loop through each fragment, build header based on position in the sequence, and add to packets list
    packets = [] # fragment with header storage list
    for index, chunk in enumerate(fragments): 
        
        if index == 0: # first packet = RESP_MULTI_START message type
            messageType = RESP_MULTI_START

        elif index == totalPackets - 1: # last packet = RESP_MULTI_END message type
            messageType = RESP_MULTI_END

        else: # middle packets = RESP_MULTI_CONT message type
            messageType = RESP_MULTI_CONT

        header = _buildViolet2Header( # build the VIOLET2 header for this fragment based on its position in the sequence
            messageType=messageType,
            sequenceNumber=sequenceNumber,
            totalPackets=totalPackets,
            packetIndex=index,
            payloadLength=len(chunk),
        )
        packets.append(header + _padApplicationData(chunk)) # pad the application data for this fragment, combine with header, and add to packets list

    return packets

def ax25Send(payload: bytes, txSocket: socket.socket | None = None) -> bytes:
    """
    Build an AX.25 packet with the given payload and send it over UDP to the configured address and port for transmission.
    Returns: the complete AX.25 packet that was sent, as bytes.
    """
    ax25Packet = (
        DEST_CALLSIGN.encode('ascii') +
        bytes.fromhex(DEST_SSID) +
        SOURCE_CALLSIGN.encode('ascii') +
        bytes.fromhex(SOURCE_SSID) +
        bytes.fromhex(AX25_CONTROL) +
        bytes.fromhex(AX25_PID) +
        payload
    )

    print(f"[VIOLET2 TRANSMISSION]: {ax25Packet.hex()}\n")
   
    # use a caller-provided socket when available, otherwise use a temporary one.
    if txSocket is not None:
        txSocket.sendto(ax25Packet, (UDP_HOST, UDP_PORT))
    else:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(ax25Packet, (UDP_HOST, UDP_PORT))
        sock.close()
    
    return ax25Packet