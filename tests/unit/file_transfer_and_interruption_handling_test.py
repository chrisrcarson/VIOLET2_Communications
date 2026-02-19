# File Transfer and Interruption Handling Tests
# Associated Requirement: R-G0G-001

# Verifies that file uploads and downloads between the Earth ground station and
# VIOLET2 complete successfully over AX.25, including transfers requiring multiple
# overhead passes, and that Tx/Rx interruptions are handled properly.

import pytest
import socket
import threading
import time

# Constants
EARTH_CALLSIGN      = "VE9CNB"
SATELLITE_CALLSIGN  = "VE9VLT"
DEST_SSID           = bytes.fromhex("60")
SRC_SSID            = bytes.fromhex("E0")
CONTROL             = bytes.fromhex("00")
PID                 = bytes.fromhex("F0")

AX25_HEADER_SIZE    = 16
MAX_PAYLOAD_SIZE    = 255  # max bytes per frame

# Placeholder functions (remove once packet_utils.py and file_transfer.py exist)
def upload_file(filepath: str) -> bool: # upload a file from Earth PC to VIOLET2 OBC.
    raise NotImplementedError("upload_file() not yet implemented in file_transfer.py")

def download_file(filename: str) -> bytes: # download a file from VIOLET2 OBC to Earth PC.
    raise NotImplementedError("download_file() not yet implemented in file_transfer.py")

def handle_interruption(transfer_id: str) -> bool: # handle a Tx/Rx interruption and attempt retransmission.
    raise NotImplementedError("handle_interruption() not yet implemented in file_transfer.py")

def reassemble_payload(fragments: list[bytes]) -> bytes: # reassemble a list of fragments into the original payload.
    raise NotImplementedError("reassemble_payload() not yet implemented in packet_utils.py")

# Helper: manually build a frame the same way existing code does
def _build_raw_frame(dest_callsign: str, src_callsign: str, payload: bytes) -> bytes:
    return (
        dest_callsign.encode('ascii') +
        DEST_SSID +
        src_callsign.encode('ascii') +
        SRC_SSID +
        CONTROL +
        PID +
        payload
    )

def _fragment_payload(payload: bytes, max_size: int = MAX_PAYLOAD_SIZE) -> list[bytes]: # split payload into chunks of max_size.
    return [payload[i:i+max_size] for i in range(0, len(payload), max_size)]


# Test 1: File Upload (will require file_transfer.py)
class TestFileUpload:

    def testUploadCompletesSuccessfully(self, tmp_path): # a file upload from Earth PC to VIOLET2 OBC should complete successfully.
        test_file = tmp_path / "upload_test.txt"
        test_file.write_bytes(b"A" * 100)
        result = upload_file(str(test_file))
        assert result is True, "Expected upload_file() to return True on success"

    def testUploadLargeFileRequiresMultiplePasses(self, tmp_path): # a file larger than 255 bytes should require multiple overhead passes.
        test_file = tmp_path / "large_upload_test.txt"
        test_file.write_bytes(b"A" * 1024)
        result = upload_file(str(test_file))
        assert result is True, "Expected large file upload to complete successfully"

    def testUploadFileIsFragmentedCorrectly(self, tmp_path): # a file larger than 255 bytes should be fragmented into valid frames.
        payload = b"A" * 1024
        fragments = _fragment_payload(payload)
        for i, fragment in enumerate(fragments):
            assert len(fragment) <= MAX_PAYLOAD_SIZE, (
                f"Fragment {i} exceeds maximum frame payload size: {len(fragment)} bytes"
            )


# Test 2: File Download (will require file_transfer.py)
class TestFileDownload:

    def testDownloadCompletesSuccessfully(self): # a file download from VIOLET2 OBC to Earth PC should complete successfully.
        result = download_file("test_file.txt")
        assert result is not None, "Expected download_file() to return file contents"

    def testDownloadedFileMatchesOriginal(self, tmp_path): # downloaded file contents should match what was originally uploaded.
        original = b"A" * 100
        test_file = tmp_path / "roundtrip_test.txt"
        test_file.write_bytes(original)
        upload_file(str(test_file))
        downloaded = download_file("roundtrip_test.txt")
        assert downloaded == original, "Downloaded file contents do not match original"

    def testLargeDownloadReassemblesCorrectly(self): # a large file downloaded in multiple fragments should reassemble correctly.
        original = b"A" * 1024
        fragments = _fragment_payload(original)
        reassembled = reassemble_payload(fragments)
        assert reassembled == original, "Reassembled download does not match original file"


# Test 3: Interruption Handling (will require file_transfer.py)
class TestInterruptionHandling:

    def testInterruptionTriggersErrorOrRetransmission(self): # a mid-transfer interruption should produce an error or trigger retransmission.
        result = handle_interruption("transfer_001")
        assert result is not None, (
            "Expected handle_interruption() to return a result indicating error or retry"
        )

    def testTransferCompletesAfterInterruption(self, tmp_path): # a transfer should complete successfully after recovering from an interruption.
        test_file = tmp_path / "interrupted_transfer.txt"
        test_file.write_bytes(b"A" * 512)
        handle_interruption("transfer_001")
        result = upload_file(str(test_file))
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
