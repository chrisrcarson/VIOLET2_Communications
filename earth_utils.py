import socket
import os

# Earth Terminal Configuration Constants

# UDP Configuration
RECEIVE_HOST = "127.0.0.1"
RECEIVE_PORT = 27000
UDP_HOST = "127.0.0.1" 
UDP_PORT = 27001

# AX.25 Layer 1 Configuration
AX25_HEADER_LEN     = 16
AX25_CONTROL        = "00"
AX25_FCS            = "0000"
AX25_PID            = "F0"

SOURCE_CALLSIGN     = "VE9CNB"
SOURCE_SSID         = "E0"
DEST_CALLSIGN       = "VE9VLT"
DEST_SSID           = "60"

# VIOLET2 Layer 2 Protocol Configuration
VIOLET2_HEADER_LEN  = 8
VIOLET2_MIN_APP_DATA = 92
VIOLET2_MAX_APP_DATA = 248

PAD_BYTE_A          = 0xAA
PAD_BYTE_B          = 0x55

# VIOLET2 Message Types
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

def _padApplicationData(data: bytes) -> bytes: # pad application data using alternating 0xAA 0x55 pattern. 
    if len(data) >= VIOLET2_MIN_APP_DATA: 
        return data
    padNeeded = VIOLET2_MIN_APP_DATA - len(data)
    pattern = bytes([
        PAD_BYTE_A if i % 2 == 0 else PAD_BYTE_B
        for i in range(padNeeded)
    ])
    return data + pattern

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

def _fragmentData(data: bytes) -> list[bytes]:
    fragments = []
    offset = 0
    while offset < len(data): 
        fragments.append(
            data[offset:offset + VIOLET2_MAX_APP_DATA]
        )
        offset += VIOLET2_MAX_APP_DATA
    return fragments

