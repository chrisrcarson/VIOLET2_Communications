"""
Dual UDP terminal test simulating packet loss during file downloads.

A VIOLET2 responder worker sends a multi-fragment file download with intentional
packet drops, and an EARTH ground station detects incomplete reception and requests
retransmission via NACK. The test validates that the full file is reconstructed
despite packet loss.
"""

import json
import os
import socket
import random
import subprocess
import sys
import tempfile
import time
from pathlib import Path


LOG_FILE_NAME = "udp_dual_terminal_download_packet_loss_test.log"
LOG_DIR_NAME = "logs"


def _free_udp_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


VIOLET_WORKER = r'''
import os
import socket
import time
import random
from pathlib import Path

from earth_utils import (
    AX25_CONTROL,
    AX25_HEADER_LEN,
    AX25_PID,
    EARTH_CALLSIGN,
    EARTH_SSID,
    MSG_CMD_MULTI_CONT,
    MSG_CMD_MULTI_END,
    MSG_CMD_MULTI_START,
    MSG_CMD_SINGLE,
    MSG_PING,
    MSG_PONG,
    MSG_NACK,
    RESP_SINGLE,
    RESP_MULTI_START,
    RESP_MULTI_CONT,
    RESP_MULTI_END,
    SATELLITE_CALLSIGN,
    SATELLITE_SSID,
    VIOLET2_MAX_APP_DATA,
    _buildViolet2Header,
    _padApplicationData,
)
from violet2_utils import isAx25UplinkPacket, parseViolet2Packet, violet2ProtocolBuilder


LOG_PATH = os.environ.get("TEST_OUTPUT_LOG_PATH")


def log_line(message: str):
    if not LOG_PATH:
        return
    with open(LOG_PATH, "a", encoding="utf-8") as handle:
        handle.write(f"[VIOLET] {message}\n")


def build_ax25_downlink(payload: bytes) -> bytes:
    return (
        EARTH_CALLSIGN.encode("ascii")
        + bytes.fromhex(EARTH_SSID)
        + SATELLITE_CALLSIGN.encode("ascii")
        + bytes.fromhex(SATELLITE_SSID)
        + bytes.fromhex(AX25_CONTROL)
        + bytes.fromhex(AX25_PID)
        + payload
    )


def build_response_packets(response_text: bytes, sequence_number: int) -> list[bytes]:
    """
    Build response packets with the given sequence number, handling fragmentation.
    """
    VIOLET2_MAX_APP_DATA = 248
    
    if len(response_text) <= VIOLET2_MAX_APP_DATA:
        header = _buildViolet2Header(
            messageType=RESP_SINGLE,
            sequenceNumber=sequence_number,
            totalPackets=1,
            packetIndex=0,
            payloadLength=len(response_text),
        )
        return [header + _padApplicationData(response_text)]
    
    # Fragment the response
    fragments = [response_text[i:i + VIOLET2_MAX_APP_DATA] 
                for i in range(0, len(response_text), VIOLET2_MAX_APP_DATA)]
    total = len(fragments)
    packets = []
    
    for idx, chunk in enumerate(fragments):
        if idx == 0:
            msg_type = RESP_MULTI_START
        elif idx == total - 1:
            msg_type = RESP_MULTI_END
        else:
            msg_type = RESP_MULTI_CONT
        
        header = _buildViolet2Header(
            messageType=msg_type,
            sequenceNumber=sequence_number,
            totalPackets=total,
            packetIndex=idx,
            payloadLength=len(chunk),
        )
        packets.append(header + _padApplicationData(chunk))
    
    return packets


def execute_local_command(command: str) -> str:
    log_line(f"execute_local_command command={command}")
    if command.startswith("download "):
        relative_path = command[len("download "):].strip()
        target = Path(relative_path)
        if not target.exists() or not target.is_file():
            log_line(f"command download failed path={relative_path}")
            return f"DOWNLOAD_ERROR:{relative_path}"
        output = target.read_text(encoding="utf-8", errors="replace")
        log_line(f"command download completed path={relative_path} bytes={len(output)}")
        return output
    log_line(f"command unknown command={command}")
    return f"UNKNOWN:{command}"


def main() -> int:
    recv_port = int(os.environ["TEST_VIOLET_RECV_PORT"])
    earth_recv_port = int(os.environ["TEST_EARTH_RECV_PORT"])
    packet_loss_rate = float(os.environ.get("TEST_PACKET_LOSS_RATE", "0.3"))  # 30% loss by default
    random_seed = int(os.environ.get("TEST_RANDOM_SEED", "42"))
    
    random.seed(random_seed)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", recv_port))
    sock.settimeout(0.5)

    reassembly = {}
    downlink_cache = {}  # Cache responses for potential retransmission on NACK
    completed_downloads = 0
    idle_ticks = 0
    nack_retries = 0
    max_nack_retries = 20

    try:
        log_line(
            f"worker_start recv_port={recv_port} earth_recv_port={earth_recv_port} packet_loss_rate={packet_loss_rate:.0%}"
        )
        while idle_ticks < 60:
            try:
                data, _ = sock.recvfrom(4096)
                idle_ticks = 0
            except socket.timeout:
                idle_ticks += 1
                # Exit if download complete and no new NACKs arriving
                if completed_downloads >= 1 and nack_retries >= max_nack_retries:
                    break
                continue

            if not isAx25UplinkPacket(data):
                continue

            parsed = parseViolet2Packet(data[AX25_HEADER_LEN:])
            if "error" in parsed:
                continue

            msg_type = parsed["msg_type"]
            seq = parsed["seq_num"]

            # Handle NACK: resend requested fragments with potential packet loss
            if msg_type == MSG_NACK:
                if nack_retries >= max_nack_retries:
                    log_line(f"max NACK retries reached, exiting")
                    break
                
                payload = parsed["payload"]
                if len(payload) < 1:
                    continue
                nack_seq = payload[0]
                missing_indices = list(payload[1:]) if len(payload) > 1 else []
                
                log_line(f"received NACK seq={nack_seq} missing_indices={missing_indices}")
                
                if nack_seq not in downlink_cache:
                    log_line(f"no cached response for seq={nack_seq}, ignoring NACK")
                    continue
                
                cached_packets = downlink_cache[nack_seq]
                indices_to_send = missing_indices if missing_indices else list(range(len(cached_packets)))
                
                resent = 0
                for idx in sorted(set(indices_to_send)):
                    if 0 <= idx < len(cached_packets):
                        # Apply packet loss on retransmitted packets too
                        if random.random() < packet_loss_rate:
                            log_line(f"SIMULATED LOSS: retransmitted fragment idx={idx} seq={nack_seq}")
                            continue
                        
                        frame = build_ax25_downlink(cached_packets[idx])
                        sock.sendto(frame, ("127.0.0.1", earth_recv_port))
                        resent += 1
                        time.sleep(0.01)
                
                log_line(f"retransmitted {resent} fragments for seq={nack_seq}")
                nack_retries += 1
                continue

            # Handle download command
            if msg_type == MSG_CMD_SINGLE:
                command = parsed["payload"].decode("ascii", errors="replace")
            elif msg_type == MSG_CMD_MULTI_START:
                reassembly[seq] = {
                    "total": parsed["total_pkt"],
                    "chunks": {parsed["pkt_idx"]: parsed["payload"]},
                }
                continue
            elif msg_type in (MSG_CMD_MULTI_CONT, MSG_CMD_MULTI_END):
                if seq not in reassembly:
                    continue
                reassembly[seq]["chunks"][parsed["pkt_idx"]] = parsed["payload"]
                if msg_type != MSG_CMD_MULTI_END:
                    continue

                total = reassembly[seq]["total"]
                chunks = reassembly[seq]["chunks"]
                if len(chunks) < total:
                    continue
                command = b"".join(chunks[i] for i in range(total)).decode("ascii", errors="replace")
                del reassembly[seq]
            else:
                continue

            response_text = execute_local_command(command)
            
            # Build response packets with the incoming command's sequence number
            response_payload = response_text.encode("ascii")
            response_packets = build_response_packets(response_payload, seq)
            
            # Cache the response for NACK-based retransmission
            downlink_cache[seq] = response_packets
            
            log_line(
                f"sending_response seq={seq} fragments={len(response_packets)} response_bytes={len(response_text)}"
            )
            
            # Send response packets with simulated packet loss
            sent = 0
            for pkt_idx, packet in enumerate(response_packets):
                # Simulate packet loss for initial send
                if random.random() < packet_loss_rate:
                    log_line(f"SIMULATED LOSS: dropping response fragment pkt_idx={pkt_idx} seq={seq}")
                    continue
                
                frame = build_ax25_downlink(packet)
                sock.sendto(frame, ("127.0.0.1", earth_recv_port))
                sent += 1
                time.sleep(0.01)
            
            log_line(f"sent {sent}/{len(response_packets)} fragments, packet_loss_applied")
            completed_downloads += 1

        rc = 0 if completed_downloads >= 1 else 2
        log_line(f"worker_end completed_downloads={completed_downloads} nack_retries={nack_retries} rc={rc}")
        return rc
    finally:
        sock.close()


if __name__ == "__main__":
    raise SystemExit(main())
'''


