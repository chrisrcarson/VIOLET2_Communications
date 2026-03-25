"""
Verification 5 – Payload Packet Size Test
Associated Requirement: R-G0G-003
Test Type: Conformance and Functional

Verify that:
  - The AX.25 payload is padded to a minimum of 100 bytes when application
    data is smaller.
  - Single-frame payloads do not exceed 256 bytes.
  - Data requiring more than 248 bytes of application data is automatically
    fragmented across multiple frames and correctly reassembled.

Prerequisites (handled by hardware/conftest.py session fixture):
    SP1 – Physical hardware setup complete.
    SP2 – Earth Station running (LimeSDR.py + EARTH.py), ping succeeded.
    SP3 – OBC running (Lime_Mini_v5_headless.py + VIOLET2.py).

    test_data/test.txt         – short file (< 248 bytes) must exist on OBC.
    test_data/max_single.txt   – exactly 248 bytes; generate via SSH:
        python3 -c "print('B' * 248, end='')" > test_data/max_single.txt
    test_data/larger_file.txt  – > 248 bytes app data; generate via SSH:
        python3 -c "print('A' * 400)" > test_data/larger_file.txt

Run with:
    pytest tests/hardware/verification5_payload_packet_size_test.py -v -s
"""

import pytest


def _ask(prompt: str) -> bool:
    response = input(f"\n{prompt} (y/n): ").strip().lower()
    return response == "y"


class TestVerification5SubtestA_PaddingVerification:
    """
    Sub-test A – Padding verification for short payloads (app data < 92 bytes).

    Downloads test_data/test.txt and inspects the LimeSDR.py PDU debug output
    to verify the padding pattern and total PDU length.
    """

    def test_subtestA_pdu_length_is_116_bytes(self):
        """
        Step 2 – Send the short file download command.

        In the EARTH.py terminal type:
            download test_data/test.txt

        In the LimeSDR.py VERBOSE PDU DEBUG PRINT output, confirm:
            pdu_length = 116  (= 16 bytes AX.25 header + 100 bytes minimum payload)
        """
        print("\n[Sub-test A – Step 2]  In the EARTH.py terminal type:")
        print("  download test_data/test.txt")
        print("\nIn the LimeSDR.py debug terminal look for:")
        print("  pdu_length = 116")

        assert _ask(
            "Does LimeSDR.py show pdu_length = 116 for the short file download?"
        ), "PDU length is not 116 bytes – padding to minimum may not be working."

    def test_subtestA_padding_pattern_is_aa55(self):
        """
        Step 3b – Confirm payload bytes beyond actual data use the 0xAA 0x55 pattern.

        In the LimeSDR.py hex dump, bytes after the VIOLET2 payload data should
        alternate:  AA 55 AA 55 AA 55 ...

        Example (from the test plan, uplink at 1200 baud):
            0020: ... aa 55 aa 55 aa 55 aa 55
            0030: aa 55 aa 55 aa 55 aa 55 aa 55 aa 55 aa 55 aa 55
        """
        print("\n[Sub-test A – Step 3b]  In the LimeSDR.py hex dump confirm that bytes")
        print("after the actual payload data alternate AA 55 AA 55 ...")
        print("Example pattern:")
        print("  0020: ... aa 55 aa 55 aa 55 aa 55")
        print("  0030: aa 55 aa 55 aa 55 aa 55 ...")

        assert _ask(
            "Do the padding bytes show the alternating 0xAA 0x55 pattern?"
        ), "Padding pattern is not the expected 0xAA 0x55 alternating sequence."

    def test_subtestA_violet2_payload_len_reflects_actual_data_only(self):
        """
        Step 3c – Confirm the VIOLET2 header PAYLOAD_LEN reflects actual data only.

        In the VIOLET2.py terminal on the OBC the header parse should show
        a payload_len that matches the actual content length of test.txt,
        NOT the padded length (100 bytes):
            [VIOLET2 Header]: ... payload_len=X  (where X < 92)
        """
        print("\n[Sub-test A – Step 3c]  In the VIOLET2.py terminal confirm:")
        print("  [VIOLET2 Header]: ... payload_len=X")
        print("  X should equal the actual byte length of test.txt,")
        print("  NOT the padded total (which would be 92 or the full 100-byte payload).")

        assert _ask(
            "Does the VIOLET2 header payload_len reflect only the actual data length (not the padded size)?"
        ), "VIOLET2 header payload_len reports padded size instead of actual data length."


