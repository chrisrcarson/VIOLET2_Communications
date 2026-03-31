import socket
import subprocess
import threading
import time
from violet2_utils import *
from violet2_utils import _buildViolet2Header, _padApplicationData

# receive socket setup
receiveSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
receiveSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # allow reuse of address if previous connection didn't close properly
receiveSocket.bind((RECEIVE_HOST, RECEIVE_PORT))

# transmit socket setup (reused for all sends)
transmitSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

reassemblyBuffer = {} # fragment reassembly buffer (key: sequenceNumber, value: dict with total_pkt) then contains additional dict with fragments
downlinkResponseCache = {} # cache of recent downlink responses (key: sequenceNumber, value: list of packets) for potential retransmission on NACK

##################################################
# Antenna switch / TX timing constants
##################################################
BAUD_RATE          = 1200   # must match GNU Radio baud_rate parameter
AX25_OVERHEAD      = 17     # bytes: flags + addresses + control + PID + FCS
BIT_STUFF_FACTOR   = 1.2    # worst-case HDLC bit stuffing overhead
PREAMBLE_BYTES     = 20     # num_preamble_bytes in hdlc_framer_with_preamble
POSTAMBLE_BYTES    = 20     # num_postamble_bytes in hdlc_framer_with_preamble
TX_SAFETY_MARGIN   = 0.5    # seconds added after calculated on-air time

# Timer handle — used to cancel a pending RX switchback if a new TX starts
# before the previous window has expired (e.g. back-to-back retransmissions)
_rxSwitchbackTimer = None
_rxSwitchbackLock  = threading.Lock()

def _calcTxDuration(payloadBytes: int) -> float:
    """
    Calculate the on-air duration in seconds for a single AX.25/HDLC frame.

    Accounts for:
      - AX.25 frame overhead (17 bytes)
      - Worst-case HDLC bit stuffing (x1.2)
      - GNU Radio preamble + postamble bytes (40 bytes total)
      - Safety margin (TX_SAFETY_MARGIN seconds)

    Formula:
      tx_time = ((payload + AX25_OVERHEAD) * BIT_STUFF_FACTOR + PREAMBLE + POSTAMBLE) * 8 / BAUD_RATE
    """
    on_air = ((payloadBytes + AX25_OVERHEAD) * BIT_STUFF_FACTOR + PREAMBLE_BYTES + POSTAMBLE_BYTES) * 8 / BAUD_RATE
    return on_air + TX_SAFETY_MARGIN

def _calcTotalTxDuration(packets: list) -> float:
    """
    Calculate the total on-air duration for a list of VIOLET2 packets (fragments).
    Each packet is a bytes object; its full length is used as the payload size
    since VIOLET2 header + application data are all encapsulated inside the AX.25 frame.
    Durations are summed across all fragments.
    """
    return sum(_calcTxDuration(len(pkt)) for pkt in packets)

def _setAntennaTX():
    """Switch antenna to TX mode via GPIO (61=1)."""
    subprocess.run(["gpioset", "-t", "0", "-c", "2", "61=1"], check=False)
    print("[GPIO]: Antenna switched to TX mode (61=1)\n")

def _setAntennaRX():
    """Switch antenna back to RX mode via GPIO (61=0)."""
    subprocess.run(["gpioset", "-t", "0", "-c", "2", "61=0"], check=False)
    print("[GPIO]: Antenna switched to RX mode (61=0)\n")

def _scheduleSwitchbackToRX(duration: float):
    """
    Switch antenna to TX immediately, then schedule a return to RX after
    `duration` seconds. If a switchback is already pending, cancel it and
    extend the window — this handles back-to-back retransmissions correctly.
    """
    global _rxSwitchbackTimer

    with _rxSwitchbackLock:
        # cancel any pending switchback so we don't flip to RX mid-transmit
        if _rxSwitchbackTimer is not None and _rxSwitchbackTimer.is_alive():
            _rxSwitchbackTimer.cancel()
            print(f"[GPIO]: TX window extended by {duration:.3f}s\n")
        else:
            _setAntennaTX() # only call gpioset 61=1 if we weren't already in TX

        _rxSwitchbackTimer = threading.Timer(duration, _setAntennaRX)
        _rxSwitchbackTimer.daemon = True
        _rxSwitchbackTimer.start()
        print(f"[GPIO]: RX switchback scheduled in {duration:.3f}s\n")