EARTH_WORKER = r'''
import json
import os
import socket
import time
from pathlib import Path

from earth_utils import (
    AX25_CONTROL,
    AX25_HEADER_LEN,
    AX25_PID,
    EARTH_CALLSIGN,
    EARTH_SSID,
    MSG_CMD_MULTI_CONT,
    MSG_CMD_MULTI_END,
    MSG_CMD_MULTI_START,
    MSG_CMD_SINGLE,
    MSG_NACK,
    RESP_MULTI_CONT,
    RESP_MULTI_END,
    RESP_MULTI_START,
    RESP_SINGLE,
    SATELLITE_CALLSIGN,
    SATELLITE_SSID,
    VIOLET2_MAX_APP_DATA,
    _buildViolet2Header,
    _padApplicationData,
    isAx25DownlinkPacket,
)
from violet2_utils import parseViolet2Packet


LOG_PATH = os.environ.get("TEST_OUTPUT_LOG_PATH")


def log_line(message: str):
    if not LOG_PATH:
        return
    with open(LOG_PATH, "a", encoding="utf-8") as handle:
        handle.write(f"[EARTH] {message}\n")


def build_ax25_uplink(payload: bytes) -> bytes:
    return (
        SATELLITE_CALLSIGN.encode("ascii")
        + bytes.fromhex(SATELLITE_SSID)
        + EARTH_CALLSIGN.encode("ascii")
        + bytes.fromhex(EARTH_SSID)
        + bytes.fromhex(AX25_CONTROL)
        + bytes.fromhex(AX25_PID)
        + payload
    )


def fragment_command_payload(payload: bytes, sequence_number: int) -> list[bytes]:
    if len(payload) <= VIOLET2_MAX_APP_DATA:
        header = _buildViolet2Header(
            messageType=MSG_CMD_SINGLE,
            sequenceNumber=sequence_number,
            totalPackets=1,
            packetIndex=0,
            payloadLength=len(payload),
        )
        return [header + _padApplicationData(payload)]

    chunks = [payload[i:i + VIOLET2_MAX_APP_DATA] for i in range(0, len(payload), VIOLET2_MAX_APP_DATA)]
    total = len(chunks)
    packets = []
    for idx, chunk in enumerate(chunks):
        if idx == 0:
            msg_type = MSG_CMD_MULTI_START
        elif idx == total - 1:
            msg_type = MSG_CMD_MULTI_END
        else:
            msg_type = MSG_CMD_MULTI_CONT
        header = _buildViolet2Header(
            messageType=msg_type,
            sequenceNumber=sequence_number,
            totalPackets=total,
            packetIndex=idx,
            payloadLength=len(chunk),
        )
        packets.append(header + _padApplicationData(chunk))
    return packets


def receive_download_with_recovery(sock: socket.socket, expected_sequence: int, max_retries: int = 5) -> str:
    """
    Receive a multi-fragment download response, handling packet loss via NACK/retransmission.
    """
    start = time.time()
    fragments = {}
    total = None
    retry_count = 0
    violet_port = int(os.environ["TEST_VIOLET_RECV_PORT"])
    last_fragment_time = time.time()
    fragment_timeout = 3.0  # If no new frags in 3 seconds, assume incomplete and NACK

    log_line(f"receive_download_with_recovery seq={expected_sequence} max_retries={max_retries}")

    while time.time() - start < 30:
        try:
            data, _ = sock.recvfrom(4096)
            last_fragment_time = time.time()
        except socket.timeout:
            # Check if we've been waiting too long for new fragments
            if total is not None and len(fragments) < total and (time.time() - last_fragment_time) > fragment_timeout:
                # Incomplete reception: send NACK for missing indices
                if retry_count < max_retries:
                    missing = [i for i in range(total) if i not in fragments]
                    log_line(f"receive_download_with_recovery incomplete (timeout): missing={missing} retry={retry_count + 1}/{max_retries}")
                    
                    # Build NACK packet
                    nack_payload = bytes([expected_sequence] + missing)
                    nack_header = _buildViolet2Header(
                        messageType=MSG_NACK,
                        sequenceNumber=expected_sequence,
                        totalPackets=1,
                        packetIndex=0,
                        payloadLength=len(nack_payload),
                    )
                    nack_frame = build_ax25_uplink(nack_header + _padApplicationData(nack_payload))
                    sock.sendto(nack_frame, ("127.0.0.1", violet_port))
                    log_line(f"receive_download_with_recovery sent NACK for missing fragments")
                    
                    retry_count += 1
                    last_fragment_time = time.time()
                    continue
            continue

        if not isAx25DownlinkPacket(data):
            continue

        parsed = parseViolet2Packet(data[AX25_HEADER_LEN:])
        if "error" in parsed:
            continue

        msg_type = parsed["msg_type"]

        # Only process responses for our sequence
        if parsed["seq_num"] != expected_sequence:
            continue

        # Single-packet response (no fragmentation)
        if msg_type == RESP_SINGLE:
            log_line(f"receive_download_with_recovery received RESP_SINGLE")
            return parsed["payload"].decode("ascii", errors="replace")

        # Multi-packet response
        if msg_type in (RESP_MULTI_START, RESP_MULTI_CONT, RESP_MULTI_END):
            if total is None:
                total = parsed["total_pkt"]
                log_line(f"receive_download_with_recovery total_packets={total}")
            
            fragments[parsed["pkt_idx"]] = parsed["payload"]
            log_line(f"receive_download_with_recovery received fragment pkt_idx={parsed['pkt_idx']} total_received={len(fragments)}/{total}")

            if msg_type != RESP_MULTI_END:
                continue

            # End-of-message reached
            if len(fragments) == total:
                # All fragments received successfully
                payload = b"".join(fragments[i] for i in range(total))
                log_line(f"receive_download_with_recovery all fragments received successfully")
                return payload.decode("ascii", errors="replace")
            
            # Incomplete reception: send NACK for missing indices
            if retry_count < max_retries:
                missing = [i for i in range(total) if i not in fragments]
                log_line(f"receive_download_with_recovery incomplete (END received): missing={missing} retry={retry_count + 1}/{max_retries}")
                
                # Build NACK packet
                nack_payload = bytes([expected_sequence] + missing)
                nack_header = _buildViolet2Header(
                    messageType=MSG_NACK,
                    sequenceNumber=expected_sequence,
                    totalPackets=1,
                    packetIndex=0,
                    payloadLength=len(nack_payload),
                )
                nack_frame = build_ax25_uplink(nack_header + _padApplicationData(nack_payload))
                sock.sendto(nack_frame, ("127.0.0.1", violet_port))
                log_line(f"receive_download_with_recovery sent NACK for missing fragments")
                
                retry_count += 1
                last_fragment_time = time.time()
                continue

    raise TimeoutError(f"Download incomplete after {max_retries} retries: {len(fragments)}/{total} fragments received")


def main() -> int:
    earth_recv_port = int(os.environ["TEST_EARTH_RECV_PORT"])
    violet_recv_port = int(os.environ["TEST_VIOLET_RECV_PORT"])
    result_path = os.environ["TEST_RESULT_PATH"]

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", earth_recv_port))
    sock.settimeout(0.5)

    test_file = Path("test_data") / "larger_file.txt"
    expected_content = test_file.read_text(encoding="utf-8", errors="replace")

    try:
        log_line(f"worker_start earth_recv_port={earth_recv_port} violet_recv_port={violet_recv_port}")
        time.sleep(0.2)

        # Send download command
        command = "download test_data/larger_file.txt"
        payload = command.encode("ascii")
        packets = fragment_command_payload(payload, 21)
        
        log_line(f"send_download_command packets={len(packets)} command={command}")
        for packet in packets:
            frame = build_ax25_uplink(packet)
            sock.sendto(frame, ("127.0.0.1", violet_recv_port))
            time.sleep(0.01)

        # Receive download with packet loss recovery
        received_content = receive_download_with_recovery(sock, 21, max_retries=10)
        
        log_line(f"download_complete received_bytes={len(received_content)} expected_bytes={len(expected_content)}")

        # Validate
        result = {
            "success": received_content == expected_content,
            "received_bytes": len(received_content),
            "expected_bytes": len(expected_content),
            "content_matches": received_content == expected_content,
        }

        with open(result_path, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2)
        log_line(f"results_written success={result['success']}")

        return 0 if result["success"] else 1
    except Exception as e:
        log_line(f"error {type(e).__name__}: {e}")
        with open(result_path, "w", encoding="utf-8") as handle:
            json.dump({"success": False, "error": str(e)}, handle)
        return 1
    finally:
        sock.close()


if __name__ == "__main__":
    raise SystemExit(main())
'''


