import socket

import time
import subprocess
import readline 
from earth_utils import *
from earth_utils import _buildViolet2Header, _padApplicationData

# Reassembly buffer for multi-packet responses, keyed by sequence number
receiveSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
receiveSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Allow reuse of address if previous connection didn't close properly
receiveSocket.bind((RECEIVE_HOST, RECEIVE_PORT))
receiveSocket.settimeout(RECEIVE_TIMEOUT)

# Initialize command history
historyFile = setupCommandHistory()

# Pre-fill the reassembly buffer with any packets that arrived before the main loop starts
def flushStalePackets(sock: socket.socket):
    previous_timeout = sock.gettimeout()
    sock.setblocking(False)
    try:
        while True:
            sock.recvfrom(512)
    except (BlockingIOError, socket.error):
        pass
    finally:
        # Restore caller-configured timeout/blocking mode.
        sock.settimeout(previous_timeout)

def sendAx25Packets(packets: list[bytes]):
    for info in packets:
        ax25Send(info)

# Validate if a single packet is an AX.25 downlink packet from the satellite, 
# returning the raw data if valid or None if invalid or timed out.
def receiveValidatedDownlinkPacket(sock: socket.socket, timeoutSeconds: float):
    deadline = time.time() + timeoutSeconds
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            return None

        sock.settimeout(remaining)
        try:
            data, _ = sock.recvfrom(512)
        except socket.timeout:
            return None

        if not isAx25DownlinkPacket(data):
            print("Unexpected AX.25 header in received packet")
            continue

        return data

