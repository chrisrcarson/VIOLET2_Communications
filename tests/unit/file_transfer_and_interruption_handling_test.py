# File Transfer and Interruption Handling Tests
# Associated Requirement: R-G0G-001
# Verifies that file uploads and downloads between the Earth ground station and
# VIOLET2 complete successfully over AX.25, including transfers requiring multiple
# overhead passes, and that Tx/Rx interruptions are handled properly.

import pathlib

import pytest
import socket
import threading
import time
from test_utils import (
    reassemble_payload,
    EARTH_CALLSIGN,
    SATELLITE_CALLSIGN,
    DEST_SSID_BYTES,
    SRC_SSID_BYTES,
    CONTROL_BYTE,
    PID_BYTE,
    AX25_HEADER_LEN,
)

# Constants
AX25_HEADER_SIZE = AX25_HEADER_LEN
MAX_PAYLOAD_SIZE = 255  # max bytes per frame

# Pre-built fixture files used by the integration tests below.
TESTDATA_DIR = pathlib.Path(__file__).parent.parent / "test_data"

# Placeholder functions (file transfer is tested separately)
# Upload a file from Earth PC to VIOLET2 OBC.
def uploadData(filepath: str) -> bool:
    raise NotImplementedError("uploadData() integration test - requires live VIOLET2 responder")

# Download a file from VIOLET2 OBC to Earth PC.
def downloadFile(filename: str) -> bytes:
    raise NotImplementedError("downloadFile() integration test - requires live VIOLET2 responder")

# Handle a Tx/Rx interruption and attempt retransmission.
def handleInterruption(transfer_id: str) -> bool:
    raise NotImplementedError("handleInterruption() integration test - requires simulated interruption")

# Helper: manually build a frame the same way existing code does
def _build_raw_frame(dest_callsign: str, src_callsign: str, payload: bytes) -> bytes:
    return (
        dest_callsign.encode('ascii') +
        DEST_SSID_BYTES +
        src_callsign.encode('ascii') +
        SRC_SSID_BYTES +
        CONTROL_BYTE +
        PID_BYTE +
        payload
    )

def _fragment_payload(payload: bytes, max_size: int = MAX_PAYLOAD_SIZE) -> list[bytes]: # split payload into chunks of max_size.
    return [payload[i:i+max_size] for i in range(0, len(payload), max_size)]


# Test 1: File Upload (will require file_transfer.py)
@pytest.mark.skip(reason="Requires live VIOLET2 responder")
class TestFileUpload:

    def testUploadCompletesSuccessfully(self): # a file upload from Earth PC to VIOLET2 OBC should complete successfully.
        test_file = TESTDATA_DIR / "upload_test.txt"
        assert test_file.exists(), f"Fixture file not found: {test_file}"
        result = uploadData(str(test_file))
        assert result is True, "Expected uploadData() to return True on success"

    def testUploadLargeFileRequiresMultiplePasses(self): # a file larger than 255 bytes should require multiple overhead passes.
        test_file = TESTDATA_DIR / "large_upload_test.txt"
        assert test_file.exists(), f"Fixture file not found: {test_file}"
        assert test_file.stat().st_size > MAX_PAYLOAD_SIZE, (
            f"Fixture file must exceed {MAX_PAYLOAD_SIZE} bytes to require multiple passes"
        )
        result = uploadData(str(test_file))
        assert result is True, "Expected large file upload to complete successfully"

    def testUploadFileIsFragmentedCorrectly(self, tmp_path): # a file larger than 255 bytes should be fragmented into valid frames.
        payload = b"A" * 1024
        fragments = _fragment_payload(payload)
        for i, fragment in enumerate(fragments):
            assert len(fragment) <= MAX_PAYLOAD_SIZE, (
                f"Fragment {i} exceeds maximum frame payload size: {len(fragment)} bytes"
            )