def test_dual_background_terminals_download_with_packet_loss():
    """
    Test file download over AX.25 with simulated packet loss (30% drop rate).
    Validates that EARTH detects incomplete multi-fragment responses and sends
    NACK to request retransmission, eventually receiving the complete file.
    """
    violet_recv_port = _free_udp_port()
    earth_recv_port = _free_udp_port()
    log_dir = Path(__file__).resolve().parent / LOG_DIR_NAME
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / LOG_FILE_NAME

    log_path.write_text("", encoding="utf-8")
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("[TEST] start dual-terminal download with packet loss\n")
        handle.write(f"[TEST] earth_recv_port={earth_recv_port} violet_recv_port={violet_recv_port}\n")

    with tempfile.TemporaryDirectory() as temp_dir:
        result_path = Path(temp_dir) / "results.json"

        env = os.environ.copy()
        env.update(
            {
                "TEST_VIOLET_RECV_PORT": str(violet_recv_port),
                "TEST_EARTH_RECV_PORT": str(earth_recv_port),
                "TEST_RESULT_PATH": str(result_path),
                "TEST_OUTPUT_LOG_PATH": str(log_path),
                "TEST_PACKET_LOSS_RATE": "0.3",  # 30% packet loss
                "TEST_RANDOM_SEED": "42",
            }
        )

        # Start VIOLET2 responder worker
        violet_proc = subprocess.Popen(
            [sys.executable, "-c", VIOLET_WORKER],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=Path(__file__).resolve().parent.parent.parent,
            text=True,
        )

        # Start EARTH ground station worker
        earth_proc = subprocess.Popen(
            [sys.executable, "-c", EARTH_WORKER],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=Path(__file__).resolve().parent.parent.parent,
            text=True,
        )

        with log_path.open("a", encoding="utf-8") as handle:
            handle.write("[TEST] both workers started\n")

        # Wait for completion
        violet_rc = violet_proc.wait(timeout=45)
        earth_rc = earth_proc.wait(timeout=45)

        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"[TEST] workers finished: violet_rc={violet_rc} earth_rc={earth_rc}\n")

        # Load and validate results
        results = json.loads(result_path.read_text(encoding="utf-8"))

        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"[TEST] results={json.dumps(results)}\n")

        # Assertions
        assert violet_rc == 0, f"VIOLET2 worker exited with code {violet_rc}"
        assert earth_rc == 0, f"EARTH worker exited with code {earth_rc}"
        assert results["success"], f"Download failed or content mismatch: {results}"
        assert results["content_matches"], "Received content does not match expected"