isExiting = False
try:
    while not isExiting:

        userInput = input("VIOLET2> ").strip()
        
        if userInput.lower() == "quit":
            isExiting = True
            break
        
        if userInput.lower() == "clear":
            clearTerminal()
            continue
        
        if userInput.lower().startswith("download "): # local command: download <remote_path> [local_path]
            downloadFile(userInput, receiveSocket)
            continue

        if userInput.lower() == "ping": # local command: send a ping to VIOLET2 and measure round-trip time
            pingPayload = f"PING:{time.time():.6f}".encode('ascii')
            pingHeader = _buildViolet2Header(
                messageType=MSG_PING,
                sequenceNumber=0,
                totalPackets=1,
                packetIndex=0,
                payloadLength=len(pingPayload),
            )
            pingPacket = pingHeader + _padApplicationData(pingPayload)

            # flush stale packets before sending
            flushStalePackets(receiveSocket)
            receiveSocket.settimeout(PING_TIMEOUT) # shorter timeout for ping response since we expect it to be quick and want to retry faster if it fails

            pingSuccess = False
            totalAttempts = PING_MAX_RETRIES + 1
            for attempt in range(1, totalAttempts + 1): # attempt the ping multiple times if we don't get a valid response, to account for potential packet loss
                sendTime = time.time()
                ax25Send(pingPacket)

                data = receiveValidatedDownlinkPacket(receiveSocket, PING_TIMEOUT)
                if data is None:
                    if attempt < totalAttempts:
                        print(f"Ping timeout ({attempt}/{totalAttempts}), retransmitting in {RETRANSMIT_INTERVAL:.1f}s...")
                        time.sleep(RETRANSMIT_INTERVAL)
                        flushStalePackets(receiveSocket)
                        continue
                    continue

                try: # if we got a packet, check if it's a valid pong response to our ping and calculate round-trip time
                    rtt = (time.time() - sendTime) * 1000 # round-trip time in milliseconds
                    violet2Raw = data[AX25_HEADER_LEN:]
                    parsed = parseViolet2Response(violet2Raw)

                    if "error" not in parsed and parsed["msg_type"] == MSG_PONG:
                        print(f"Pong! Round-trip time: {rtt:.1f} ms\n")
                        pingSuccess = True
                        break

                    print(f"Unexpected response to ping (type=0x{parsed.get('msg_type', 0):02X})")
                    pingSuccess = True
                    break
                
                # If we got a response but it wasn't a valid pong, 
                # we consider the ping successful in terms of connectivity but print a warning about the unexpected response. 
                # We won't retry in this case.
                except socket.timeout:
                    if attempt < totalAttempts:
                        print(f"Ping timeout ({attempt}/{totalAttempts}), retransmitting in {RETRANSMIT_INTERVAL:.1f}s...")
                        time.sleep(RETRANSMIT_INTERVAL)
                        flushStalePackets(receiveSocket)
                        continue

                if attempt < totalAttempts: # continue to retry if we haven't exhausted all attempts yet
                    print(f"Ping attempt {attempt} did not produce a valid pong, retransmitting in {RETRANSMIT_INTERVAL:.1f}s...")
                    time.sleep(RETRANSMIT_INTERVAL)
                    flushStalePackets(receiveSocket)

            if not pingSuccess: # after exhausting all attempts, print final timeout message
                print(f"[VIOLET2]: Ping timed out after {totalAttempts} attempts")
            continue

        # Force flushing buffer
        flushStalePackets(receiveSocket)
        
        # For any other command, we assume it's a command to be sent to the satellite, 
        # so we build VIOLET2 packets and send them, then wait for and print the response. 
        # We also use retransmission logic in case we don't get a response within the timeout, 
        # to improve reliability over an intermittent connection.
        rawData = userInput.encode('ascii')
        violet2Packets = violet2ProtocolBuilder(rawData)
        
        if len(violet2Packets) > 1:
            print(f"Fragmenting into {len(violet2Packets)} packets...\n")

        totalCommandAttempts = COMMAND_MAX_RETRIES + 1
        responseComplete = False

        # Attempt to send the command and receive a complete response, with retries on timeout. 
        # We consider the command successful if we receive a valid response (even if it's an error message from the satellite), 
        # and we only retry if we don't get any valid response within the timeout.
        for attempt in range(1, totalCommandAttempts + 1):
            receiveSocket.settimeout(RECEIVE_TIMEOUT)
            sendAx25Packets(violet2Packets)

            try:
                responseBuffer = {}

                while not responseComplete: # keep receiving until we get a complete response or hit a timeout
                    data = receiveValidatedDownlinkPacket(receiveSocket, RECEIVE_TIMEOUT)
                    if data is None:
                        raise socket.timeout

                    print(f"[Data Received from VIOLET2]: {data.hex()}\n")

                    violet2Raw = data[AX25_HEADER_LEN:] # strip AX.25 header before parsing VIOLET2 layer
                    parsed = parseViolet2Response(violet2Raw)

                    if "error" in parsed:
                        print(f"[VIOLET2]: Error! {parsed['error']}")
                        break
                    
                    # Print VIOLET2 header info for debugging
                    messageType  = parsed["msg_type"]
                    sequenceNum  = parsed["seq_num"]
                    totalPackets = parsed["total_pkt"]
                    packetIdx    = parsed["pkt_idx"]

                    # We print the header info for each received fragment,
                    # which can help with debugging and understanding the flow of multi-packet responses.
                    print(f"[VIOLET2 Header]: type=0x{messageType:02X}  "
                          f"seq={sequenceNum}  "
                          f"pkt {packetIdx+1}/{totalPackets}  "
                          f"payload_len={parsed['payload_len']}  checksum=OK\n")

                    if messageType == RESP_SINGLE: # single packet, print immediately
                        print(f"[Response]:\n{parsed['payload'].decode('ascii', errors='replace')}")
                        responseComplete = True

                    elif messageType == RESP_MULTI_START: # first fragment, initiate buffer
                        responseBuffer[sequenceNum] = {
                            "total_pkt": totalPackets,
                            "fragments": {packetIdx: parsed["payload"]}
                        }

                    elif messageType in (RESP_MULTI_CONT, RESP_MULTI_END): # middle or final fragment
                        if sequenceNum not in responseBuffer:
                            print(f"[VIOLET2 Error]: fragment for unknown seq {sequenceNum}, discarding")
                            break
                        responseBuffer[sequenceNum]["fragments"][packetIdx] = parsed["payload"]

                        if messageType == RESP_MULTI_END: # last fragment, reassemble and print
                            buf = responseBuffer[sequenceNum]
                            if len(buf["fragments"]) == buf["total_pkt"]:
                                fullResponse = b"".join(
                                    buf["fragments"][i] for i in range(buf["total_pkt"])
                                ).decode('ascii', errors='replace')
                                print(f"[Response]:\n{fullResponse}")
                                del responseBuffer[sequenceNum]
                                responseComplete = True
                            else:
                                print(f"  Warning: RESP_MULTI_END but only have {len(buf['fragments'])}/{buf['total_pkt']} fragments")

            # We only retry sending the command if we didn't receive any valid response (including error responses) from the satellite.
            except socket.timeout:
                if attempt < totalCommandAttempts:
                    print(f"[VIOLET2]: Command timeout ({attempt}/{totalCommandAttempts}), retransmitting in {RETRANSMIT_INTERVAL:.1f}s...")
                    time.sleep(RETRANSMIT_INTERVAL)
                    flushStalePackets(receiveSocket)
                    continue
                print(f"[VIOLET2]: Connection Timeout: No data received after {totalCommandAttempts} attempts")

            if responseComplete: # if we got a complete response, we break out of the retry loop and go back to the command prompt
                break

            if attempt < totalCommandAttempts:
                print(f"[VIOLET2]: No complete response yet ({attempt}/{totalCommandAttempts}), retransmitting in {RETRANSMIT_INTERVAL:.1f}s...")
                time.sleep(RETRANSMIT_INTERVAL)
                flushStalePackets(receiveSocket)

except KeyboardInterrupt:
    pass  # Ctrl+C at the input() prompt

finally: # Cleanup
    # Save command history before exiting
    saveCommandHistory(historyFile)
    receiveSocket.close()
    print("\nCleaned up connections and saved history.")