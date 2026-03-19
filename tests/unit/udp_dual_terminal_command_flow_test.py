import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path


LOG_FILE_NAME = "udp_dual_terminal_command_flow_test.log"


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
    SATELLITE_CALLSIGN,
    SATELLITE_SSID,
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


def execute_local_command(command: str) -> str:
    log_line(f"execute_local_command command={command}")
    if command == "ls":
        output = "\n".join(sorted(os.listdir(".")))
        log_line("command ls completed")
        return output
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
    expected_transactions = int(os.environ["TEST_EXPECTED_TRANSACTIONS"])

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", recv_port))
    sock.settimeout(0.5)

    reassembly = {}
    completed = 0
    idle_ticks = 0

    try:
        log_line(
            f"worker_start recv_port={recv_port} earth_recv_port={earth_recv_port} expected_transactions={expected_transactions}"
        )
        while completed < expected_transactions and idle_ticks < 40:
            try:
                data, _ = sock.recvfrom(4096)
                idle_ticks = 0
            except socket.timeout:
                idle_ticks += 1
                continue

            if not isAx25UplinkPacket(data):
                continue

            parsed = parseViolet2Packet(data[AX25_HEADER_LEN:])
            if "error" in parsed:
                continue

            msg_type = parsed["msg_type"]
            seq = parsed["seq_num"]

            if msg_type == MSG_PING:
                log_line(f"received ping seq={seq}")
                payload = parsed["payload"]
                header = _buildViolet2Header(
                    messageType=MSG_PONG,
                    sequenceNumber=seq,
                    totalPackets=1,
                    packetIndex=0,
                    payloadLength=len(payload),
                )
                frame = build_ax25_downlink(header + _padApplicationData(payload))
                sock.sendto(frame, ("127.0.0.1", earth_recv_port))
                completed += 1
                log_line(f"sent pong seq={seq} completed={completed}")
                continue

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
            response_packets = violet2ProtocolBuilder(response_text.encode("ascii"))
            log_line(
                f"sending_response seq={seq} fragments={len(response_packets)} response_bytes={len(response_text)}"
            )
            for packet in response_packets:
                frame = build_ax25_downlink(packet)
                sock.sendto(frame, ("127.0.0.1", earth_recv_port))
                time.sleep(0.01)
            completed += 1

        rc = 0 if completed == expected_transactions else 2
        log_line(f"worker_end completed={completed} rc={rc}")
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
    MSG_PING,
    MSG_PONG,
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


def receive_response(sock: socket.socket, expected_kind: str, expected_sequence: int) -> dict:
    start = time.time()
    fragments = {}
    total = None

    while time.time() - start < 8:
        data, _ = sock.recvfrom(4096)
        if not isAx25DownlinkPacket(data):
            continue

        parsed = parseViolet2Packet(data[AX25_HEADER_LEN:])
        if "error" in parsed:
            continue

        msg_type = parsed["msg_type"]

        if expected_kind == "ping":
            if msg_type != MSG_PONG:
                continue
            if parsed["seq_num"] != expected_sequence:
                continue
            return {
                "message": parsed["payload"].decode("ascii", errors="replace"),
                "fragmented_downlink": False,
            }

        if msg_type == RESP_SINGLE:
            return {
                "message": parsed["payload"].decode("ascii", errors="replace"),
                "fragmented_downlink": False,
            }

        if msg_type in (RESP_MULTI_START, RESP_MULTI_CONT, RESP_MULTI_END):
            if total is None:
                total = parsed["total_pkt"]
            fragments[parsed["pkt_idx"]] = parsed["payload"]

            if msg_type != RESP_MULTI_END:
                continue

            if len(fragments) < total:
                continue

            payload = b"".join(fragments[i] for i in range(total))
            return {
                "message": payload.decode("ascii", errors="replace"),
                "fragmented_downlink": True,
            }

    raise TimeoutError("Timed out waiting for downlink response")


