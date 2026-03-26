from __future__ import annotations
from typing import List, Dict, Optional, Union

import socket
import os
from ax25_utils import validate_ax25_header

# UDP Configuration
RECEIVE_HOST = "127.0.0.1"
RECEIVE_PORT = 27000

UDP_HOST = "127.0.0.1" 
UDP_PORT = 27001

# AX.25 Layer 1
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

# VIOLET2 Layer 2
VIOLET2_HEADER_LEN          = 8 # Bytes
VIOLET2_MIN_APP_DATA        = 92
VIOLET2_MAX_APP_DATA        = 248
EARTH_RECEIVE_BUFFER_SIZE   = 2048

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

# Timeout and Retransmission Setup
RECEIVE_TIMEOUT         = 5 # seconds
PING_TIMEOUT            = 15 # seconds

DOWNLOAD_MAX_RETRIES    = 3 # max consecutive timeouts before aborting a download
COMMAND_MAX_RETRIES     = 3 # number of command retransmissions after initial send
PING_MAX_RETRIES        = 3 # number of ping retransmissions after initial send

HELP_TEXT = """Available commands:
    help
        Show this help message.

    clear
        Clear the terminal screen.

    quit
        Exit the EARTH terminal.

    ping
        Send a ping to VIOLET2 and print round-trip time.

    download <remotePath> [localPath]
        Download a file from VIOLET2.
        Example: download test_data/larger_file.txt
        Example: download test_data/larger_file.txt downloads_from_violet2/larger_file.txt

    resume <remotePath> [localPath]
        Resume a partial download from VIOLET2.
        Example: resume test_data/larger_file.txt

Any other input is treated as a remote shell command sent to VIOLET2.
"""

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

def _fragmentData(data: bytes) -> List[bytes]:
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

def parseViolet2Response(rawData: bytes) -> dict:
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

def isAx25DownlinkPacket(rawData: bytes) -> bool:
    """
    Validate that the given raw data has an AX.25 header matching the expected values for a downlink packet from VIOLET2 to Earth.
    Returns: True if the AX.25 header is valid and matches the expected values for an incoming downlink packet, False otherwise.
    """
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

