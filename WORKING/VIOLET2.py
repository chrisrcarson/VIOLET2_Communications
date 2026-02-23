import socket
from time import sleep
import subprocess
from VIOLET2_Constants import *

# Set the UDP receive address and port
receive_host = "127.0.0.1"
receive_port = 27000

# Set the UDP server addresses and ports (transmit)
UDP_HOST = "127.0.0.1"
UDP_PORT = 27002

# 7 bytes allocated for each callsign, byte 7 for SSID in Hex
#SourceCallsign = "VE9VLT"
#SourceSSID = "E0" # Bit 7 set to 1 indicating destination SSID **
#DestinationCallsign = "VE9CNB"
#DestinationSSID = "60" # Bit 7 set to 0 indicating source SSID **
#Control = "00" # Control byte
#FCS = "0000"
#PID = "F0" # PID Byte

_seq_num = 0


def _next_seq_num(): # increments and returns a global sequence number for VIOLET2 packets, wraps at 256.
    global _seq_num
    val = _seq_num
    _seq_num = (_seq_num + 1) % 256 # wrap
    return val


def _violet2_checksum(headerWithoutChecksum: bytes) -> int: # XOR checksum over the first 6 VIOLET2 header bytes.
    check = 0
    for b in headerWithoutChecksum:
        check ^= b
    return check


def _build_violet2_header(
    msg_type: int,
    seq_num: int,
    total_pkt: int,
    pkt_idx: int,
    payload_len: int,
) -> bytes:

    header_core = bytes([
        msg_type,
        seq_num,
        total_pkt,
        pkt_idx,
        (payload_len >> 8) & 0xFF,  # shifts all bits 8 places to the right, leaving only the high byte, then masks with 0xFF to ensure it's a single byte
        payload_len & 0xFF, # masks payload_len with 0xFF to get the low byte (last 8 bits)
    ])
    checksum = _violet2_checksum(header_core) # XOR across bytes 0-5
    return header_core + bytes([checksum, 0x00]) # append checksum + reserved byte to complete the 8-byte header


def _pad_application_data(data: bytes) -> bytes: # pad application data using alternating 0xAA 0x55 pattern.
    if len(data) >= VIOLET2_MIN_APP_DATA:
        return data
    pad_needed = VIOLET2_MIN_APP_DATA - len(data)
    pattern = bytes([
        PAD_BYTE_A if i % 2 == 0 else PAD_BYTE_B
        for i in range(pad_needed)
    ])
    return data + pattern


def _fragment_data(data: bytes) -> list[bytes]: # split data into chunks of at most VIOLET2_MAX_APP_DATA bytes.
    fragments = [] # list to store chunks
    offset = 0 # tracks current pos in data
    while offset < len(data):
        fragments.append(
            data[offset:offset + VIOLET2_MAX_APP_DATA] # slice out the next chunk (up to VIOLET2_MAX_APP_DATA bytes)
        )
        offset += VIOLET2_MAX_APP_DATA # advance position by 248, even if last chunk was smaller
    return fragments # return the list of stored chunks


def parse_violet2_packet(raw: bytes) -> dict: # parse VIOLET2 Layer 2 header and extract application data (AX.25 header already stripped)
    if len(raw) < VIOLET2_HEADER_LEN:
        return {"error": "Packet too short for VIOLET2 header"}

    msg_type    = raw[0]
    seq_num     = raw[1]
    total_pkt   = raw[2]
    pkt_idx     = raw[3]
    payload_len = (raw[4] << 8) | raw[5] # reconstruct 2-byte payload length from high and low bytes
    checksum    = raw[6]
    # raw[7] is reserved

    expectedCheck = _violet2_checksum(raw[0:6]) # recompute checksum over the same 6 bytes
    if checksum != expectedCheck:
        return {
            "error": f"Checksum mismatch: got 0x{checksum:02X}, "
                     f"expected 0x{expectedCheck:02X}"
        }

    app_data = raw[VIOLET2_HEADER_LEN:VIOLET2_HEADER_LEN + payload_len] # strip padding using true payload length

    return {
        "msg_type":    msg_type,
        "seq_num":     seq_num,
        "total_pkt":   total_pkt,
        "pkt_idx":     pkt_idx,
        "payload_len": payload_len,
        "checksum_ok": True,
        "payload":     app_data,
    }


