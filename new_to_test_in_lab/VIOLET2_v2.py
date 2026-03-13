import socket
import subprocess
import shlex
from time import sleep
from violet2_utils_v2 import *
from violet2_utils_v2 import _buildViolet2Header, _padApplicationData, _fragmentData

# fragment reassembly buffer, keyed by seq_num
reassemblyBuffer = {}

# cached file fragments by remote path for download polling
downloadFragmentCache = {}


def _readCommandOutput(commandText: str) -> tuple[bool, bytes]:
    result = subprocess.run(commandText, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        errorMessage = result.stderr.strip() if result.stderr.strip() else f"Command failed with exit code {result.returncode}"
        return False, errorMessage.encode('ascii', errors='replace')
    if not result.stdout.strip():
        return True, b"Command executed successfully (no output)"
    return True, result.stdout.encode('ascii', errors='replace')


def _getOrBuildDownloadFragments(remotePath: str) -> tuple[bool, list[bytes] | bytes]:
    if remotePath in downloadFragmentCache:
        return True, downloadFragmentCache[remotePath]

    ok, payload = _readCommandOutput(f"cat {shlex.quote(remotePath)}")
    if not ok:
        return False, payload

    fragments = _fragmentData(payload)
    if not fragments:
        fragments = [b""]

    downloadFragmentCache[remotePath] = fragments
    return True, fragments


def _handleDownloadPollingCommand(command: str) -> tuple[bool, bytes, bool]:
    if command.startswith("dlmeta "):
        remotePath = command[7:].strip()
        if not remotePath:
            return True, b"V2ERR missing remote path for dlmeta", True
        ok, fragmentsOrError = _getOrBuildDownloadFragments(remotePath)
        if not ok:
            return True, b"V2ERR " + fragmentsOrError, True
        fragments = fragmentsOrError
        totalPackets = len(fragments)
        totalBytes = sum(len(chunk) for chunk in fragments)
        metadata = f"V2META total={totalPackets} bytes={totalBytes}".encode('ascii', errors='replace')
        return True, metadata, True

    if command.startswith("dlfrag "):
        parts = command.split(" ", 2)
        if len(parts) < 3:
            return True, b"V2ERR usage: dlfrag <index> <remote_path>", True
        indexText = parts[1].strip()
        remotePath = parts[2].strip()
        if not remotePath:
            return True, b"V2ERR missing remote path for dlfrag", True
        try:
            fragmentIndex = int(indexText)
        except ValueError:
            return True, b"V2ERR fragment index must be an integer", True

        ok, fragmentsOrError = _getOrBuildDownloadFragments(remotePath)
        if not ok:
            return True, b"V2ERR " + fragmentsOrError, True
        fragments = fragmentsOrError

        if fragmentIndex < 0 or fragmentIndex >= len(fragments):
            return True, f"V2ERR fragment index {fragmentIndex} out of range (0..{len(fragments) - 1})".encode('ascii', errors='replace'), True

        return True, fragments[fragmentIndex], True

    return False, b"", False

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

        elif messageType in (MSG_PONG, RESP_SINGLE, RESP_MULTI_START, RESP_MULTI_CONT, RESP_MULTI_END, MSG_ACK, MSG_NACK): # our own transmissions looping back via RF, ignore
            print(f"[VIOLET2]: loopback packet type=0x{messageType:02X} ignored")
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

        handled, response, _ = _handleDownloadPollingCommand(command)
        if handled:
            if command.startswith("dlmeta "):
                remotePath = command[7:].strip()
                cachedCount = len(downloadFragmentCache.get(remotePath, []))
                print(f"Download metadata prepared for {remotePath} ({cachedCount} fragments)")
            elif command.startswith("dlfrag "):
                print("Download fragment request served")
        else:
            ok, response = _readCommandOutput(command)
        
        violet2Packets = violet2ProtocolBuilder(response)

        if len(violet2Packets) > 1:
            print(f"Fragmenting response into {len(violet2Packets)} packets...")

        for i, info in enumerate(violet2Packets):
            ax25Send(info)
            if len(violet2Packets) > 1 and i < len(violet2Packets) - 1:
                sleep(INTER_PACKET_DELAY)

except KeyboardInterrupt:
    print("\nShutting down VIOLET2 responder...")
finally:
    receiveSocket.close()
    print("Cleaned up connections.")
