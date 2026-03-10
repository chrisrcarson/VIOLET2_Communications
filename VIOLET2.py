import socket
import subprocess
from violet2_utils import *
from violet2_utils import _buildViolet2Header, _padApplicationData

# fragment reassembly buffer, keyed by seq_num
reassemblyBuffer = {}

receiveSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
receiveSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # allow reuse of address if previous connection didn't close properly
receiveSocket.bind((RECEIVE_HOST, RECEIVE_PORT))

try:
    while True:
        data, addr = receiveSocket.recvfrom(512) # receive raw AX.25 packet
        print(f"[Received Data]: {data.hex()}")

        if not isAx25Packet(data):
            print("[VIOLET2 Error]: non-AX.25 packet rejected")
            continue

        violet2Raw = data[AX25_HEADER_LEN:] # strip AX.25 header before parsing VIOLET2 layer
        parsed = parseViolet2Packet(violet2Raw)

        if "error" in parsed:
            print(f"[VIOLET2 Error]: {parsed['error']}")
            continue

        messageType = parsed["msg_type"]
        sequenceNumber = parsed["seq_num"]
        print(f"[VIOLET2 Header]: type=0x{messageType:02X}  seq={sequenceNumber}  "
              f"pkt {parsed['pkt_idx']+1}/{parsed['total_pkt']}  "
              f"payload_len={parsed['payload_len']}  checksum=OK")

        if messageType == MSG_CMD_SINGLE: # single packet command, execute immediately
            command = parsed["payload"].decode('ascii', errors='replace')

        elif messageType == MSG_CMD_MULTI_START: # first fragment, start reassembly buffer for this seq
            reassemblyBuffer[sequenceNumber] = {
                "total_pkt": parsed["total_pkt"],
                "fragments": {parsed["pkt_idx"]: parsed["payload"]}
            }
            continue

        elif messageType in (MSG_CMD_MULTI_CONT, MSG_CMD_MULTI_END): # middle or final fragment, add to buffer
            if sequenceNumber not in reassemblyBuffer:
                print(f"[VIOLET2 Error]: received fragment for unknown seq {sequenceNumber}, discarding")
                continue
            reassemblyBuffer[sequenceNumber]["fragments"][parsed["pkt_idx"]] = parsed["payload"]

            if messageType == MSG_CMD_MULTI_END: # final fragment, check if all fragments are present
                buffer = reassemblyBuffer[sequenceNumber]
                if len(buffer["fragments"]) < buffer["total_pkt"]: # still missing fragments, wait for retransmit
                    print(f"[VIOLET2]: seq {sequenceNumber} incomplete, "
                          f"got {len(buffer['fragments'])}/{buffer['total_pkt']} fragments")
                    continue
                # reassemble in order and decode
                command = b"".join(
                    buffer["fragments"][i] for i in range(buffer["total_pkt"])
                ).decode('ascii', errors='replace')
                del reassemblyBuffer[sequenceNumber] # clean up buffer once reassembled
            else:
                continue

        elif messageType == MSG_PING: # ping request, respond immediately with a pong
            print(f"[VIOLET2]: ping received, sending pong")
            pongPayload = parsed["payload"]
            pongHeader = _buildViolet2Header(
                messageType=MSG_PONG,
                sequenceNumber=sequenceNumber,
                totalPackets=1,
                packetIndex=0,
                payloadLength=len(pongPayload),
            )
            ax25Send(pongHeader + _padApplicationData(pongPayload))
            continue

        else:
            print(f"[VIOLET2]: unhandled message type 0x{messageType:02X}")
            continue

        # execute command and send response
        print(f"Command: {command}")
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        print(f"Command output: {result.stdout}")

        # if command was successful but generated no output, send success message
        if result.returncode == 0 and not result.stdout.strip():
            response = "Command executed successfully (no output)".encode('ascii')
        elif result.returncode != 0:
            # if command failed, send error output if available
            errorMessage = result.stderr.strip() if result.stderr.strip() else f"Command failed with exit code {result.returncode}"
            response = errorMessage.encode('ascii')
        else:
            response = result.stdout.encode('ascii')
        
        violet2Packets = violet2ProtocolBuilder(response)

        if len(violet2Packets) > 1:
            print(f"Fragmenting response into {len(violet2Packets)} packets...")

        for info in violet2Packets:
            ax25Send(info)

except KeyboardInterrupt:
    print("\nShutting down VIOLET2 responder...")
finally:
    receiveSocket.close()
    print("Cleaned up connections.")