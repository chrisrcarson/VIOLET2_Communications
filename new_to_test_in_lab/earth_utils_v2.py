import socket
import os
import json
import base64

# Earth Terminal Configuration Constants

# UDP Configuration
RECEIVE_HOST = "127.0.0.1"
RECEIVE_PORT = 27001 #27000
UDP_HOST = "127.0.0.1" 
UDP_PORT = 27000#27001

# AX.25 Layer 1 Configuration
AX25_HEADER_LEN     = 16
AX25_CONTROL        = "00"
AX25_FCS            = "0000"
AX25_PID            = "F0"

SOURCE_CALLSIGN     = "VE9CNB"
SOURCE_SSID         = "E0"
DEST_CALLSIGN       = "VE9VLT"
DEST_SSID           = "60"

# Timeout and Retry Configuration
RECEIVE_TIMEOUT      = 15 # seconds to wait for a command response
PING_TIMEOUT         = 20 # seconds to wait for a pong reply
DOWNLOAD_TIMEOUT     = 30 # seconds to wait between fragments before retransmitting
DOWNLOAD_MAX_RETRIES = 3  # max retransmit attempts per missing fragment before aborting
COMMAND_MAX_RETRIES  = 3

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
    
    # Create tmp_downloads directory in script's directory if it doesn't exist
    scriptDir = os.path.dirname(os.path.abspath(__file__))
    tmpDir = os.path.join(scriptDir, "tmp_downloads")
    try:
        os.makedirs(tmpDir, exist_ok=True)
    except Exception as e:
        print(f"Error creating tmp_downloads directory: {e}")
        return False
    
    def parseDownloadArgs(rawInput: str):
        tokens = rawInput.strip().split()
        if not tokens or tokens[0].lower() != "download":
            return None

        resumeMode = False
        idx = 1
        if idx < len(tokens) and tokens[idx] == "--resume":
            resumeMode = True
            idx += 1

        if idx >= len(tokens):
            return None

        remotePath = tokens[idx]
        idx += 1
        localPath = " ".join(tokens[idx:]) if idx < len(tokens) else None
        return resumeMode, remotePath, localPath

    parsedArgs = parseDownloadArgs(userInput)
    if parsedArgs is None:
        print("Usage: download [--resume] <remote_path> [local_path]")
        print(f"  download /path/to/file.txt              - save to tmp_downloads/ as 'file.txt'")
        print(f"  download /path/to/file.txt subdir/      - save to tmp_downloads/subdir/ as 'file.txt'")
        print(f"  download /path/to/file.txt newname.txt  - save to tmp_downloads/ as 'newname.txt'")
        print(f"  download --resume /path/to/file.txt     - resume from tmp_downloads/<file>.partial.fragments")
        return False

    resumeMode, remote_path, local_path = parsedArgs
    remote_filename = os.path.basename(remote_path)
    
    # Determine local path - always relative to tmpDir
    if local_path is not None:
        # Check if it's a directory (ends with / or \)
        if local_path.endswith(os.sep) or local_path.endswith('/'):
            # It's a directory within tmp_downloads
            local_dir = os.path.join(tmpDir, local_path.rstrip('/').rstrip(os.sep))
            local_name = os.path.join(local_dir, remote_filename)
        else:
            # It's a filename or path within tmp_downloads
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
        # No local path specified, save to tmp_downloads root with remote filename
        local_dir = tmpDir
        local_name = os.path.join(tmpDir, remote_filename)
    
    # Create directory if it doesn't exist
    try:
        os.makedirs(local_dir, exist_ok=True)
    except Exception as e:
        print(f"Error creating directory {local_dir}: {e}")
        return False

    def sendCommand(commandText: str):
        commandPackets = violet2ProtocolBuilder(commandText.encode('ascii', errors='replace'))
        if len(commandPackets) > 1:
            print(f"Fragmenting command into {len(commandPackets)} packets...")
        for info in commandPackets:
            ax25Send(info)

    def flushSocket():
        receiveSocket.setblocking(False)
        flushed = 0
        try:
            while True:
                receiveSocket.recvfrom(512)
                flushed += 1
        except (BlockingIOError, socket.error):
            if flushed > 0:
                print(f"Flushed {flushed} stale packets...")
        receiveSocket.settimeout(DOWNLOAD_TIMEOUT)

    def savePartialFile(fragments, totalPkt):
        # write what we have, using empty bytes for missing fragments
        partialName = local_name + ".partial"
        stateName = local_name + ".partial.fragments"
        missingIdxs = [i for i in range(totalPkt) if i not in fragments]
        content = b"".join(
            fragments.get(i, b"[MISSING FRAGMENT]\n")
            for i in range(totalPkt)
        ).decode('ascii', errors='replace')
        with open(partialName, 'w') as f:
            f.write(content)

        serializedFragments = {
            str(idx): base64.b64encode(payload).decode('ascii')
            for idx, payload in fragments.items()
        }
        statePayload = {
            "remote_path": remote_path,
            "total_packets": totalPkt,
            "fragments": serializedFragments,
        }
        with open(stateName, 'w') as f:
            json.dump(statePayload, f)

        print(f"Partial file saved to {partialName}")
        print(f"Resume state saved to {stateName}")
        print(f"Missing fragments: {missingIdxs} ({len(missingIdxs)}/{totalPkt})")

    def loadResumeState():
        stateName = local_name + ".partial.fragments"
        if not os.path.exists(stateName):
            return None, None
        try:
            with open(stateName, 'r') as f:
                statePayload = json.load(f)
            storedTotal = int(statePayload.get("total_packets", 0))
            storedFragments = {}
            for idxText, encoded in statePayload.get("fragments", {}).items():
                try:
                    idx = int(idxText)
                    storedFragments[idx] = base64.b64decode(encoded.encode('ascii'))
                except (ValueError, TypeError):
                    continue
            if storedTotal <= 0:
                return None, None
            return storedTotal, storedFragments
        except Exception as e:
            print(f"Warning: could not load resume state: {e}")
            return None, None

    def clearResumeState():
        partialName = local_name + ".partial"
        stateName = local_name + ".partial.fragments"
        for path in (partialName, stateName):
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

    def receiveCommandResponse() -> bytes | None:
        responseFragments = {}
        expectedTotal = None

        while True:
            try:
                data, _ = receiveSocket.recvfrom(512)
            except socket.timeout:
                return None

            violet2Raw = data[AX25_HEADER_LEN:]
            parsed = parseViolet2Response(violet2Raw)
            if "error" in parsed:
                print(f"[VIOLET2 Error]: {parsed['error']}")
                continue

            messageType = parsed["msg_type"]
            packetIdx = parsed["pkt_idx"]
            pktTotal = parsed["total_pkt"]
            payload = parsed["payload"]

            if messageType == RESP_SINGLE:
                return payload

            if messageType in (RESP_MULTI_START, RESP_MULTI_CONT, RESP_MULTI_END):
                if expectedTotal is None:
                    expectedTotal = pktTotal
                responseFragments[packetIdx] = payload
                if len(responseFragments) == expectedTotal:
                    return b"".join(responseFragments[i] for i in range(expectedTotal))
                continue

            # ignore loopback/unexpected packet types while waiting for a response

    def isProtocolError(payload: bytes) -> bool:
        text = payload.decode('ascii', errors='replace').strip()
        return text.startswith("V2ERR ")

    def isLegacyRemoteError(payload: bytes) -> bool:
        text = payload.decode('ascii', errors='replace').lower()
        errorKeywords = ['no such file', 'cannot open', 'error', 'permission denied', 'is a directory']
        return any(keyword in text for keyword in errorKeywords)

    def parseMetadata(payload: bytes) -> int | None:
        text = payload.decode('ascii', errors='replace').strip()
        if not text.startswith("V2META "):
            return None
        parts = text.split()
        for part in parts[1:]:
            if part.startswith("total="):
                try:
                    value = int(part.split("=", 1)[1])
                except ValueError:
                    return None
                return value if value > 0 else None
        return None

    fragments = {}
    totalPkt = None

    try:
        flushSocket()

        # Step 1: request metadata so EARTH knows exactly how many packets to poll.
        metadata = None
        for attempt in range(1, DOWNLOAD_MAX_RETRIES + 1):
            sendCommand(f"dlmeta {remote_path}")
            metadata = receiveCommandResponse()
            if metadata is not None:
                break
            print(f"Download metadata timeout, retrying ({attempt}/{DOWNLOAD_MAX_RETRIES})...")

        if metadata is None:
            print(f"Download failed: no metadata response after {DOWNLOAD_MAX_RETRIES} attempts")
            flushSocket()
            return False

        if isProtocolError(metadata):
            print(f"Download failed: {metadata.decode('ascii', errors='replace')}")
            flushSocket()
            return False

        totalPkt = parseMetadata(metadata)
        if totalPkt is None:
            # Fallback for older responder behavior: treat metadata response as the full file content.
            if isLegacyRemoteError(metadata):
                print(f"Error: {metadata.decode('ascii', errors='replace')}")
                flushSocket()
                return False
            with open(local_name, 'w') as f:
                f.write(metadata.decode('ascii', errors='replace'))
            print(f"Downloaded {remote_path} -> {local_name}")
            flushSocket()
            return True

        print(f"Transfer metadata: expecting {totalPkt} fragment(s)")

        if resumeMode:
            resumedTotal, resumedFragments = loadResumeState()
            if resumedTotal is not None and resumedFragments is not None:
                if resumedTotal == totalPkt:
                    fragments.update({
                        idx: payload
                        for idx, payload in resumedFragments.items()
                        if 0 <= idx < totalPkt
                    })
                    print(f"Resume mode: loaded {len(fragments)}/{totalPkt} fragment(s) from saved state")
                else:
                    print(f"Resume state total mismatch (saved={resumedTotal}, current={totalPkt}), starting fresh")

        # Step 2: poll each fragment index until received or retries exhausted.
        for idx in range(totalPkt):
            if idx in fragments:
                continue

            received = False
            for attempt in range(1, DOWNLOAD_MAX_RETRIES + 1):
                sendCommand(f"dlfrag {idx} {remote_path}")
                payload = receiveCommandResponse()

                if payload is None:
                    print(f"  Fragment {idx + 1}/{totalPkt} timeout ({attempt}/{DOWNLOAD_MAX_RETRIES})")
                    continue

                if isProtocolError(payload):
                    print(f"Error receiving fragment {idx}: {payload.decode('ascii', errors='replace')}")
                    break

                fragments[idx] = payload
                received = True
                print(f"  Received fragment {idx + 1}/{totalPkt} (collected {len(fragments)}/{totalPkt})")
                break

            if not received:
                print(f"  Fragment {idx + 1}/{totalPkt} missing after {DOWNLOAD_MAX_RETRIES} attempts")

    except KeyboardInterrupt:
        print("\nDownload aborted by user.")
        if totalPkt is not None:
            savePartialFile(fragments, totalPkt)
        flushSocket()
        return False

    except Exception as e:
        print(f"Download error: {e}")
        if totalPkt is not None and fragments:
            savePartialFile(fragments, totalPkt)
        flushSocket()
        return False

    if totalPkt is None:
        flushSocket()
        return False

    missing = [i for i in range(totalPkt) if i not in fragments]
    if missing:
        print(f"Download incomplete: missing fragment(s) {missing}")
        savePartialFile(fragments, totalPkt)
        flushSocket()
        return False

    print(f"  All {totalPkt} fragments received, reassembling...")
    fileContent = b"".join(fragments[i] for i in range(totalPkt)).decode('ascii', errors='replace')

    with open(local_name, 'w') as f:
        f.write(fileContent)

    clearResumeState()

    print(f"Downloaded {remote_path} -> {local_name} ({totalPkt} fragments)")
    flushSocket()
    return True