def main() -> int:
    earth_recv_port = int(os.environ["TEST_EARTH_RECV_PORT"])
    violet_recv_port = int(os.environ["TEST_VIOLET_RECV_PORT"])
    result_path = os.environ["TEST_RESULT_PATH"]

    scenarios = [
        {
            "name": "ping",
            "kind": "ping",
            "command": "ping-token-123",
            "expected": "ping-token-123",
            "sequence": 11,
        },
        {
            "name": "ls",
            "kind": "command",
            "command": "ls",
            "expected": None,
            "sequence": 12,
        },
        {
            "name": "download",
            "kind": "command",
            "command": "download test_data/test.txt",
            "expected": None,
            "sequence": 13,
        },
    ]

    # Resolve expected content from repository root so assertions validate real file transfer payload.
    scenarios[1]["expected"] = "test_data"
    scenarios[2]["expected"] = (Path("test_data") / "test.txt").read_text(encoding="utf-8", errors="replace")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", earth_recv_port))
    sock.settimeout(0.5)

    results = []

    try:
        log_line(
            f"worker_start earth_recv_port={earth_recv_port} violet_recv_port={violet_recv_port} scenario_count={len(scenarios)}"
        )
        for scenario in scenarios:
            payload = scenario["command"].encode("ascii")
            log_line(
                f"send_scenario name={scenario['name']} seq={scenario['sequence']} command={scenario['command']}"
            )

            if scenario["kind"] == "ping":
                header = _buildViolet2Header(
                    messageType=MSG_PING,
                    sequenceNumber=scenario["sequence"],
                    totalPackets=1,
                    packetIndex=0,
                    payloadLength=len(payload),
                )
                packets = [header + _padApplicationData(payload)]
            else:
                packets = fragment_command_payload(payload, scenario["sequence"])

            for packet in packets:
                frame = build_ax25_uplink(packet)
                sock.sendto(frame, ("127.0.0.1", violet_recv_port))
                time.sleep(0.01)

            response = receive_response(sock, scenario["kind"], scenario["sequence"])
            log_line(
                f"received_response name={scenario['name']} fragmented_downlink={response['fragmented_downlink']} bytes={len(response['message'])}"
            )
            results.append(
                {
                    "name": scenario["name"],
                    "expected": scenario["expected"],
                    "actual": response["message"],
                    "fragmented_uplink": len(packets) > 1,
                    "fragmented_downlink": response["fragmented_downlink"],
                }
            )

        with open(result_path, "w", encoding="utf-8") as handle:
            json.dump(results, handle)
        log_line(f"results_written path={result_path}")

        return 0
    finally:
        sock.close()


if __name__ == "__main__":
    raise SystemExit(main())
'''


def test_dual_background_terminals_udp_uplink_downlink_commands():
    violet_recv_port = _free_udp_port()
    earth_recv_port = _free_udp_port()
    log_path = Path(__file__).with_name(LOG_FILE_NAME)

    log_path.write_text("", encoding="utf-8")
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("[TEST] start dual-terminal udp command flow\n")
        handle.write(f"[TEST] earth_recv_port={earth_recv_port} violet_recv_port={violet_recv_port}\n")

    with tempfile.TemporaryDirectory() as temp_dir:
        result_path = Path(temp_dir) / "results.json"

        env = os.environ.copy()
        env.update(
            {
                "TEST_VIOLET_RECV_PORT": str(violet_recv_port),
                "TEST_EARTH_RECV_PORT": str(earth_recv_port),
                "TEST_RESULT_PATH": str(result_path),
                "TEST_EXPECTED_TRANSACTIONS": "3",
                "TEST_OUTPUT_LOG_PATH": str(log_path),
            }
        )

        violet_proc = subprocess.Popen(
            [sys.executable, "-u", "-c", VIOLET_WORKER],
            cwd=str(Path(__file__).resolve().parents[2]),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        earth_proc = subprocess.Popen(
            [sys.executable, "-u", "-c", EARTH_WORKER],
            cwd=str(Path(__file__).resolve().parents[2]),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            earth_stdout, earth_stderr = earth_proc.communicate(timeout=20)
            try:
                violet_stdout, violet_stderr = violet_proc.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                violet_proc.terminate()
                violet_stdout, violet_stderr = violet_proc.communicate(timeout=5)
        finally:
            if earth_proc.poll() is None:
                earth_proc.terminate()
            if violet_proc.poll() is None:
                violet_proc.terminate()

        assert earth_proc.returncode == 0, (
            "Earth worker failed\n"
            f"stdout:\n{earth_stdout}\n"
            f"stderr:\n{earth_stderr}"
        )
        if violet_proc.returncode is not None:
            assert violet_proc.returncode == 0, (
                "VIOLET worker failed\n"
                f"stdout:\n{violet_stdout}\n"
                f"stderr:\n{violet_stderr}"
            )

        assert result_path.exists(), "Earth worker did not produce a result file"
        with result_path.open("r", encoding="utf-8") as handle:
            results = json.load(handle)

        with log_path.open("a", encoding="utf-8") as handle:
            handle.write("[TEST] earth stdout begin\n")
            handle.write(earth_stdout)
            handle.write("\n[TEST] earth stderr begin\n")
            handle.write(earth_stderr)
            handle.write("\n[TEST] violet stdout begin\n")
            handle.write(violet_stdout)
            handle.write("\n[TEST] violet stderr begin\n")
            handle.write(violet_stderr)
            handle.write("\n[TEST] parsed results\n")
            handle.write(json.dumps(results, indent=2))
            handle.write("\n")

        assert len(results) == 3, f"Expected 3 transactions, got {len(results)}"

        by_name = {item["name"]: item for item in results}

        assert by_name["ping"]["actual"] == by_name["ping"]["expected"]
        assert by_name["ls"]["expected"] in by_name["ls"]["actual"]
        assert by_name["download"]["actual"] == by_name["download"]["expected"]

        assert by_name["ls"]["fragmented_uplink"] is False
        assert isinstance(by_name["ls"]["fragmented_downlink"], bool)
        assert by_name["download"]["fragmented_uplink"] is False

    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("[TEST] completed successfully\n")
