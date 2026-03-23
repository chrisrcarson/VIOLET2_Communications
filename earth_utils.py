import socket
import os
from ax25_utils import validate_ax25_header

# Earth Terminal Configuration Constants

# UDP Configuration
RECEIVE_HOST = "127.0.0.1"
RECEIVE_PORT = 27000 

UDP_HOST = "127.0.0.1" 
UDP_PORT = 27001

# AX.25 Layer 1 Configuration
AX25_HEADER_LEN     = 16
AX25_CONTROL        = "03"
AX25_FCS            = "0000"
AX25_PID            = "F0" 

EARTH_CALLSIGN      = "VE9CNB"
EARTH_SSID          = "E0"
SATELLITE_CALLSIGN  = "VE9VLT"
SATELLITE_SSID      = "60"

SOURCE_CALLSIGN     = EARTH_CALLSIGN
SOURCE_SSID         = EARTH_SSID
DEST_CALLSIGN       = SATELLITE_CALLSIGN
DEST_SSID           = SATELLITE_SSID

# Timeout and Retry Configuration
RECEIVE_TIMEOUT         = 5 # seconds to wait for a command response or download packet
PING_TIMEOUT            = 5 # seconds to wait for a pong reply
RETRANSMIT_INTERVAL     = 15 # fixed wait between retransmissions (seconds)

DOWNLOAD_MAX_RETRIES    = 5 # max consecutive timeouts before aborting a download
COMMAND_MAX_RETRIES     = 3 # number of command retransmissions after initial send
PING_MAX_RETRIES        = 3 # number of ping retransmissions after initial send

# VIOLET2 Layer 2 Protocol Configuration
VIOLET2_HEADER_LEN      = 8 # Bytes
VIOLET2_MIN_APP_DATA    = 92
VIOLET2_MAX_APP_DATA    = 248

PAD_BYTE_A  = 0xAA
PAD_BYTE_B  = 0x55

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
    # Split the input data into chunks of size VIOLET2_MAX_APP_DATA or smaller, and return a list of these chunks. 
    # This is used for fragmenting large commands or responses that exceed the maximum application data length for a single VIOLET2 packet.
    fragments = []
    offset = 0
    while offset < len(data): 
        fragments.append(
            data[offset:offset + VIOLET2_MAX_APP_DATA]
        )
        offset += VIOLET2_MAX_APP_DATA
    return fragments

def violet2ProtocolBuilder(payload: bytes) -> list[bytes]:
    sequenceNumber = _getNextSequenceNumber() # get next sequence number for this command

    if len(payload) <= VIOLET2_MAX_APP_DATA: # fits in single packet, no fragmentation needed
        payloadLength = len(payload) # actual payload length before padding
        applicationData = _padApplicationData(payload) # pad to minimum application data length if needed
        header = _buildViolet2Header( # single packet command for VIOLET2 header
            messageType=MSG_CMD_SINGLE,
            sequenceNumber=sequenceNumber,
            totalPackets=1,
            packetIndex=0,
            payloadLength=payloadLength,                
        )
        return [header + applicationData] 

    fragments = _fragmentData(payload) # split into multiple application data chunks if payload exceeds max application data length
    totalPackets = len(fragments) # total number of packets needed for this command (1 header + N-1 continuation)
    packets = []
    for index, chunk in enumerate(fragments): # build a VIOLET2 packet for each chunk with appropriate header fields
        if index == 0: # first packet, use multi-start message type
            messageType = MSG_CMD_MULTI_START
        elif index == totalPackets - 1: # last packet, use multi-end message type
            messageType = MSG_CMD_MULTI_END
        else: # middle packet, use multi-cont message type
            messageType = MSG_CMD_MULTI_CONT

        header = _buildViolet2Header( # build VIOLET2 header for this fragment with correct message type and sequence number
            messageType=messageType,
            sequenceNumber=sequenceNumber,
            totalPackets=totalPackets,
            packetIndex=index,
            payloadLength=len(chunk),
        )
        packets.append(header + _padApplicationData(chunk)) # pad each chunk to minimum application data length if needed and combine with header to form complete packet
    return packets