# Test 2: File Download (will require file_transfer.py)
@pytest.mark.skip(reason="Requires live VIOLET2 responder")
class TestFileDownload:

    def testDownloadCompletesSuccessfully(self): # a file download from VIOLET2 OBC to Earth PC should complete successfully.
        result = downloadFile("test_file.txt")
        assert result is not None, "Expected downloadFile() to return file contents"

    def testDownloadedFileMatchesOriginal(self): # downloaded file contents should match what was originally uploaded.
        test_file = TESTDATA_DIR / "roundtrip_test.txt"
        assert test_file.exists(), f"Fixture file not found: {test_file}"
        original = test_file.read_bytes()
        uploadData(str(test_file))
        downloaded = downloadFile("roundtrip_test.txt")
        assert downloaded == original, "Downloaded file contents do not match original"

    def testLargeDownloadReassemblesCorrectly(self): # a large file downloaded in multiple fragments should reassemble correctly.
        original = b"A" * 1024
        fragments = _fragment_payload(original)
        reassembled = reassemble_payload(fragments)
        assert reassembled == original, "Reassembled download does not match original file"


# Test 3: Interruption Handling (will require file_transfer.py)
@pytest.mark.skip(reason="Requires simulated interruption and live responder")
class TestInterruptionHandling:

    def testInterruptionTriggersErrorOrRetransmission(self): # a mid-transfer interruption should produce an error or trigger retransmission.
        result = handleInterruption("transfer_001")
        assert result is not None, (
            "Expected handleInterruption() to return a result indicating error or retry"
        )

    def testTransferCompletesAfterInterruption(self): # a transfer should complete successfully after recovering from an interruption.
        test_file = TESTDATA_DIR / "interrupted_transfer.txt"
        assert test_file.exists(), f"Fixture file not found: {test_file}"
        handleInterruption("transfer_001")
        result = uploadData(str(test_file))
        assert result is True, "Expected transfer to complete successfully after interruption"


# Test 4: Loopback Multi-Pass Transfer
class TestLoopbackMultiPassTransfer:

    def testMultiFragmentTransferOverLoopback(self): # multiple fragments should all be received correctly over UDP loopback.
        send_host = "127.0.0.1"
        send_port = 29002

        payload = b"A" * 1024
        fragments = _fragment_payload(payload)
        frames = [
            _build_raw_frame(SATELLITE_CALLSIGN, EARTH_CALLSIGN, fragment)
            for fragment in fragments
        ]

        received = []

        def listen():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((send_host, send_port))
            sock.settimeout(3)
            try:
                while True:
                    data, _ = sock.recvfrom(1024)
                    received.append(data)
            except socket.timeout:
                pass
            finally:
                sock.close()

        listener = threading.Thread(target=listen)
        listener.start()
        time.sleep(0.1)

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        for frame in frames:
            sock.sendto(frame, (send_host, send_port))
            time.sleep(0.05)
        sock.close()

        listener.join(timeout=5)

        assert len(received) == len(frames), (
            f"Expected {len(frames)} fragments, received {len(received)}"
        )

    def testReassemblyAfterLoopbackTransfer(self): # payloads extracted from received loopback frames should reassemble correctly.
        send_host = "127.0.0.1"
        send_port = 29003

        original_payload = b"B" * 1024
        fragments = _fragment_payload(original_payload)
        frames = [
            _build_raw_frame(SATELLITE_CALLSIGN, EARTH_CALLSIGN, fragment)
            for fragment in fragments
        ]

        received_payloads = []

        def listen():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((send_host, send_port))
            sock.settimeout(3)
            try:
                while True:
                    data, _ = sock.recvfrom(1024)
                    received_payloads.append(data[AX25_HEADER_SIZE:])
            except socket.timeout:
                pass
            finally:
                sock.close()

        listener = threading.Thread(target=listen)
        listener.start()
        time.sleep(0.1)

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        for frame in frames:
            sock.sendto(frame, (send_host, send_port))
            time.sleep(0.05)
        sock.close()

        listener.join(timeout=5)

        reassembled = b"".join(received_payloads)
        assert reassembled == original_payload, (
            "Reassembled payload from loopback transfer does not match original"
        )

    def testSimulatedInterruptionDropsFragment(self): # simulating a dropped fragment should result in incomplete reassembly.
        original_payload = b"C" * 1024
        fragments = _fragment_payload(original_payload)

        # simulate an interruption by dropping the second fragment
        fragments_with_interruption = fragments[:1] + fragments[2:]
        reassembled = b"".join(fragments_with_interruption)

        assert reassembled != original_payload, (
            "Expected reassembly to fail when a fragment is dropped"
        )
