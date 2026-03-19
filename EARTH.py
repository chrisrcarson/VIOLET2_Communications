import socket

import time
import subprocess
import readline  # used for command history and arrow key navigation on Unix/Linux/Mac
from earth_utils import *
from earth_utils import _buildViolet2Header, _padApplicationData

# receive and print response as byte string over UDP
receiveSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
receiveSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # allow reuse of address if previous connection didn't close properly
receiveSocket.bind((RECEIVE_HOST, RECEIVE_PORT))
receiveSocket.settimeout(RECEIVE_TIMEOUT) # timeout set in earth_utils.py

# setup command history for up/down arrow navigation
historyFile = setupCommandHistory()

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
            receiveSocket.settimeout(PING_TIMEOUT)

            pingSuccess = False
            totalAttempts = PING_MAX_RETRIES + 1
            for attempt in range(1, totalAttempts + 1):
                sendTime = time.time()
                ax25Send(pingPacket)

                try:
                    data, _ = receiveSocket.recvfrom(512)
                    rtt = (time.time() - sendTime) * 1000
                    if not isAx25DownlinkPacket(data):
                        print("Unexpected AX.25 header in ping response")
                    else:
                        violet2Raw = data[AX25_HEADER_LEN:]
                        parsed = parseViolet2Response(violet2Raw)
                        if "error" not in parsed and parsed["msg_type"] == MSG_PONG:
                            print(f"Pong! Round-trip time: {rtt:.1f} ms")
                            pingSuccess = True
                            break
                        print(f"Unexpected response to ping (type=0x{parsed.get('msg_type', 0):02X})")
                        pingSuccess = True
                        break
                except socket.timeout:
                    if attempt < totalAttempts:
                        print(f"Ping timeout ({attempt}/{totalAttempts}), retransmitting in {RETRANSMIT_INTERVAL:.1f}s...")
                        time.sleep(RETRANSMIT_INTERVAL)
                        flushStalePackets(receiveSocket)
                        continue

                if attempt < totalAttempts:
                    print(f"Ping attempt {attempt} did not produce a valid pong, retransmitting in {RETRANSMIT_INTERVAL:.1f}s...")
                    time.sleep(RETRANSMIT_INTERVAL)
                    flushStalePackets(receiveSocket)

            if not pingSuccess:
                print(f"Ping timed out after {totalAttempts} attempts")
            continue

        # force flushing buffer
        flushStalePackets(receiveSocket)
        
        # send the command and reset timeout
        rawData = userInput.encode('ascii')
        violet2Packets = violet2ProtocolBuilder(rawData)
        
        if len(violet2Packets) > 1:
            print(f"Fragmenting into {len(violet2Packets)} packets...")

        totalCommandAttempts = COMMAND_MAX_RETRIES + 1
        responseComplete = False
        for attempt in range(1, totalCommandAttempts + 1):
            receiveSocket.settimeout(RECEIVE_TIMEOUT)
            sendAx25Packets(violet2Packets)

            try:
                responseBuffer = {}

                while not responseComplete:
                    data, addr = receiveSocket.recvfrom(512) # buffer size of 512 bytes: 16 (AX.25 header) + 8 (VIOLET2 header) + 248 (max. app data) = 272 bytes -> round up to 512 for some margin
                    print(f"[Received Data]: {data.hex()}")

                    if not isAx25DownlinkPacket(data):
                        print("[VIOLET2 Error]: packet rejected due to unexpected AX.25 callsigns")
                        continue

                    violet2Raw = data[AX25_HEADER_LEN:] # strip AX.25 header before parsing VIOLET2 layer
                    parsed = parseViolet2Response(violet2Raw)

                    if "error" in parsed:
                        print(f"[VIOLET2 Error]: {parsed['error']}")
                        break

                    messageType  = parsed["msg_type"]
                    sequenceNum  = parsed["seq_num"]
                    totalPackets = parsed["total_pkt"]
                    packetIdx    = parsed["pkt_idx"]

                    print(f"[VIOLET2 Header]: type=0x{messageType:02X}  "
                          f"seq={sequenceNum}  "
                          f"pkt {packetIdx+1}/{totalPackets}  "
                          f"payload_len={parsed['payload_len']}  checksum=OK")

                    if messageType == RESP_SINGLE: # single packet, print immediately
                        print(f"Response: {parsed['payload'].decode('ascii', errors='replace')}")
                        responseComplete = True

                    elif messageType == RESP_MULTI_START: # first fragment, init buffer
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
                                print(f"Response: {fullResponse}")
                                del responseBuffer[sequenceNum]
                                responseComplete = True
                            else:
                                print(f"  Warning: RESP_MULTI_END but only have {len(buf['fragments'])}/{buf['total_pkt']} fragments")

            except socket.timeout:
                if attempt < totalCommandAttempts:
                    print(f"Command timeout ({attempt}/{totalCommandAttempts}), retransmitting in {RETRANSMIT_INTERVAL:.1f}s...")
                    time.sleep(RETRANSMIT_INTERVAL)
                    flushStalePackets(receiveSocket)
                    continue
                print(f"Connection Timeout: No data received after {totalCommandAttempts} attempts")

            if responseComplete:
                break

            if attempt < totalCommandAttempts:
                print(f"No complete response yet ({attempt}/{totalCommandAttempts}), retransmitting in {RETRANSMIT_INTERVAL:.1f}s...")
                time.sleep(RETRANSMIT_INTERVAL)
                flushStalePackets(receiveSocket)

except KeyboardInterrupt:
    pass  # Ctrl+C at the input() prompt — fall through to cleanup

finally:
    # Save command history before exiting
    saveCommandHistory(historyFile)
    receiveSocket.close()
    print("\nCleaned up connections and saved history.")