def parseViolet2Response(rawData: bytes) -> dict: 
    if len(rawData) < VIOLET2_HEADER_LEN: # must be at least long enough to contain the VIOLET2 header
        return {"error": "Packet too short for VIOLET2 header"}

    # Parse VIOLET2 header fields from the raw data (AX.25 header should already be stripped by caller)
    messageType    = rawData[0] 
    sequenceNumber = rawData[1]
    totalPackets   = rawData[2]
    packetIndex    = rawData[3]
    payloadLength  = (rawData[4] << 8) | rawData[5]
    checksum       = rawData[6]

    expectedChecksum = _violet2Checksum(rawData[0:6]) # calculate expected checksum from the first 6 header bytes and compare to the checksum byte in the header
    if checksum != expectedChecksum: # if checksum does not match, return an error indicating a corrupted packet
        return {
            "error": f"Checksum mismatch: got 0x{checksum:02X}, "
                     f"expected 0x{expectedChecksum:02X}"
        }

    # Extract the application data payload from the raw data based on the payload length specified in the header. 
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

def _sendViolet2Control(messageType: int, payload: bytes):
    header = _buildViolet2Header(
        messageType=messageType,
        sequenceNumber=0,
        totalPackets=1,
        packetIndex=0,
        payloadLength=len(payload),
    )
    ax25Send(header + _padApplicationData(payload))

def sendFragmentAck(sequenceNumber: int):
    _sendViolet2Control(MSG_ACK, bytes([sequenceNumber & 0xFF]))

def sendFragmentNack(sequenceNumber: int, missingIndices: list[int]):
    if not missingIndices:
        return

    # Byte 0 is sequence number; remaining bytes are missing packet indices.
    maxIndicesPerPacket = max(1, VIOLET2_MAX_APP_DATA - 1)
    cleaned = [index & 0xFF for index in sorted(set(missingIndices))]
    for offset in range(0, len(cleaned), maxIndicesPerPacket):
        chunk = cleaned[offset:offset + maxIndicesPerPacket]
        payload = bytes([sequenceNumber & 0xFF] + chunk)
        _sendViolet2Control(MSG_NACK, payload)

def isAx25DownlinkPacket(rawData: bytes) -> bool:
    # Earth receives downlink: VIOLET2 -> Earth
    # Validate AX.25 header for expected callsigns/control/pid for downlink packets from VIOLET2 to Earth
    return validate_ax25_header(
        raw_data=rawData, 
        expected_dest_callsign=EARTH_CALLSIGN,
        expected_dest_ssid_hex=EARTH_SSID,
        expected_src_callsign=SATELLITE_CALLSIGN,
        expected_src_ssid_hex=SATELLITE_SSID,
        expected_control_hex=AX25_CONTROL,
        expected_pid_hex=AX25_PID,
        header_len=AX25_HEADER_LEN,
    )

def ax25Send(payload: bytes) -> bytes:
    # Build an AX.25 packet with the given payload and send it to the satellite via UDP socket.
    # The AX.25 header is constructed with the expected callsigns, SSIDs, control, and PID for uplink packets from Earth to VIOLET2.
    ax25Packet = ( 
        DEST_CALLSIGN.encode('ascii') +
        bytes.fromhex(DEST_SSID) +
        SOURCE_CALLSIGN.encode('ascii') +
        bytes.fromhex(SOURCE_SSID) +
        bytes.fromhex(AX25_CONTROL) +
        bytes.fromhex(AX25_PID) +
        payload 
    )

    # [DEBUGGING]: printout of the raw AX.25 packet being sent (in hex format) for verification
    print(f"[EARTH TRANSMISSION]: {ax25Packet.hex()}\n")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(ax25Packet, (UDP_HOST, UDP_PORT))
    sock.close()
    return ax25Packet

def clearTerminal(): 
    os.system('cls' if os.name == 'nt' else 'clear')

def setupCommandHistory():
    # Set up command history using readline, storing history in a file in the user's home directory. 
    # This allows command recall across sessions.
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
    # Save command history to the specified file. 
    # This should be called on program exit to persist the history.
    if historyFile is None:
        return
    
    import readline
    try:
        readline.write_history_file(historyFile)
    except:
        pass