def _NACK(sequenceNumber: int, missingIndices: list[int]):
    """
    Send a NACK message for a specific sequence number and list of missing packet indices.
        - sequenceNumber: the seq_num of the original message being NACKed
        - missingIndices: list of packet indices that are missing (0-based)
    """
    nackPayload = bytes(
            [sequenceNumber & 0xFF] +  # seq_num as first byte
            [i & 0xFF for i in missingIndices] # list of missing packet indices as remaining bytes
        )
    nackHeader = _buildViolet2Header(MSG_NACK, sequenceNumber, 1, 0, len(nackPayload)) # build VIOLET2 header for NACK message
    nackPacket = nackHeader + _padApplicationData(nackPayload)

    txDuration = _calcTxDuration(len(nackPacket))
    _scheduleSwitchbackToRX(txDuration)
    ax25Send(nackPacket, txSocket=transmitSocket) # send NACK
    print(f"[VIOLET2]: NACK sent for seq={sequenceNumber}, missing={missingIndices} (tx_hold={txDuration:.3f}s)\n")

def _resendRequestedFragments(sequenceNumber: int, requestedIndices: list[int]):
    """
    Resend specific fragments of a previously sent multi-packet response based on a NACK request.
        - sequenceNumber: the seq_num of the original message being retransmitted
        - requestedIndices: list of packet indices to resend (0-based)
    If requestedIndices is empty, resend all fragments for the sequenceNumber.
    """
    packets = downlinkResponseCache.get(sequenceNumber) # get cached packets for this seq_num
    
    # no packets matching that sequence number, can't retransmit anything
    if packets is None: 
        print(f"[VIOLET2]: no cached response for seq={sequenceNumber}, cannot retransmit.")
        return

    # no specific indices found at requested indices, resend all packets for this seq_num
    if not requestedIndices:
        requestedIndices = list(range(len(packets)))

    # collect the subset of packets we'll actually resend
    toResend = [packets[i] for i in sorted(set(requestedIndices)) if 0 <= i < len(packets)]

    if not toResend:
        print(f"[VIOLET2]: no valid fragments to retransmit for seq={sequenceNumber}")
        return

    # calculate total TX window covering all retransmitted fragments, then switch antenna
    totalDuration = _calcTotalTxDuration(toResend)
    _scheduleSwitchbackToRX(totalDuration)

    for pkt in toResend:
        ax25Send(pkt, txSocket=transmitSocket)

    print(f"[VIOLET2]: retransmitted {len(toResend)} fragment(s) for seq={sequenceNumber} (tx_hold={totalDuration:.3f}s)")

def receiveValidatedUplinkPacket(sock: socket.socket):
    """
    Receive and validate an incoming AX.25 uplink packet.
    Returns: the validated packet data.
    """
    # loop until we receive a valid packet with expected AX.25 header (callsigns, control, PID)
    while True: 
        data, addr = sock.recvfrom(VIOLET2_RECEIVE_BUFFER_SIZE)
        print(f"[RECEIVED DATA]: {data.hex()} \n")

        # check if packet has a valid AX.25 header
        if not isAx25UplinkPacket(data): 
            print("[VIOLET2]: Error! Packet rejected due to unexpected AX.25 callsigns")
            continue
        
        # return validated, violet2Packet data packets for further processing
        return data 

