import socket
import time
import subprocess
import readline 
from earth_utils import *
from earth_utils import _buildViolet2Header, _padApplicationData, HELP_TEXT

# receive socket setup
receiveSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
receiveSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Allow reuse of address if previous connection didn't close properly
receiveSocket.bind((RECEIVE_HOST, RECEIVE_PORT))
receiveSocket.settimeout(RECEIVE_TIMEOUT)

# transmit socket setup (reused for all sends)
transmitSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# initialize command history
historyFile = setupCommandHistory()

def printHelp():
    print(f"{HELP_TEXT}\n")

def flushStalePackets(sock: socket.socket):
    """"
    Flush stale packets from the socket buffer.
    """
    previous_timeout = sock.gettimeout()
    sock.setblocking(False)
    try:
        while True:
            sock.recvfrom(EARTH_RECEIVE_BUFFER_SIZE)
    except (BlockingIOError, socket.error):
        pass
    finally:
        # Restore timeout/blocking modes.
        sock.settimeout(previous_timeout)

def receiveValidatedDownlinkPacket(sock: socket.socket, timeoutSeconds: float):
    """
    Receive and validate an incoming AX.25 downlink packet.
    Returns: the validated packet data or None if timed out.
    """
    deadline = time.time() + timeoutSeconds # calculate deadline for receiving a valid packet based on current time and timeout duration
    while True: # loop until a valid packet is received or timeout
        remaining = deadline - time.time()

        if remaining <= 0: # if deadline passed, return None to indicate timeout
            return None

        sock.settimeout(remaining) # set socket timeout to remaining time until deadline for this receive
        try:
            data, addr = sock.recvfrom(EARTH_RECEIVE_BUFFER_SIZE) # fetch data packet from socket
        except socket.timeout:
            return None

        if not isAx25DownlinkPacket(data): # validate that it is an AX.25 packet from the satellite
            print("[EARTH Terminal]: Error! Unexpected AX.25 header in received packet")
            continue

        return data 

isExiting = False # flag to control main loop exit