def downloadFile(userInput: str, receiveSocket: socket.socket, requirePartial: bool = False) -> bool:
    # Handle the 'download' command to retrieve a file from VIOLET2. The userInput should be in the format:
    # download <remote_path> [local_path]

    scriptDir = os.path.dirname(os.path.abspath(__file__)) # get the directory of the current script to determine where to save downloaded files relative to it
    tmpDir = os.path.join(scriptDir, "downloads_from_violet2") # create a subdirectory called "downloads_from_violet2" within the script directory to store downloaded files.
    try:
        os.makedirs(tmpDir, exist_ok=True) # create the directory if it doesn't exist, ignore if it already exists
    except Exception as e:
        print(f"Error creating downloads_from_violet2 directory: {e}")
        return False
    
    parts = userInput.split(" ", 2) # split the user input into parts: command, remote path, and optional local path.
    if len(parts) < 2: # if the user input does not contain at least a command and a remote path, print usage instructions and return False to indicate failure.
        print("Usage: download <remote_path> [local_path]")
        print(f"  download /path/to/file.txt              - save to downloads_from_violet2/ as 'file.txt'")
        print(f"  download /path/to/file.txt subdir/      - save to downloads_from_violet2/subdir/ as 'file.txt'")
        print(f"  download /path/to/file.txt newname.txt  - save to downloads_from_violet2/ as 'newname.txt'")
        return False
    
    remote_path = parts[1] # the remote path on VIOLET2 to download, specified by the user as the second.partial of the input
    remote_filename = os.path.basename(remote_path) # extract the filename from the remote path to use as the default local filename if the user does not specify a local path or filename.
    
    # Determine the local path to save the downloaded file.
    if len(parts) > 2:

        local_path = parts[2] # the local path or filename specified by the user.
        
        if local_path.endswith(os.sep) or local_path.endswith('/'): # Check if it's a directory (ends with / or \)
            local_dir = os.path.join(tmpDir, local_path.rstrip('/').rstrip(os.sep)) # It is a directory within downloads_from_violet2.
            local_name = os.path.join(local_dir, remote_filename) 

        else: # It is a filename or path within downloads_from_violet2. If it contains path separators, treat the parent as a subdirectory.
            local_parent = os.path.dirname(local_path)
            local_filename = os.path.basename(local_path)
            
            if local_parent: # If there is a parent directory specified, create that subdirectory within downloads_from_violet2 and save the file there.
                local_dir = os.path.join(tmpDir, local_parent)
                local_name = os.path.join(local_dir, local_filename)

            else: # Just a filename in tmpDir root
                local_dir = tmpDir
                local_name = os.path.join(tmpDir, local_filename)
    else: # No local path specified, save to downloads_from_violet2 root with remote filename
        local_dir = tmpDir
        local_name = os.path.join(tmpDir, remote_filename)
    
    try:
        os.makedirs(local_dir, exist_ok=True) # Create directory if it doesn't exist, ignore if it already exists.
    
    except Exception as e: 
        print(f"Error creating directory {local_dir}: {e}")
        return False

    # Use the local_name variable as the final path where the downloaded file will be saved. 
    partial_name = f"{local_name}.partial" 
    resume_offset = 0 # If a .partial file exists from a previous incomplete download, get its size to determine the byte offset to resume from. This allows the download to continue from where it left off rather than starting over.
    hasPartial = os.path.exists(partial_name)
    if requirePartial and not hasPartial:
        print(f"[VIOLET2]: No partial file found for resume: {partial_name}")
        print("[VIOLET2]: Start a download first, then use resume if interrupted.")
        return False

    if hasPartial: # Check if a .partial file exists for this download.
        
        try: # If the .partial file exists, attempt to read its size to determine how many bytes were already downloaded. 
            resume_offset = os.path.getsize(partial_name)
            if resume_offset > 0:
                print(f"[VIOLET2]: Found partial download ({resume_offset} bytes). Attempting to resume download...")
        
        except OSError as e: # If the file cannot be read for some reason, catch the exception and print a warning, but continue with resume_offset set to 0 which will cause the download to start from the beginning.
            print(f"[VIOLET2]: Warning! Could not read partial file size: {e}")
            resume_offset = 0

    def appendPartialFromBuffer(buffer_map: dict[int, dict]):
        # Iterate through the buffer map which holds fragments of multi-packet responses keyed by sequence number. 
        # For each sequence number, check if there are any fragments received for that sequence.
        for seq, buf in buffer_map.items():
            fragments = buf.get("fragments", {})
            
            if not fragments: # If there are no fragments for this sequence number, skip to the next one. This can happen if we have received a header for a multi-packet response but haven't received any of the fragments yet, or if all fragments have already been processed and removed from the buffer.
                continue
            
            next_index = 0
            contiguous = []
            
            while next_index in fragments: 
                # Collect fragments in order starting from index 0 until we encounter a missing fragment index, indicating a gap in the received fragments. 
                # This allows us to append any contiguous fragments we have received so far to the partial file, even if we haven't received the complete set of fragments for that sequence number yet.
                contiguous.append(fragments[next_index])
                next_index += 1
            
            if not contiguous: # If we don't have any contiguous fragments starting from index 0, skip this sequence number for now and wait for more fragments to arrive.
                continue
            
            # Join the contiguous fragments together to form a chunk of data that can be appended to the partial file. 
            chunk = b"".join(contiguous).decode('ascii', errors='replace') 
            try:
                with open(partial_name, 'a') as f: # write chunk to the .partial file
                    f.write(chunk)
                print(f"[VIOLET2]: Saved {len(chunk)} bytes of partial data (seq={seq}) to {partial_name}")
            
            except Exception as write_err:
                print(f"[VIOLET2]: Warning! Failed to save partial data: {write_err}")

    # BEGIN DOWNLOAD PROCESS
    # Step 1: Send command to satellite (resume uses tail from byte offset)
    if resume_offset > 0:
        raw_data = f"tail -c +{resume_offset + 1} {remote_path}".encode('ascii')
    else:
        raw_data = f"cat {remote_path}".encode('ascii')
    violet2Packets = violet2ProtocolBuilder(raw_data) # Build VIOLET2 packets for the command (fragmented if necessary).

    # If the command is large enough to require fragmentation, print a message indicating how many packets will be sent.
    if len(violet2Packets) > 1: 
        print(f"Fragmenting into {len(violet2Packets)} packets...\n")
    
    # Step 2: Send each packet of the command to the satellite using the ax25Send function, which constructs an AX.25 packet and sends it via UDP.
    for info in violet2Packets: 
        ax25Send(info)

    # Flush buffer to remove stale packets
    receiveSocket.setblocking(False)
    flushCount = 0
    try:
        while True:
            receiveSocket.recvfrom(512) # Read packets until there are no more to read, counting how many were flushed.
            flushCount += 1
    except (BlockingIOError, socket.error): 
        if flushCount > 0: # If any packets were flushed, print out how many were removed from the buffer to provide feedback to the user.
            print(f"Flushed {flushCount} stale packets.")
    
    # Set the timeout for receiving packets related to this download action. 
    receiveSocket.settimeout(RECEIVE_TIMEOUT) 

    # Step 3: Enter a loop to receive packets from the satellite, looking for the response to the download command. 
    # The loop will continue until the download is complete or the maximum number of retries is reached due to timeouts.
    downloadBuffer = {} # A buffer to hold fragments of a multi-packet response, keyed by sequence number. Each entry will contain the total number of packets expected and a dictionary of received fragments indexed by packet index.
    totalReceived = 0
    maxRetries = DOWNLOAD_MAX_RETRIES
    retryCount = 0
    downloadComplete = False

    try:
        while not downloadComplete and retryCount < maxRetries: # Loop until the download is complete or we have reached the maximum number of retries due to timeouts.
            try:
                data, addr = receiveSocket.recvfrom(512) # Wait for a packet to be received from the satellite. If a packet is received, increment the totalReceived counter to keep track of how many packets have been received for this download action.
                totalReceived += 1

                if not isAx25DownlinkPacket(data): 
                    # Validate that the received packet has the expected AX.25 header for a downlink packet from VIOLET2 to Earth. 
                    # If it does not match, print an error message and ignore this packet, continuing to wait for the correct response.
                    print("[VIOLET2]: Error! Packet rejected due to unexpected AX.25 callsigns")
                    continue
                
                # If the packet has a valid AX.25 header, strip the AX.25 header and parse the remaining data as a VIOLET2 response using the parseViolet2Response function. 
                # This will extract the VIOLET2 header fields and application data payload from the raw packet data.
                violet2Raw = data[AX25_HEADER_LEN:]
                parsed = parseViolet2Response(violet2Raw) 

                if "error" in parsed: 
                    # If there was an error parsing the VIOLET2 response (e.g., a checksum mismatch or packet too short), 
                    # print out the error message and ignore this packet, continuing to wait for the correct response.
                    print(f"[VIOLET2]: Error! {parsed['error']}")
                    continue
                
                # If the packet was parsed successfully, extract the VIOLET2 header fields and parsed payload.
                messageType = parsed["msg_type"]
                sequenceNum = parsed["seq_num"]
                totalPackets = parsed["total_pkt"]
                packetIdx = parsed["pkt_idx"]
                payload = parsed["payload"]

                print(f"[Pass {totalReceived}] type=0x{messageType:02X} seq={sequenceNum} pkt {packetIdx+1}/{totalPackets} payload_len={parsed['payload_len']}")

                # 1. Single packet response
                if messageType == RESP_SINGLE:
                    fileContent = payload.decode('ascii', errors='replace')
                    errorKeywords = ['no such file', 'cannot open', 'error', 'permission denied', 'is a directory']
                    isError = any(keyword in fileContent.lower() for keyword in errorKeywords) # Check if response is an error message
                    
                    if isError: 
                        # If the response contains keywords indicating an error, print the error message and return False to indicate the download failed. 
                        # Otherwise, save the file content to the specified local path and return True to indicate success.
                        print(f"[VIOLET2]: Error! {fileContent}")
                        downloadComplete = True
                        return False

                    # If there is a .partial file from a previous incomplete download, append to it and then rename to the final local name. 
                    # Otherwise, write directly to the local name. This allows for resuming downloads if they are interrupted.
                    if resume_offset > 0 or os.path.exists(partial_name):
                        with open(partial_name, 'a') as f:
                            f.write(fileContent)
                        os.replace(partial_name, local_name)
                        if os.path.exists(partial_name):
                            os.remove(partial_name)
                    
                    else: # No .partial file, write the content to the specified local file.
                        with open(local_name, 'w') as f: 
                            f.write(fileContent)

                    print(f"[VIOLET2]: Downloaded {remote_path} to {local_name}") # Confirmation
                    downloadComplete = True
                    return True

                # 2-4. Multi-packet response handling with fragment-level NACK recovery.
                elif messageType in (RESP_MULTI_START, RESP_MULTI_CONT, RESP_MULTI_END):

                    # If this is the first packet of a multi-packet response we are seeing for this sequence number, 
                    # initialize a buffer entry to track the total number of packets expected, the fragments received so far, 
                    # and whether we have seen the end packet.
                    if sequenceNum not in downloadBuffer:
                        downloadBuffer[sequenceNum] = {
                            "total_pkt": totalPackets,
                            "fragments": {},
                            "end_seen": False,
                            "last_nack_missing": set(),
                        }
                    
                    # Store the received fragment in the buffer under the appropriate sequence number and packet index. 
                    # Update the total packets expected if this packet indicates a higher total than previously seen for this sequence number. 
                    # If this packet is an end packet, mark that we have seen the end for this sequence number.
                    buffer = downloadBuffer[sequenceNum]
                    buffer["total_pkt"] = max(buffer["total_pkt"], totalPackets)
                    buffer["fragments"][packetIdx] = payload
                    if messageType == RESP_MULTI_END:
                        buffer["end_seen"] = True
                    
                    # After buffering the received fragment, 
                    # check if we have seen the end packet and if we have received all fragments up to the total expected.
                    print(f"[VIOLET2]: Buffering fragment {packetIdx+1}/{totalPackets}...\n")
                    retryCount = 0

                    highestReceived = max(buffer["fragments"].keys(), default=-1)
                    missingSeenWindow = [
                        index
                        for index in range(highestReceived + 1)
                        if index not in buffer["fragments"]
                    ]
                    if missingSeenWindow:
                        missingSet = set(missingSeenWindow)
                        if missingSet != buffer["last_nack_missing"]:
                            sendFragmentNack(sequenceNum, missingSeenWindow)
                            buffer["last_nack_missing"] = missingSet
                            print(
                                f"[VIOLET2]: Early NACK sent for seq={sequenceNum}, "
                                f"missing {len(missingSeenWindow)} fragment(s)"
                            )

                    # If we have seen the end packet but are STILL MISSING some fragments, 
                    # send a NACK for the missing fragment indices to request retransmission from the satellite.
                    if buffer["end_seen"] and len(buffer["fragments"]) < buffer["total_pkt"]:
                        missing = [
                            index
                            for index in range(buffer["total_pkt"])
                            if index not in buffer["fragments"]
                        ]
                        missingSet = set(missing)
                        if missingSet != buffer["last_nack_missing"]:
                            sendFragmentNack(sequenceNum, missing)
                            buffer["last_nack_missing"] = missingSet
                            print(
                                f"[VIOLET2]: NACK sent for seq={sequenceNum}, "
                                f"missing {len(missing)} fragment(s)"
                            )
                        continue
                    
                    # If we have SEEN THE END packet and have received all fragments, 
                    # we can reassemble the complete file content from the buffered fragments, 
                    # check for any error messages in the content, and if it looks like a valid file, 
                    # save it to the specified local path.
                    if buffer["end_seen"] and len(buffer["fragments"]) == buffer["total_pkt"]:
                        print(f"[VIOLET2]: All {buffer['total_pkt']} fragments received, reassembling...\n")
                        fileContent = b"".join(
                            buffer["fragments"][i] for i in range(buffer["total_pkt"])
                        ).decode('ascii', errors='replace')

                        errorKeywords = ['no such file', 'cannot open', 'error', 'permission denied', 'is a directory']
                        isError = any(keyword in fileContent.lower() for keyword in errorKeywords)

                        if isError:
                            print(f"[VIOLET2]: Error! {fileContent}\n")
                            del downloadBuffer[sequenceNum]
                            downloadComplete = True
                            return False

                        if resume_offset > 0 or os.path.exists(partial_name):
                            with open(partial_name, 'a') as f:
                                f.write(fileContent)
                            os.replace(partial_name, local_name)
                            if os.path.exists(partial_name):
                                os.remove(partial_name)
                        else:
                            with open(local_name, 'w') as f:
                                f.write(fileContent)
    
                        sendFragmentAck(sequenceNum)
                        print(f"[VIOLET2]: Downloaded [{remote_path}] to [{local_name}] {totalReceived} packets.\n")
                        del downloadBuffer[sequenceNum]
                        downloadComplete = True
                        return True
                
                else: # If we receive a message type that is not recognized as.partial of the expected response types for a download command, print an error message indicating an unexpected message type.
                    print(f"[VIOLET2]: Error! Unexpected message type 0x{messageType:02X}")

            except socket.timeout: # Socket timeout handling while waiting for packets related to download action.
                retryCount += 1 

                # If we have buffered fragments and are missing any indices, send NACKs for those fragments
                # to request retransmission from the satellite.
                # This allows us to attempt to recover from lost packets without having to restart the entire download process, improving reliability during intermittent connectivity issues.
                if downloadBuffer:
                    for seq, buf in downloadBuffer.items():
                        totalPkt = buf.get("total_pkt", 0)
                        fragments = buf.get("fragments", {})
                        if totalPkt <= 0 or not fragments:
                            continue
                        missing = [
                            index
                            for index in range(totalPkt)
                            if index not in fragments
                        ]
                        if missing:
                            sendFragmentNack(seq, missing)
                            buf["last_nack_missing"] = set(missing)
                            print(
                                f"[VIOLET2]: Timeout-triggered NACK for seq={seq}, "
                                f"missing {len(missing)} fragment(s)"
                            )
                
                if retryCount < maxRetries: # If more retries are available, print a timeout message indicating the current attempt and that we are waiting for more packets.
                    print(f"[VIOLET2]: Timeout (attempt {retryCount}/{maxRetries}), waiting for more packets...")
                
                else: # Timed out completely
                    print(f"[VIOLET2]: Connection Timeout: No more data after {maxRetries} attempts")
                    
                    if downloadBuffer: 
                        # If we have any fragments in the buffer at this point, print out a warning indicating that the download is incomplete and how many fragments were received for each sequence number.
                        for seq, buf in downloadBuffer.items():
                            print(f"[VIOLET2] Incomplete transfer for seq={seq}: {len(buf['fragments'])}/{buf['total_pkt']} fragments")
                        appendPartialFromBuffer(downloadBuffer)

    except KeyboardInterrupt:
        print("\n[VIOLET2]: Download interrupted by user (Ctrl+C).")
        if downloadBuffer:
            appendPartialFromBuffer(downloadBuffer)
            print(f"[VIOLET2]: Partial download saved to {partial_name}")
        else:
            print("[VIOLET2]: No partial fragments to save.")
        return False

    except Exception as e: # Exception handling for any unexpected errors during the download process.
        print(f"Download error: {e}")
        if downloadBuffer:
            appendPartialFromBuffer(downloadBuffer)

    return False # If we exit the loop without completing the download, return False to indicate failure.