class TestVerification5SubtestB_MaximumSingleFrameBoundary:
    """
    Sub-test B – Maximum single-frame boundary (248 bytes of application data).

    Requires test_data/max_single.txt (exactly 248 bytes) on the OBC.
    Generate via SSH if missing:
        python3 -c "print('B' * 248, end='')" > test_data/max_single.txt
    """

    def test_subtestB_max_single_file_exists_on_obc(self):
        """
        Pre-check – Confirm test_data/max_single.txt exists on the OBC.

        In an SSH session run:
            ls -lh test_data/max_single.txt

        The file must be exactly 248 bytes.  If missing, generate it:
            python3 -c "print('B' * 248, end='')" > test_data/max_single.txt
        """
        print("\n[Sub-test B – pre-check]  On the OBC SSH session confirm:")
        print("  ls -lh test_data/max_single.txt  (must be exactly 248 bytes)")
        print("If missing, generate it:")
        print("  python3 -c \"print('B' * 248, end='')\" > test_data/max_single.txt")

        assert _ask(
            "Does test_data/max_single.txt exist on the OBC with exactly 248 bytes?"
        ), "max_single.txt not present or incorrect size – generate it before continuing."

    def test_subtestB_pdu_length_is_272_bytes(self):
        """
        Step 5-6 – Download max_single.txt and confirm PDU length.

        In the EARTH.py terminal type:
            download test_data/max_single.txt

        In LimeSDR.py confirm:
            pdu_length = 272  (= 16 bytes AX.25 header + 256 bytes maximum payload)
        """
        print("\n[Sub-test B – Step 5]  In the EARTH.py terminal type:")
        print("  download test_data/max_single.txt")
        print("\nIn LimeSDR.py confirm:")
        print("  pdu_length = 272  (= 16 AX.25 header + 256 max payload)")

        assert _ask(
            "Does LimeSDR.py show pdu_length = 272 for the 248-byte file?"
        ), "PDU length is not 272 bytes for the maximum single-frame file."

    def test_subtestB_no_fragmentation_pkt_1_of_1(self):
        """
        Step 6 – Confirm no fragmentation occurs (pkt 1/1).

        In the VIOLET2.py terminal on the OBC the header should show:
            [VIOLET2 Header]: ... pkt 1/1  payload_len=248  checksum=OK
        There should be NO 'Fragmenting response' message.
        """
        print("\n[Sub-test B – Step 6]  In the VIOLET2.py terminal confirm:")
        print("  [VIOLET2 Header]: ... pkt 1/1  payload_len=248  checksum=OK")
        print("  There should be NO 'Fragmenting response into 2 packets' message.")

        assert _ask(
            "Does the VIOLET2 header show pkt 1/1 with no fragmentation for the 248-byte file?"
        ), "VIOLET2 header indicates fragmentation for a 248-byte payload – single-frame boundary broken."