try: # main command loop
    while not isExiting: 

        # Step 1: Get user input and handle local commands (help, clear, download, resume, ping) before sending to satellite.
        userInput = input("VIOLET2> ").strip()
        
        if userInput.lower() == "quit": # quit command to exit the program
            isExiting = True
            break
        
        if userInput.lower() == "clear": # local command to clear the terminal screen
            clearTerminal()
            continue

        if userInput.lower() == "help": # local command to print help text
            printHelp()
            continue
        
        if userInput.lower().startswith("download "): # local command: download <remote_path> [local_path]
            downloadFile(userInput, receiveSocket) 
            continue

        if userInput.lower().startswith("resume "): # local command: resume <remote_path> [local_path]
            resumeInput = "download " + userInput[7:].strip() # convert resume command into download command format for reuse of downloadFile function
            downloadFile(resumeInput, receiveSocket, requirePartial=True) # call downloadFile with requirePartial=True to allow resuming from partial file if it exists, and pass the receiveSocket for receiving the file data
            continue

        if userInput.lower() == "ping": # local command: send a ping to VIOLET2 and measure round-trip time
            pingPayload = f"PING:{time.time():.6f}".encode('ascii') # create a ping payload with current timestamp for RTT measurement
            pingHeader = _buildViolet2Header( # build VIOLET2 header for the ping message
                messageType=MSG_PING,
                sequenceNumber=0,
                totalPackets=1,
                packetIndex=0,
                payloadLength=len(pingPayload),
            )
            pingPacket = pingHeader + _padApplicationData(pingPayload) 

            # flush buffer
            flushStalePackets(receiveSocket)
            receiveSocket.settimeout(PING_TIMEOUT) # set socket timeout for receiving the ping response
            
            pingSuccess = False 
            totalAttempts = PING_MAX_RETRIES + 1 # track number of ping attempts (includes the initial attempt plus the retries)
            
            # actually send the ping and wait for a valid "pong" response
            for attempt in range(1, totalAttempts + 1):
                sendTime = time.time() # record sent time
                ax25Send(pingPacket, txSocket=transmitSocket) # send the ping packet

                data = receiveValidatedDownlinkPacket(receiveSocket, PING_TIMEOUT) # wait for response
                
                # if not data received within timeout, print timeout message and retry if attempts remain
                if data is None:
                    if attempt < totalAttempts:
                        print(f"[EARTH Terminal]: Ping timeout ({attempt}/{totalAttempts}), retransmitting...")
                        flushStalePackets(receiveSocket)
                        continue
                    continue

                # if we got a packet, check if it's a valid pong response to our ping and calculate round-trip time
                rtt = (time.time() - sendTime) * 1000 # round-trip time in milliseconds
                violet2Raw = data[AX25_HEADER_LEN:]
                parsed = parseViolet2Response(violet2Raw)

                # check if the satellite responded with an error message
                if "error" in parsed:
                    print(f"[EARTH Terminal]: Invalid ping response: {parsed['error']}")

                # if the response was a valid pong, consider the ping successful and print the round-trip time
                elif parsed["msg_type"] == MSG_PONG:
                    print(f"[EARTH Terminal]: Pong! Round-trip time: {rtt:.1f} ms\n")
                    pingSuccess = True
                    break

                # if we got some other type of response, print a message but don't consider ping successful
                else:
                    print(f"[EARTH Terminal]: Unexpected ping response type=0x{parsed['msg_type']:02X}")
                
                # if we didn't get a valid pong response, print a message and retry if attempts remain
                if attempt < totalAttempts: # retry if attempts remain
                    print(f"[EARTH Terminal]: Ping attempt {attempt} did not produce a valid pong, retransmitting...")
                    flushStalePackets(receiveSocket) # flush any packets (partial or full) received during this attempt before retrying

            # no ping after all attempts, print timeout message
            if not pingSuccess: 
                print(f"[EARTH Terminal]: Ping timed out after {totalAttempts} attempts")

            continue
        
        # Step 2: Handle any other command (shell)
        flushStalePackets(receiveSocket) # flush stale packets
        rawData = userInput.encode('ascii') # encode the user input command as ASCII bytes for transmission
        violet2Packets = violet2ProtocolBuilder(rawData) # rebuild the command into VIOLET2 packet(s)

        totalCommandAttempts = COMMAND_MAX_RETRIES + 1 # total attempts to send the command
        responseComplete = False 

        if len(violet2Packets) > 1: # if the command was fragmented, print number of expected packets
            print(f"Fragmenting into {len(violet2Packets)} packets...\n")

        # attempt to send the command and receive a complete response. 
        for attempt in range(1, totalCommandAttempts + 1):

            # set timeout for receive
            receiveSocket.settimeout(RECEIVE_TIMEOUT)
            
            # Step 3: Transmit each packet of the command using AX.25 
            for info in violet2Packets: 
                ax25Send(info, txSocket=transmitSocket)

            try:
                responseBuffer = {} # buffer to store multi-packet fragment responses (key: sequenceNumber, value: dict with total_pkt and fragments)

                while not responseComplete: # keep receiving until we get a complete response or timeout

                    # Step 4: validate and parse incoming response packet 
                    data = receiveValidatedDownlinkPacket(receiveSocket, RECEIVE_TIMEOUT) 
                    
                    # handle timeout
                    if data is None:
                        raise socket.timeout 

                    print(f"[EARTH Terminal]: Response from VIOLET2\n{data.hex()}\n")

                    # Step 5: strip AX.25 header and parse the VIOLET2 response
                    violet2Raw = data[AX25_HEADER_LEN:]
                    parsed = parseViolet2Response(violet2Raw)

                    # handle error in response
                    if "error" in parsed: 
                        print(f"[VIOLET2]: Error! {parsed['error']}")
                        break
                    
                    # Step 3: Process VIOLET2 packet based on message type, execute commands, and build responses
                    messageType  = parsed["msg_type"]
                    sequenceNum  = parsed["seq_num"]
                    totalPackets = parsed["total_pkt"]
                    packetIdx    = parsed["pkt_idx"]

                    print(f"[VIOLET2 Header]: type=0x{messageType:02X}  "
                          f"seq={sequenceNum}  "
                          f"pkt {packetIdx+1}/{totalPackets}  "
                          f"payload_len={parsed['payload_len']}  checksum=OK\n")

                    # Step 3.1: handle single-packet response
                    if messageType == RESP_SINGLE:
                        print(f"[Response]:\n{parsed['payload'].decode('ascii', errors='replace')}")
                        responseComplete = True

                    # Step 3.2: handle start of multi-packet response
                    elif messageType == RESP_MULTI_START: # first fragment, initiate buffer
                        responseBuffer[sequenceNum] = {
                            "total_pkt": totalPackets,
                            "fragments": {packetIdx: parsed["payload"]}
                        }

                    # Step 3.3: handle middle or end of multi-packet response
                    elif messageType in (RESP_MULTI_CONT, RESP_MULTI_END): # middle or final fragment

                        # if a multi-packet response fragment is received but no start fragment was stored in the buffer
                        if sequenceNum not in responseBuffer:
                            print(f"[VIOLET2]: Error! Fragment for seq={sequenceNum} unknown, discarding")
                            break

                        # if we HAVE seen the first packet fragment for this seq_num, add the current fragment to the buffer
                        responseBuffer[sequenceNum]["fragments"][packetIdx] = parsed["payload"]

                        # handle end of multi-packet response
                        if messageType == RESP_MULTI_END:

                            buf = responseBuffer[sequenceNum] # get the buffered fragments for this seq_num

                            # check that all fragments are accounted for
                            if len(buf["fragments"]) == buf["total_pkt"]:
                                
                                fullResponse = b"".join( # reassemble in order based on pkt_idx and decode as ASCII for display
                                    buf["fragments"][i] for i in range(buf["total_pkt"])
                                ).decode('ascii', errors='replace')
                                print(f"[EARTH Terminal]: Response from VIOLET2\n{fullResponse}\n") 

                                del responseBuffer[sequenceNum] # delete packets in buffer at this seq_num
                                responseComplete = True 
                            
                            # received end but some fragments are missing
                            else:
                                print(f"[EARTH Terminal]: Warning! RESP_MULTI_END but only have {len(buf['fragments'])}/{buf['total_pkt']} fragments")

            #  Step 6: handle timeout at any point during reception, print a message and retransmit if attempts remain
            except socket.timeout:
                if attempt < totalCommandAttempts:
                    print(f"[EARTH Terminal]: No response packet before timeout ({attempt}/{totalCommandAttempts}). Retransmitting command...")
                    flushStalePackets(receiveSocket)
                    continue

                # Final attempt timeout warning
                print(f"[EARTH Terminal]: No response packet received after {totalCommandAttempts} attempts")

            # Step 7: if complete response received, break out of loop
            if responseComplete:
                break
            
            # Step 8: if response incomplete, print a message and retransmit if attempts remain
            if attempt < totalCommandAttempts:
                print(f"[EARTH Terminal]: Response received but incomplete (missing fragment(s)) ({attempt}/{totalCommandAttempts}). Retransmitting command...")
                flushStalePackets(receiveSocket)

except KeyboardInterrupt:
    print("\nShutting down EARTH Terminal...")
    pass  # Ctrl+C at the input() prompt

finally: # final cleanup on exit, save command history and close socket
    saveCommandHistory(historyFile)
    receiveSocket.close()
    print("\nCleaned up connections and saved history.")