def violet2ProtocolBuilder(payload: bytes) -> List[bytes]:
    """
    Build VIOLET2 Layer 2 packets from the given application data payload, handling fragmentation based on the maximum allowed size.
    Returns: a list of byte strings, each representing a complete VIOLET2 packet.
    """
    sequenceNumber = _getNextSequenceNumber() # get the next available seq_num for the VIOLET2 header

    # if payload fits in a single packet, use MSG_CMD_SINGLE message type
    if len(payload) <= VIOLET2_MAX_APP_DATA:
        payloadLength = len(payload) # calculate the actual payload length (before padding)
        applicationData = _padApplicationData(payload) # pad the application data
        header = _buildViolet2Header( # build the VIOLET2 header for a single packet command
            messageType=MSG_CMD_SINGLE,
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
        
        if index == 0: # first packet = MSG_CMD_MULTI_START message type
            messageType = MSG_CMD_MULTI_START

        elif index == totalPackets - 1: # last packet = MSG_CMD_MULTI_END message type
            messageType = MSG_CMD_MULTI_END

        else: # middle packets = MSG_CMD_MULTI_CONT message type
            messageType = MSG_CMD_MULTI_CONT

        header = _buildViolet2Header( # build the VIOLET2 header for this fragment based on its position in the sequence
            messageType=messageType,
            sequenceNumber=sequenceNumber,
            totalPackets=totalPackets,
            packetIndex=index,
            payloadLength=len(chunk),
        )
        packets.append(header + _padApplicationData(chunk)) # pad the application data for this fragment, combine with header, and add to packets list

    return packets

def ax25Send(payload: bytes, txSocket: Optional[socket.socket] = None) -> bytes:
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

    print(f"[EARTH TRANSMISSION]:\n{ax25Packet.hex()}\n")
    
    # use a caller-provided socket when available, otherwise use a temporary one.
    if txSocket is not None:
        txSocket.sendto(ax25Packet, (UDP_HOST, UDP_PORT))
    else:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(ax25Packet, (UDP_HOST, UDP_PORT))
        sock.close()
    
    return ax25Packet

def _ACK(sequenceNumber: int):
    """
    Send an ACK message for the given sequence number.
        - sequenceNumber: the sequence number of the packet or message being acknowledged
    """
    payload = bytes([sequenceNumber & 0xFF])
    header = _buildViolet2Header(
        messageType=MSG_ACK,
        sequenceNumber=0,
        totalPackets=1,
        packetIndex=0,
        payloadLength=len(payload),
    )
    ax25Send(header + _padApplicationData(payload))

def _NACK(sequenceNumber: int, missingIndices: List[int]):
    """
    Send a NACK message for the given sequence number, including the list of missing packet indices.
        - sequenceNumber: the sequence number of the multi-packet message being NACKed
        - missingIndices: a list of packet indices that were not received and need to be retransmitted (e.g. [0, 2] means the first and third packets are missing)
    """
    # if there are no missing indices, we don't need to send a NACK at all
    if not missingIndices:
        return

    maxIndicesPerPacket = max(1, VIOLET2_MAX_APP_DATA - 1) # calculate how many missing indices we can fit in a single NACK packet
    cleaned = [index & 0xFF for index in sorted(set(missingIndices))] # clean the list of missing indices by removing duplicates

    # if the list of missing indices fits in a single packet, send one NACK with MSG_NACK message type
    for offset in range(0, len(cleaned), maxIndicesPerPacket):
        chunk = cleaned[offset:offset + maxIndicesPerPacket] # take a chunk of missing indices that fits in one packet
        payload = bytes([sequenceNumber & 0xFF] + chunk) # the payload consists of the sequence number followed by the list of missing indices
        header = _buildViolet2Header(
            messageType=MSG_NACK,
            sequenceNumber=0,
            totalPackets=1,
            packetIndex=0,
            payloadLength=len(payload),
        )
        ax25Send(header + _padApplicationData(payload))

def clearTerminal(): 
    """
    Clear the terminal screen using the appropriate command for the operating system.
    """
    os.system('cls' if os.name == 'nt' else 'clear')

def setupCommandHistory():
    """
    Set up command history using the readline module, storing history in a file in the user's home directory.
    Returns: the path to the history file being used, or None if history could not be set up.
    """
    import readline # import readline for command history functionality
    
    historyFile = os.path.expanduser('~/.violet2_history')
    readline.set_history_length(100)
    
    if os.path.exists(historyFile):
        try:
            readline.read_history_file(historyFile)
        except:
            pass
    
    return historyFile

def saveCommandHistory(historyFile):
    """
    Save the command history to the specified history file.
        - historyFile: the path to the history file where command history should be saved. If None, history will not be saved.
    """
    if historyFile is None:
        return
    
    import readline
    try:
        readline.write_history_file(historyFile)
    except:
        pass

def downloadFile(userInput: str, receiveSocket: socket.socket, requirePartial: bool = False) -> bool:
    """
    Handle the download command by transmitting to VIOLET2, receiving response packets, and saving the downloaded file to disk; support for resuming partial downloads included.
        - userInput: the raw command input from the user (including local path)
        - receiveSocket: the socket object configured for receiving packets from VIOLET2.
        - requirePartial: if True, the function will only attempt to resume a download if a .partial file already exists for the specified remote path. If False, the function will start a new download even if no .partial file exists.
    Returns: True if the download was successful, False if it failed (e.g. due to timeouts, errors, or user input issues).
    """
    # Step 1: Determine local path to save the downloaded file
    scriptDir = os.path.dirname(os.path.abspath(__file__)) 
    tmpDir = os.path.join(scriptDir, "downloads_from_violet2") 
    
    # Step 2: Determine the final local path and filename for the download file
    parts = userInput.split(" ", 2) 
    if len(parts) < 2: 
        print("Usage: download <remotePath> [localPath]")
        print(f"  download /path/to/file.txt              - save to downloads_from_violet2/ as 'file.txt'")
        print(f"  download /path/to/file.txt subdir/      - save to downloads_from_violet2/subdir/ as 'file.txt'")
        print(f"  download /path/to/file.txt newname.txt  - save to downloads_from_violet2/ as 'newname.txt'")
        return False
    
    remotePath = parts[1] 
    remoteFilename = os.path.basename(remotePath) 
    
    if len(parts) > 2:

        localPath = parts[2] 

        if localPath.endswith(os.sep) or localPath.endswith('/'): 
            localDir = os.path.join(tmpDir, localPath.rstrip('/').rstrip(os.sep)) 
            localName = os.path.join(localDir, remoteFilename) 
        else: 
            localParent = os.path.dirname(localPath)
            localFilename = os.path.basename(localPath)
            
            if localParent: 
                localDir = os.path.join(tmpDir, localParent)
                localName = os.path.join(localDir, localFilename)
            else: 
                localDir = tmpDir
                localName = os.path.join(tmpDir, localFilename)

    else: 
        localDir = tmpDir
        localName = os.path.join(tmpDir, remoteFilename)
    
    try:
        os.makedirs(localDir, exist_ok=True)

    except Exception as e: 
        print(f"Error creating directory {localDir}: {e}")
        return False

    # Step 3: Determine if this is a "resume" download and if a .partial file exists
    partialName = f"{localName}.partial" 
    resumeOffset = 0 
    hasPartial = os.path.exists(partialName)

    # if attempting "resume" and no .partial file exists, print warning and return False
    if requirePartial and not hasPartial:
        print(f"[EARTH PC]: No partial file found for resume: {partialName}. Start a download first, then use resume if interrupted.")
        return False

    # .partial file exists after "resume" command called
    if hasPartial:    
        try: 
            # attempt to read the size of the existing .partial file
            resumeOffset = os.path.getsize(partialName)

            # if the .partial is longer than the actual file on VIOLET2, use the tail command
            if resumeOffset > 0:
                print(f"[EARTH PC]: Found partial download ({resumeOffset} bytes). Attempting to resume download...")
        
        except OSError as e: # if there is an error reading the .partial file size, print a warning and start from the beginning of the file
            print(f"[EARTH PC]: Warning! Could not read partial file size: {e}")
            resumeOffset = 0

    def appendPartialFromBuffer(buffer_map: Dict[int, dict]):
        """
        Check the buffer map for any received fragments that can be appended to the .partial file, and append them in order if possible.
            - buffer_map: a dictionary mapping sequence numbers to dicts containing total packet count and received fragments for multi-packet responses.
        """
        # loop through each seq_num in the buffer map
        for seq, buf in buffer_map.items():
            # check if this seq_num corresponds to the current download, if not match ignore and continue to next seq_num
            fragments = buf.get("fragments", {})
            
            # if there are no fragments received for this seq_num yet, skip to the next one in the buffer map
            if not fragments:
                continue

            # if there ARE fragments received for this seq_num, check if we have a contiguous sequence from idx=0
            nextIdx = 0
            contiguous = [] 
            while nextIdx in fragments: 
                contiguous.append(fragments[nextIdx])
                nextIdx += 1
            
            # if no contiguous fragments starting from idx=0, nothing to append to .partial yet, skip to next seq_num in buffer map
            if not contiguous: 
                continue
            
            # if we have a contiguous sequence of fragments starting from idx=0, append chunk to .partial and remove fragments from the buffer map for seq_num 
            chunk = b"".join(contiguous).decode('ascii', errors='replace') 
            try:
                with open(partialName, 'a') as f: # write chunk to the .partial file
                    f.write(chunk)

                print(f"[EARTH PC]: Saved {len(chunk)} bytes of partial data (seq={seq}) to {partialName}")
            
            except Exception as write_err:
                print(f"[EARTH PC]: Warning! Failed to save partial data: {write_err}")

    ### BEGIN DOWNLOAD PROCESS ###

    # Step 4: Send command to satellite (resume uses tail from byte offset)
    if resumeOffset > 0: 
        raw_data = f"tail -c +{resumeOffset + 1} {remotePath}".encode('ascii')
    
    # if not resuming, use cat command
    else:
        raw_data = f"cat {remotePath}".encode('ascii')

    # build VIOLET2 packets for the command (fragmented if necessary)
    violet2Packets = violet2ProtocolBuilder(raw_data)

    # if the command was fragmented into multiple packets, print out how many packets will be sent to provide feedback to the user before transmission begins.
    if len(violet2Packets) > 1: 
        print(f"Fragmenting into {len(violet2Packets)} packets...\n")
    
    # Step 5: Transmit command as AX.25 packets
    for info in violet2Packets: 
        ax25Send(info)

    # flush buffer
    receiveSocket.setblocking(False)
    flushCount = 0
    try:
        while True:
            receiveSocket.recvfrom(EARTH_RECEIVE_BUFFER_SIZE) 
            flushCount += 1

    except (BlockingIOError, socket.error): 
        if flushCount > 0: 
            print(f"Flushed {flushCount} stale packets.")
    
    receiveSocket.settimeout(RECEIVE_TIMEOUT) # set the receive timeout

    # Step 6: loop to receive packets, looking for download response
    downloadBuffer = {}     
    totalReceived = 0 
    retryCount = 0
    downloadComplete = False

    try:
        # loop until download is complete or timeout
        while not downloadComplete and retryCount < DOWNLOAD_MAX_RETRIES:
            try:
                data, addr = receiveSocket.recvfrom(EARTH_RECEIVE_BUFFER_SIZE)

                # validate downlink response packet
                if not isAx25DownlinkPacket(data): 
                    print("[EARTH PC]: Error! Packet rejected due to unexpected AX.25 callsigns")
                    continue
                
                # if packet is valid, parse the VIOLET2 header and payload
                violet2Raw = data[AX25_HEADER_LEN:]
                parsed = parseViolet2Response(violet2Raw) 

                # if there was an error parsing the VIOLET2 packet, print the error message and continue to the next received packet
                if "error" in parsed: 
                    print(f"[EARTH PC]: Error! {parsed['error']}")
                    continue
                
                # parse VIOLET2 header fields and payload for valid packets
                messageType = parsed["msg_type"]
                sequenceNum = parsed["seq_num"]
                totalPackets = parsed["total_pkt"]
                packetIdx = parsed["pkt_idx"]
                payload = parsed["payload"]
                totalReceived += 1

                print(f"[Pass {totalReceived}] type=0x{messageType:02X} seq={sequenceNum} pkt {packetIdx+1}/{totalPackets} payload_len={parsed['payload_len']}")

                # Step 6.1: Handle single packet response
                if messageType == RESP_SINGLE:
                    fileContent = payload.decode('ascii', errors='replace') # decode payload as ASCII text
                    errorKeywords = ['no such file', 'cannot open', 'error', 'permission denied', 'is a directory']
                    isError = any(keyword in fileContent.lower() for keyword in errorKeywords) # check if response contains error message
                    
                    if isError: # Notify user of error
                        print(f"[EARTH PC]: Error! {fileContent}")
                        downloadComplete = True # download is marked as complete to exit the receive loop with a failure status
                        return False

                    # saving partial data if resuming, then renaming to final filename; if not resuming, write directly to final filename
                    if resumeOffset > 0 or os.path.exists(partialName):
                        with open(partialName, 'a') as f:
                            f.write(fileContent)
                        os.replace(partialName, localName)
                        if os.path.exists(partialName):
                            os.remove(partialName)
                    
                    # no .partial file, write the content to the specified local file.
                    else: 
                        with open(localName, 'w') as f: 
                            f.write(fileContent)

                    print(f"[EARTH PC]: Downloaded [{remotePath}] to [{localName}]") 
                    downloadComplete = True
                    return True

                # Step 6.2: Handle multi-packet responses
                elif messageType in (RESP_MULTI_START, RESP_MULTI_CONT, RESP_MULTI_END):

                    # if not the first packet of multi-packet response, check if we have buffered fragments for this seq_num.
                    if sequenceNum not in downloadBuffer:
                        downloadBuffer[sequenceNum] = {
                            "total_pkt": totalPackets,
                            "fragments": {},
                            "end_seen": False,
                            "last_nack_missing": set(),
                        }
                    
                    # buffer the received fragment in the downloadBuffer under its sequence number
                    buffer = downloadBuffer[sequenceNum]
                    buffer["total_pkt"] = max(buffer["total_pkt"], totalPackets)
                    buffer["fragments"][packetIdx] = payload

                    # if this packet has the RESP_MULTI_END message type, mark in the buffer we have seen the end of this message
                    if messageType == RESP_MULTI_END:
                        buffer["end_seen"] = True
                    
                    print(f"[EARTH PC]: Buffering fragment {packetIdx+1}/{totalPackets}...\n")

                    retryCount = 0
                    highestReceived = max(buffer["fragments"].keys(), default=-1) # find the highest packet index we have received so far for this sequence number
                    
                    # check for any missing packet indices from 0 up to the highest received index
                    missingSeenWindow = [ 
                        index
                        for index in range(highestReceived + 1)
                        if index not in buffer["fragments"]
                    ]

                    # if we have seen the end of the multi-packet message but there are still missing fragments at lower indices, send early NACK for those missing fragments
                    if missingSeenWindow:
                        missingSet = set(missingSeenWindow)

                        # only send NACK if the set of missing indices has changed since the last NACK for this seq_num
                        if missingSet != buffer["last_nack_missing"]:
                            _NACK(sequenceNum, missingSeenWindow) # send NACK
                            buffer["last_nack_missing"] = missingSet # update the buffer with the set of missing indices just NACK'd
                            print(
                                f"[EARTH PC]: Early NACK sent for seq={sequenceNum}, "
                                f"missing {len(missingSeenWindow)} fragment(s)"
                            )

                    # if we have seen the end of the multi-packet message but are still missing fragments, send NACK for those missing fragments (triggering retransmission from VIOLET2)
                    if buffer["end_seen"] and len(buffer["fragments"]) < buffer["total_pkt"]:

                        # list of missing packet indices based on total packet count in the buffer and which packet indices we have received so far
                        missing = [ 
                            index
                            for index in range(buffer["total_pkt"])
                            if index not in buffer["fragments"]
                        ]

                        # only send NACK if the set of missing indices has changed since the last NACK for this seq_num to avoid unnecessary retransmissions
                        missingSet = set(missing)

                        # if the set of missing indices has changed since the last NACK, send a new NACK with the updated list of missing fragments to request retransmission from VIOLET2 
                        if missingSet != buffer["last_nack_missing"]:
                            _NACK(sequenceNum, missing) # send NACK
                            buffer["last_nack_missing"] = missingSet # update buffer with the set of missing indices just NACK'd
                            print(
                                f"[EARTH PC]: NACK sent for seq={sequenceNum}, "
                                f"missing {len(missing)} fragment(s)"
                            )
                        continue
                    
                    # if we have seen the end of the multi-packet message and have received all fragments, we can reassemble the file content and save to disk
                    if buffer["end_seen"] and len(buffer["fragments"]) == buffer["total_pkt"]:
                        
                        print(f"[EARTH PC]: All {buffer['total_pkt']} fragments received, reassembling...\n")
                        fileContent = b"".join( # reassemble the file content by concatenating the fragments in order based on their packet index
                            buffer["fragments"][i] for i in range(buffer["total_pkt"])
                        ).decode('ascii', errors='replace')

                        # error handling 
                        errorKeywords = ['no such file', 'cannot open', 'error', 'permission denied', 'is a directory']
                        isError = any(keyword in fileContent.lower() for keyword in errorKeywords)

                        # if the reassembled content contains an error message, print the error and mark the download as complete with a failure status to exit the receive loop
                        if isError: 
                            print(f"[EARTH PC]: Error! {fileContent}\n")
                            del downloadBuffer[sequenceNum]
                            downloadComplete = True
                            return False

                        # saving partial data if resuming, then renaming to final filename; if not resuming, write directly to final filename.
                        if resumeOffset > 0 or os.path.exists(partialName):
                            with open(partialName, 'a') as f:
                                f.write(fileContent)
                            os.replace(partialName, localName)
                            if os.path.exists(partialName):
                                os.remove(partialName)
                        else:
                            with open(localName, 'w') as f:
                                f.write(fileContent)
    
                        _ACK(sequenceNum) # send ACK to VIOLET2 to confirm successful receipt of the complete multi-packet message
                        print(f"[EARTH PC]: Downloaded [{remotePath}] to [{localName}] {totalReceived} packets.\n")
                        del downloadBuffer[sequenceNum] # remove entry for this seq_num from buffer after successful download and ACK
                        downloadComplete = True
                        return True
                
                # Step 6.3: message type is not recognized
                else: 
                    print(f"[EARTH PC]: Error! Unexpected message type 0x{messageType:02X}")

            # Step 7: Handle receive timeout for download responses
            except socket.timeout: 
                retryCount += 1 

                # on timeout, check if buffer contains any incomplete multi-packet messages that we are still waiting for fragments on, and if so send NACKs for any missing fragments to trigger retransmission from VIOLET2.
                if downloadBuffer:

                    # loop through each seq_num in downloadBuffer
                    for seq, buf in downloadBuffer.items():
                        totalPkt = buf.get("total_pkt", 0)
                        fragments = buf.get("fragments", {})

                        # no fragments received for this seq_num yet, skip to next one in the buffer
                        if totalPkt <= 0 or not fragments:
                            continue

                        # if we have received some fragments for this seq_num but are still missing others, send NACK for the missing fragments to trigger retransmission from VIOLET2
                        missing = [
                            index
                            for index in range(totalPkt)
                            if index not in fragments
                        ]

                        # only send NACK if the set of missing indices has changed since the last NACK for this seq_num to avoid unnecessary retransmissions on subsequent timeouts
                        if missing:
                            _NACK(seq, missing)
                            buf["last_nack_missing"] = set(missing)
                            print(
                                f"[EARTH PC]: Timeout-triggered NACK for seq={seq}, "
                                f"missing {len(missing)} fragment(s)"
                            )
                
                # if we have not received any packets for the current download, timeout, print warning and retransmit if attempts remain.
                if retryCount < DOWNLOAD_MAX_RETRIES: 
                    print(f"[EARTH PC]: Timeout (attempt {retryCount}/{DOWNLOAD_MAX_RETRIES}), waiting for more packets...")
                
                else: # Timed out completely
                    print(f"[EARTH PC]: Connection Timeout: No more data after {DOWNLOAD_MAX_RETRIES} attempts")
                    
                    # on complete timeout, check if we have any fragments in the buffer for the current download, print warning indicating download is incomplete 
                    if downloadBuffer: 

                        # loop through each seq_num in the buffer and print fragments received vs. total expected
                        for seq, buf in downloadBuffer.items():
                            print(f"[EARTH PC] Incomplete transfer for seq={seq}: {len(buf['fragments'])}/{buf['total_pkt']} fragments")
                        
                        # if fragments were received but the file is incomplete, attempt to add new fragments to .partial if possible to save progress.
                        appendPartialFromBuffer(downloadBuffer)

    except KeyboardInterrupt:
        print("\n[EARTH PC]: Download interrupted by user (Ctrl+C).")
        if downloadBuffer:
            appendPartialFromBuffer(downloadBuffer)
            print(f"[EARTH PC]: Partial download saved to [{partialName}]")
            
        else:
            print("[EARTH PC]: No partial fragments to save.")

        return False

    except Exception as e: 
        print(f"Download error: {e}")
        if downloadBuffer:
            appendPartialFromBuffer(downloadBuffer)

    return False # if we exit the receive loop without completing the download, return False to indicate failure