try: 
    while True: # main loop (receive, parse, execute, respond)
        
        # Step 1: validate and parse incoming packet
        data = receiveValidatedUplinkPacket(receiveSocket) 

        # Step 2: strip AX.25 header and parse VIOLET2 layer
        rawData = data[AX25_HEADER_LEN:] 
        violet2Packet = parseViolet2Packet(rawData)

        # if there was an error parsing the VIOLET2 packet (e.g., checksum failure), log the error and skip packet
        if "error" in violet2Packet:
            print(f"[VIOLET2]: Error! {violet2Packet['error']}")
            continue

        # Step 3: Process VIOLET2 packet based on message type, execute commands, and build responses
        messageType = violet2Packet["msg_type"]
        sequenceNumber = violet2Packet["seq_num"]
        print(f"[VIOLET2 Header]: type=0x{messageType:02X} seq={sequenceNumber}  "
              f"pkt {violet2Packet['pkt_idx'] + 1}/{violet2Packet['total_pkt']}  "
              f"payload_len={violet2Packet['payload_len']} checksum=OK\n")

        # Step 3.1: Handle a single packet command (executed immediately without reassembly)
        if messageType == MSG_CMD_SINGLE:
            command = violet2Packet["payload"].decode('ascii', errors='replace')

        # Step 3.2: Handle the first packet in a multi-part packet
        elif messageType == MSG_CMD_MULTI_START: 
            reassemblyBuffer[sequenceNumber] = { # initialize the reassemblyBuffer for this seq_num with total_pkt count and first fragment idx
                "total_pkt": violet2Packet["total_pkt"],
                "fragments": {violet2Packet["pkt_idx"]: violet2Packet["payload"]}
            }
            # Example: 
            # reassemblyBuffer[seq=1] = { 
            #   "total_pkt": total_pkt=2,
            #   "fragments": {pkt_idx=0: payload=b"Hello, world!"}, {pkt_idx=1: payload=b" How are you?"}}
            # }
            continue
        
        # Step 3.2: Handle middle or end packets in a multi-part packet sequence
        elif messageType in (MSG_CMD_MULTI_CONT, MSG_CMD_MULTI_END):
            
            # if we haven't seen the first packet fragment for this seq_num by checking the reassembly buffer, can't continue processing
            if sequenceNumber not in reassemblyBuffer:
                print(f"[VIOLET2]: Error! Received fragment for seq={sequenceNumber} (unknown), discarding")
                missingIndices = list(range(violet2Packet["pkt_idx"])) # add to list of missing indices for this seq_num (from 0 to current pkt_idx - 1)

                # if we get a middle or end fragment without having seen the start, we can NACK all previous indices since we know they're missing
                if missingIndices:
                    _NACK(sequenceNumber, missingIndices)
                continue

            # if we HAVE seen the first packet fragment for this seq_num, add the current fragment to reassemblyBuffer (this includes middle fragments)
            reassemblyBuffer[sequenceNumber]["fragments"][violet2Packet["pkt_idx"]] = violet2Packet["payload"]

            # if this is the last packet in the sequence, check if we have all fragments
            if messageType == MSG_CMD_MULTI_END: 

                # if we don't have all fragments, we can NACK the missing ones
                buffer = reassemblyBuffer[sequenceNumber]

                # if we don't have all fragments, send a NACK with the missing indices and wait for retransmission
                if len(buffer["fragments"]) < buffer["total_pkt"]:

                    # collect missing packet indices for this seq_num (from 0 to total_pkt - 1)
                    missingIndices = [
                        i for i in range(buffer["total_pkt"])
                        if i not in buffer["fragments"]
                    ] 

                    if missingIndices: # if any are missing, send NACK for those indices
                        _NACK(sequenceNumber, missingIndices)

                    print(f"[VIOLET2]: seq={sequenceNumber} incomplete, received {len(buffer['fragments'])}/{buffer['total_pkt']} fragments")
                    continue

                # if we have all fragments, reassemble the command and clean up the reassembly buffer for this seq_num
                command = b"".join(
                    buffer["fragments"][i] for i in range(buffer["total_pkt"])
                ).decode('ascii', errors='replace')

                del reassemblyBuffer[sequenceNumber] # clean up buffer once reassembled
                print(f"[VIOLET2]: seq={sequenceNumber} reassembled: {command}")

            # if middle fragment, wait for more fragments to arrive before processing
            else: 
                print(f"[VIOLET2]: seq={sequenceNumber} received fragment {violet2Packet['pkt_idx'] + 1}/{violet2Packet['total_pkt']}, waiting for more...")
                continue
        
        # Handle ping requests
        elif messageType == MSG_PING:
            print(f"[VIOLET2]: ping received, sending pong\n")
            pongPayload = violet2Packet["payload"] # echo back the same payload in the pong response
            pongHeader = _buildViolet2Header( # build VIOLET2 header for pong response
                messageType=MSG_PONG,
                sequenceNumber=sequenceNumber,
                totalPackets=1,
                packetIndex=0,
                payloadLength=len(pongPayload),
            )
            pongPacket = pongHeader + _padApplicationData(pongPayload)
            txDuration = _calcTxDuration(len(pongPacket))
            _scheduleSwitchbackToRX(txDuration)
            ax25Send(pongPacket, txSocket=transmitSocket)
            continue
        
        # Step 3.3: Handle NACK messages for retransmissions
        elif messageType == MSG_NACK:
            payload = violet2Packet["payload"] # payload structure: [seq_num (1 byte), missing_idx_1, missing_idx_2, ...]
            
            # if no seq_num in the payload, we can not process this NACK
            if len(payload) < 1: 
                print("[VIOLET2]: Error! Payload for NACK message is too short, cannot process")
                continue
            
            nackSeq = payload[0] # extract NACK seq_num from first byte of payload
            missingIndices = list(payload[1:]) # extract missing packet indices from remaining payload bytes (if any)
            print(f"[VIOLET2]: NACK received for seq={nackSeq}, missing={missingIndices}")
            _resendRequestedFragments(nackSeq, missingIndices) # resend the requested fragments from NACK payload list
            continue
        
        # Step 3.4: Handle ACK messages to clear cached responses that have been successfully received by the earth station
        elif messageType == MSG_ACK:
            payload = violet2Packet["payload"] # payload structure: [seq_num (1 byte)]

            # if no seq_num in the payload, we can not process this ACK
            if len(payload) < 1: 
                print("[VIOLET2]: Error! Payload for ACK message is too short, cannot process")
                continue
            
            ackSeq = payload[0] # extract ACK seq_num from first byte of payload
            if ackSeq in downlinkResponseCache: # if we have a cached response for this seq_num, we can delete them (ACK indicates received successfully)
                del downlinkResponseCache[ackSeq]
                print(f"[VIOLET2]: ACK received for seq={ackSeq}, cleared cached response")
            
            continue 
        
        # Step 3.5: Handle unknown message types by logging and ignoring the packet
        else: 
            print(f"[VIOLET2]: unhandled message type 0x{messageType:02X}")
            continue

        # Step 4: Execute the command
        print(f"[COMMAND]: {command}\n")
        result = subprocess.run(command, shell=True, capture_output=True, text=True) # this is the actual subprocess
        print(f"[COMMAND OUTPUT]: {result.stdout}\n") # DEBUGGING: printing results to console

        # Step 4.1: Handle successful execution with no output
        if result.returncode == 0 and not result.stdout.strip():
            response = "Command executed successfully (no output)".encode('ascii')

        # Step 4.2: Handle command failed with error output
        elif result.returncode != 0:
            errorMessage = result.stderr.strip() if result.stderr.strip() else f"Command failed with exit code {result.returncode}"
            response = errorMessage.encode('ascii')

        # Step 4.3: Handle successful execution WITH output
        else:
            response = result.stdout.encode('ascii')
        
        # Step 5: Build VIOLET2 response packets (fragmented if needed) and send them to the AX.25 layer for transmission
        violet2Packets = violet2ProtocolBuilder(response)

        # Step 5.1: Cache fragmented responses for any potential retransmissions
        if violet2Packets and len(violet2Packets) > 1:
            responseSeq = violet2Packets[0][1] # first packet, index 1 is the sequence number in the VIOLET2 header
            downlinkResponseCache[responseSeq] = violet2Packets # cache the list of packets for this seq_num

        # if fragmentation needed, print how many packets will be sent for this response
        if len(violet2Packets) > 1: 
            print(f"Fragmenting response into {len(violet2Packets)} packets...\n")

        # Step 5.2: Calculate total TX window covering all fragments, switch antenna to TX,
        # then send all packets. The timer will flip back to RX once the window expires.
        totalTxDuration = _calcTotalTxDuration(violet2Packets)
        _scheduleSwitchbackToRX(totalTxDuration)
        print(f"[GPIO]: TX window = {totalTxDuration:.3f}s for {len(violet2Packets)} packet(s)\n")

        for info in violet2Packets: 
            ax25Send(info, txSocket=transmitSocket)

except KeyboardInterrupt:
    print("\nShutting down VIOLET2 responder...")
finally:
    # ensure antenna is back in RX mode and timer is cancelled on exit
    with _rxSwitchbackLock:
        if _rxSwitchbackTimer is not None and _rxSwitchbackTimer.is_alive():
            _rxSwitchbackTimer.cancel()
    _setAntennaRX()
    receiveSocket.close()
    transmitSocket.close()
    print("Cleaned up connections.")