class TestVerification5SubtestC_Fragmentation:
    """
    Sub-test C – Fragmentation for application data > 248 bytes.

    Requires test_data/larger_file.txt (> 248 bytes app data) on the OBC.
    Generate via SSH if missing:
        python3 -c "print('A' * 400)" > test_data/larger_file.txt
    """

    def test_subtestC_larger_file_exists_on_obc(self):
        """
        Pre-check – Confirm test_data/larger_file.txt exists on the OBC.

        In an SSH session run:
            ls -lh test_data/larger_file.txt

        The file must be > 248 bytes.  If missing, generate it:
            python3 -c "print('A' * 400)" > test_data/larger_file.txt
        """
        print("\n[Sub-test C – pre-check]  On the OBC SSH session confirm:")
        print("  ls -lh test_data/larger_file.txt  (must be > 248 bytes)")
        print("If missing, generate it:")
        print("  python3 -c \"print('A' * 400)\" > test_data/larger_file.txt")

        assert _ask(
            "Does test_data/larger_file.txt exist on the OBC with more than 248 bytes?"
        ), "larger_file.txt not present or too small – generate it before continuing."

    def test_subtestC_obc_logs_fragmentation_message(self):
        """
        Step 8-9 – Download the larger file and observe OBC fragmentation log.

        In the EARTH.py terminal type:
            download test_data/larger_file.txt

        In the VIOLET2.py terminal on the OBC confirm:
            Fragmenting response into 2 packets...
            VIOLET2 TRANSMISSION: ...  (fragment 1, type=0x06, pkt 1/2)
            VIOLET2 TRANSMISSION: ...  (fragment 2, type=0x08, pkt 2/2)
        """
        print("\n[Sub-test C – Step 8-9]  In the EARTH.py terminal type:")
        print("  download test_data/larger_file.txt")
        print("\nIn the VIOLET2.py terminal on the OBC confirm:")
        print("  Fragmenting response into 2 packets...")
        print("  VIOLET2 TRANSMISSION: ...  (fragment 1, type=0x06, pkt 1/2)")
        print("  VIOLET2 TRANSMISSION: ...  (fragment 2, type=0x08, pkt 2/2)")

        assert _ask(
            "Does the VIOLET2.py terminal show 'Fragmenting into 2 packets' with type=0x06 and type=0x08?"
        ), "OBC did not log fragmentation into 2 packets with the expected type bytes."

    def test_subtestC_earth_receives_both_fragments(self):
        """
        Step 10 – Confirm EARTH.py receives and assembles both fragments.

        In the EARTH.py terminal confirm:
            Transfer announced: 2 packets incoming (seq=N)
            [1/2] type=0x06  pkt 1/2  payload_len=248
            [2/2] type=0x08  pkt 2/2  payload_len=153
            Downloaded test_data/larger_file.txt -> .../tmp_downloads/larger_file.txt
        """
        print("\n[Sub-test C – Step 10]  In the EARTH.py terminal confirm receipt:")
        print("  Transfer announced: 2 packets incoming (seq=N)")
        print("  [1/2] type=0x06  pkt 1/2  payload_len=248")
        print("  [2/2] type=0x08  pkt 2/2  payload_len=153")
        print("  Downloaded test_data/larger_file.txt -> .../tmp_downloads/larger_file.txt")

        assert _ask(
            "Did EARTH.py receive both fragments (type 0x06 and 0x08) and print a 'Downloaded' confirmation?"
        ), "EARTH.py did not receive or reassemble both fragments successfully."

    def test_subtestC_each_pdu_at_most_272_bytes(self):
        """
        Confirm each fragment PDU is at most 272 bytes total.

        In the LimeSDR.py debug terminal, check the pdu_length for each of
        the two fragment PDU blocks:
            Fragment 1: pdu_length <= 272
            Fragment 2: pdu_length <= 272  (typically smaller for the last chunk)
        """
        print("\n[Sub-test C – PDU size check]  In LimeSDR.py for each fragment PDU block confirm:")
        print("  Fragment 1: pdu_length <= 272")
        print("  Fragment 2: pdu_length <= 272  (last chunk is typically smaller)")

        assert _ask(
            "Are both fragment PDUs at most 272 bytes total (16 AX.25 header + 256 max payload)?"
        ), "A fragment PDU exceeds the 272-byte maximum total size."

    def test_subtestC_reassembled_content_matches_original(self):
        """
        Step 11 – Verify the downloaded file content matches the original.

        On the Earth PC run:
            cat tmp_downloads/larger_file.txt

        On the OBC (via SSH) run:
            cat test_data/larger_file.txt

        Both should contain 400 'A' characters followed by a newline.
        """
        print("\n[Sub-test C – Step 11]  Verify file content matches:")
        print("  Earth PC:  cat tmp_downloads/larger_file.txt")
        print("  OBC (SSH): cat test_data/larger_file.txt")
        print("  Both should show 400 'A' characters (+ newline).")

        assert _ask(
            "Does the reassembled downloaded file content match the original on the OBC?"
        ), "Reassembled file content does not match the original – fragmentation or reassembly error."