def VIOLET2_Protocol_Builder(payload: bytes) -> list[bytes]:
    seq = _next_seq_num() # get the next sequence number for message

    if len(payload) <= VIOLET2_MAX_APP_DATA: # if payload fits in a single packet
        payload_len = len(payload) # store true length before padding
        app_data = _pad_application_data(payload) # pad to minimum, if needed
        header = _build_violet2_header( # build header with fields for a single-packet response
            msg_type=RESP_SINGLE, # response type instead of command type
            seq_num=seq,
            total_pkt=1, # only one packet in this message
            pkt_idx=0, # first (and only) packet
            payload_len=payload_len,
        )
        return [header + app_data] # list used for consistency with fragmented path

    fragments = _fragment_data(payload) # payload too large, split into VIOLET2_MAX_APP_DATA byte chunks
    total_pkt = len(fragments) # total number of fragments the receiver should expect
    packets = []
    for idx, chunk in enumerate(fragments): # build a packet for each fragment
        if idx == 0:
            msg_type = RESP_MULTI_START # first fragment
        elif idx == total_pkt - 1:
            msg_type = RESP_MULTI_END # last fragment
        else:
            msg_type = RESP_MULTI_CONT # middle fragment, if needed

        header = _build_violet2_header(
            msg_type=msg_type,
            seq_num=seq, # all fragments share the same seq_num so receiver can reassemble
            total_pkt=total_pkt,
            pkt_idx=idx, # position of fragment in the sequence
            payload_len=len(chunk), # real length of chunk before padding
        )
        packets.append(header + _pad_application_data(chunk)) # pad chunk and attach header
    return packets # list of complete VIOLET2 info payloads, one per fragment


def AX25_Send(payload: bytes) -> bytes: # combine into a single byte string
    AX25Packet = (
        # header
        DEST_CALLSIGN.encode('ascii') +
        bytes.fromhex(DEST_SSID) +
        SOURCE_CALLSIGN.encode('ascii') +
        bytes.fromhex(SOURCE_SSID) +
        bytes.fromhex(AX25_CONTROL) +
        bytes.fromhex(AX25_PID) +
        # data
        payload
    )

    print(f"VIOLET2 TRANSMISSION: {AX25Packet.hex()}\n") # DEBUGGING

    sleep(2)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # push over udp
    sock.sendto(AX25Packet, (UDP_HOST, UDP_PORT))
    sock.close()
    return AX25Packet


# fragment reassembly buffer, keyed by seq_num
reassembly_buffer = {}

receive_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
receive_socket.bind((receive_host, receive_port))

while True:
    data, addr = receive_socket.recvfrom(512) # receive raw AX.25 packet
    print(f"[Received Data]: {data.hex()}")

    violet2_raw = data[AX25_HEADER_LEN:] # strip AX.25 header before parsing VIOLET2 layer
    parsed = parse_violet2_packet(violet2_raw)

    if "error" in parsed:
        print(f"[VIOLET2 Error]: {parsed['error']}")
        continue

    msg_type = parsed["msg_type"]
    seq      = parsed["seq_num"]
    print(f"[VIOLET2 Header]: type=0x{msg_type:02X}  seq={seq}  "
          f"pkt {parsed['pkt_idx']+1}/{parsed['total_pkt']}  "
          f"payload_len={parsed['payload_len']}  checksum=OK")

    if msg_type == MSG_CMD_SINGLE: # single packet command, execute immediately
        command = parsed["payload"].decode('ascii', errors='replace')

    elif msg_type == MSG_CMD_MULTI_START: # first fragment, start reassembly buffer for this seq
        reassembly_buffer[seq] = {
            "total_pkt": parsed["total_pkt"],
            "fragments": {parsed["pkt_idx"]: parsed["payload"]}
        }
        continue

    elif msg_type in (MSG_CMD_MULTI_CONT, MSG_CMD_MULTI_END): # middle or final fragment, add to buffer
        if seq not in reassembly_buffer:
            print(f"[VIOLET2 Error]: received fragment for unknown seq {seq}, discarding")
            continue
        reassembly_buffer[seq]["fragments"][parsed["pkt_idx"]] = parsed["payload"]

        if msg_type == MSG_CMD_MULTI_END: # final fragment, check if all fragments are present
            buf = reassembly_buffer[seq]
            if len(buf["fragments"]) < buf["total_pkt"]: # still missing fragments, wait for retransmit
                print(f"[VIOLET2]: seq {seq} incomplete, "
                      f"got {len(buf['fragments'])}/{buf['total_pkt']} fragments")
                continue
            # reassemble in order and decode
            command = b"".join(
                buf["fragments"][i] for i in range(buf["total_pkt"])
            ).decode('ascii', errors='replace')
            del reassembly_buffer[seq] # clean up buffer once reassembled
        else:
            continue

    else:
        print(f"[VIOLET2]: unhandled message type 0x{msg_type:02X}")
        continue

    # execute command and send response
    print(f"Command: {command}")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    print(f"Command output: {result.stdout}")

    response = result.stdout.encode('ascii')
    violet2_packets = VIOLET2_Protocol_Builder(response)

    if len(violet2_packets) > 1:
        print(f"Fragmenting response into {len(violet2_packets)} packets...")

    for info in violet2_packets:
        AX25_Send(info)