def violet2ProtocolBuilder(payload: bytes) -> list[bytes]:
    sequenceNumber = _getNextSequenceNumber()

    if len(payload) <= VIOLET2_MAX_APP_DATA:
        payloadLength = len(payload)
        applicationData = _padApplicationData(payload)
        header = _buildViolet2Header(
            messageType=MSG_CMD_SINGLE,
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
            messageType = MSG_CMD_MULTI_START
        elif index == totalPackets - 1:
            messageType = MSG_CMD_MULTI_END
        else:
            messageType = MSG_CMD_MULTI_CONT

        header = _buildViolet2Header(
            messageType=messageType,
            sequenceNumber=sequenceNumber,
            totalPackets=totalPackets,
            packetIndex=index,
            payloadLength=len(chunk),
        )
        packets.append(header + _padApplicationData(chunk))
    return packets

def parseViolet2Response(rawData: bytes) -> dict:
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

def ax25Send(payload: bytes) -> bytes:
    ax25Packet = (
        DEST_CALLSIGN.encode('ascii') +
        bytes.fromhex(DEST_SSID) +
        SOURCE_CALLSIGN.encode('ascii') +
        bytes.fromhex(SOURCE_SSID) +
        bytes.fromhex(AX25_CONTROL) +
        bytes.fromhex(AX25_PID) +
        payload 
    )

    print(f"EARTH PC TRANSMISSION: {ax25Packet.hex()}\n")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(ax25Packet, (UDP_HOST, UDP_PORT))
    sock.close()
    return ax25Packet

# Earth Terminal Utilities

def clearTerminal():
    os.system('cls' if os.name == 'nt' else 'clear')

def setupCommandHistory():
    import readline
    
    historyFile = os.path.expanduser('~/.violet2_history')
    readline.set_history_length(100)
    
    if os.path.exists(historyFile):
        try:
            readline.read_history_file(historyFile)
        except:
            pass
    
    return historyFile

def saveCommandHistory(historyFile):
    if historyFile is None:
        return
    
    import readline
    try:
        readline.write_history_file(historyFile)
    except:
        pass

# File Download Function
def downloadFile(userInput: str, receiveSocket: socket.socket) -> bool:
    
    # Create tmp directory in script's directory if it doesn't exist
    scriptDir = os.path.dirname(os.path.abspath(__file__))
    tmpDir = os.path.join(scriptDir, "tmp")
    try:
        os.makedirs(tmpDir, exist_ok=True)
    except Exception as e:
        print(f"Error creating tmp directory: {e}")
        return False
    
    parts = userInput.split(" ", 2)
    if len(parts) < 2:
        print("Usage: download <remote_path> [local_path]")
        print(f"  download /path/to/file.txt              - save to tmp/ as 'file.txt'")
        print(f"  download /path/to/file.txt subdir/      - save to tmp/subdir/ as 'file.txt'")
        print(f"  download /path/to/file.txt newname.txt  - save to tmp/ as 'newname.txt'")
        return False
    
    remote_path = parts[1]
    remote_filename = os.path.basename(remote_path)
    
    # Determine local path - always relative to tmpDir
    if len(parts) > 2:
        local_path = parts[2]
        # Check if it's a directory (ends with / or \)
        if local_path.endswith(os.sep) or local_path.endswith('/'):
            # It's a directory within tmp
            local_dir = os.path.join(tmpDir, local_path.rstrip('/').rstrip(os.sep))
            local_name = os.path.join(local_dir, remote_filename)
        else:
            # It's a filename or path within tmp
            # If it contains path separators, treat the parent as a subdirectory
            local_parent = os.path.dirname(local_path)
            local_filename = os.path.basename(local_path)
            
            if local_parent:
                local_dir = os.path.join(tmpDir, local_parent)
                local_name = os.path.join(local_dir, local_filename)
            else:
                # Just a filename in tmpDir root
                local_dir = tmpDir
                local_name = os.path.join(tmpDir, local_filename)
    else:
        # No local path specified, save to tmp root with remote filename
        local_dir = tmpDir
        local_name = os.path.join(tmpDir, remote_filename)
    
    # Create directory if it doesn't exist
    try:
        os.makedirs(local_dir, exist_ok=True)
    except Exception as e:
        print(f"Error creating directory {local_dir}: {e}")
        return False

    # Send cat command to satellite
    raw_data = f"cat {remote_path}".encode('ascii')
    violet2Packets = violet2ProtocolBuilder(raw_data)

    if len(violet2Packets) > 1:
        print(f"Fragmenting into {len(violet2Packets)} packets...")
    for info in violet2Packets:
        ax25Send(info)

    # Flush buffer to remove stale packets
    receiveSocket.setblocking(False)
    flushCount = 0
    try:
        while True:
            receiveSocket.recvfrom(512)
            flushCount += 1
    except (BlockingIOError, socket.error):
        if flushCount > 0:
            print(f"Flushed {flushCount} stale packets...")
    receiveSocket.settimeout(3)

    # Reassembly buffer for multi-packet downloads
    downloadBuffer = {}
    totalReceived = 0
    maxRetries = 5
    retryCount = 0
    downloadComplete = False

    try:
        while not downloadComplete and retryCount < maxRetries:
            try:
                data, addr = receiveSocket.recvfrom(512)
                totalReceived += 1
                
                violet2Raw = data[AX25_HEADER_LEN:]
                parsed = parseViolet2Response(violet2Raw)

                if "error" in parsed:
                    print(f"[VIOLET2 Error]: {parsed['error']}")
                    continue

                messageType = parsed["msg_type"]
                sequenceNum = parsed["seq_num"]
                totalPackets = parsed["total_pkt"]
                packetIdx = parsed["pkt_idx"]
                payload = parsed["payload"]

                print(f"[Pass {totalReceived}] type=0x{messageType:02X}  seq={sequenceNum}  pkt {packetIdx+1}/{totalPackets}  payload_len={parsed['payload_len']}")

                # Single packet response
                if messageType == RESP_SINGLE:
                    fileContent = payload.decode('ascii', errors='replace')
                    # Check if response is an error message
                    errorKeywords = ['no such file', 'cannot open', 'error', 'permission denied', 'is a directory']
                    isError = any(keyword in fileContent.lower() for keyword in errorKeywords)
                    if isError:
                        print(f"Error: {fileContent}")
                        downloadComplete = True
                        return False
                    with open(local_name, 'w') as f:
                        f.write(fileContent)
                    print(f"Downloaded {remote_path} -> {local_name}")
                    downloadComplete = True
                    return True

                # Multi-packet response - start of transfer
                elif messageType == RESP_MULTI_START:
                    if sequenceNum not in downloadBuffer:
                        downloadBuffer[sequenceNum] = {
                            "total_pkt": totalPackets,
                            "fragments": {}
                        }
                    downloadBuffer[sequenceNum]["fragments"][packetIdx] = payload
                    print(f"  Buffering fragment {packetIdx+1}/{totalPackets}...")
                    retryCount = 0

                # Multi-packet continuation
                elif messageType == RESP_MULTI_CONT:
                    if sequenceNum not in downloadBuffer:
                        print(f"[VIOLET2 Error]: Received fragment for unknown seq {sequenceNum}")
                        continue
                    downloadBuffer[sequenceNum]["fragments"][packetIdx] = payload
                    print(f"  Buffering fragment {packetIdx+1}/{totalPackets}...")
                    retryCount = 0

                # Multi-packet end
                elif messageType == RESP_MULTI_END:
                    if sequenceNum not in downloadBuffer:
                        print(f"[VIOLET2 Error]: Received end fragment for unknown seq {sequenceNum}")
                        continue
                    
                    downloadBuffer[sequenceNum]["fragments"][packetIdx] = payload
                    print(f"  Buffering fragment {packetIdx+1}/{totalPackets}...")
                    
                    buffer = downloadBuffer[sequenceNum]
                    if len(buffer["fragments"]) == buffer["total_pkt"]:
                        print(f"  All {buffer['total_pkt']} fragments received, reassembling...")
                        fileContent = b"".join(
                            buffer["fragments"][i] for i in range(buffer["total_pkt"])
                        ).decode('ascii', errors='replace')
                        # Check if response is an error message
                        errorKeywords = ['no such file', 'cannot open', 'error', 'permission denied', 'is a directory']
                        isError = any(keyword in fileContent.lower() for keyword in errorKeywords)
                        if isError:
                            print(f"Error: {fileContent}")
                            del downloadBuffer[sequenceNumber]
                            downloadComplete = True
                            return False
                        with open(local_name, 'w') as f:
                            f.write(fileContent)
                        print(f"Downloaded {remote_path} -> {local_name} ({totalReceived} packets)")
                        del downloadBuffer[sequenceNum]
                        downloadComplete = True
                        return True
                    else:
                        print(f"  Warning: RESP_MULTI_END but only have {len(buffer['fragments'])}/{buffer['total_pkt']} fragments")
                        retryCount = 0
                
                else:
                    print(f"  [VIOLET2] Unexpected message type 0x{messageType:02X}")

            except socket.timeout:
                retryCount += 1
                if retryCount < maxRetries:
                    print(f"Timeout (attempt {retryCount}/{maxRetries}), waiting for more packets...")
                else:
                    print(f"Connection Timeout: No more data after {maxRetries} attempts")
                    if downloadBuffer:
                        for seq, buf in downloadBuffer.items():
                            print(f"  Incomplete transfer seq {seq}: {len(buf['fragments'])}/{buf['total_pkt']} fragments")

    except Exception as e:
        print(f"Download error: {e}")

    return False
