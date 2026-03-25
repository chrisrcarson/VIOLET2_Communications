"""
Verification 2 – File Transfer and Interruption Handling
Associated Requirement: R-G0G-001
Test Type: Functional

Verify that file downloads between the Earth ground station and VIOLET2 complete
successfully for both single-packet and multi-packet files, and that Tx/Rx
interruptions mid-transfer are handled gracefully with partial file saving and
resume capability.

Prerequisites (handled by hardware/conftest.py session fixture):
    SP1 – Physical hardware setup complete.
    SP2 – Earth Station running (LimeSDR.py + EARTH.py), ping succeeded.
    SP3 – OBC running (Lime_Mini_v5_headless.py + VIOLET2.py).

    test_data/test.txt must exist on the OBC (short file, < 248 bytes).
    test_data/larger_file.txt must exist on the OBC (> 248 bytes).
    If larger_file.txt is missing, generate it via SSH:
        python3 -c "print('A' * 400)" > test_data/larger_file.txt

Run with:
    pytest tests/hardware/verification2_file_transfer_and_interruption_handling_test.py -v -s
"""

import pytest


def _ask(prompt: str) -> bool:
    response = input(f"\n{prompt} (y/n): ").strip().lower()
    return response == "y"


class TestVerification2SubtestA_SinglePacketDownload:
    """
    Sub-test A – Single-packet file download.

    Downloads test_data/test.txt, which fits in a single AX.25 packet.
    """

    def test_subtestA_download_command_accepted(self):
        """
        In the EARTH.py terminal type:
            download test_data/test.txt

        The terminal should immediately print:
            Transfer started: 1 fragments expected (seq=N)
        """
        print("\n[Sub-test A – Step 2]  In the EARTH.py terminal type:")
        print("  download test_data/test.txt")
        print("Expected output:")
        print("  Transfer started: 1 fragments expected (seq=N)")

        assert _ask(
            "Did the EARTH.py terminal print 'Transfer started: 1 fragments expected'?"
        ), "Download command was not accepted or transfer start message not seen."

    def test_subtestA_single_packet_received(self):
        """
        After the transfer-start line, the terminal should print the single
        received fragment and a completion message:
            [1/1] type=0x05  pkt 1/1  payload_len=X
            Downloaded test_data/test.txt -> .../tmp_downloads/test.txt
        """
        print("\n[Sub-test A – Step 3]  Observe the rest of the EARTH.py output.")
        print("Expected output:")
        print("  [1/1] type=0x05  pkt 1/1  payload_len=X")
        print("  Downloaded test_data/test.txt -> .../tmp_downloads/test.txt")

        assert _ask(
            "Did the terminal show [1/1] type=0x05 and a 'Downloaded' confirmation?"
        ), "Single-packet download did not complete with the expected output."

    def test_subtestA_file_present_in_tmp_downloads(self):
        """
        Verify the downloaded file exists on the Earth PC at:
            tmp_downloads/test.txt

        On the Earth PC run:
            ls tmp_downloads/test.txt
        or open the file in a text editor to confirm it is not empty.
        """
        print("\n[Sub-test A – verification]  On the Earth PC confirm the file exists:")
        print("  ls tmp_downloads/test.txt")

        assert _ask(
            "Is tmp_downloads/test.txt present and non-empty on the Earth PC?"
        ), "Downloaded file not found in tmp_downloads/."


class TestVerification2SubtestB_MultiPacketDownload:
    """
    Sub-test B – Multi-packet file download.

    Downloads test_data/larger_file.txt (> 248 bytes), which requires two
    AX.25 packets.  If the file does not exist on the OBC, generate it first:
        python3 -c "print('A' * 400)" > test_data/larger_file.txt
    """

    def test_subtestB_larger_file_exists_on_obc(self):
        """
        Confirm test_data/larger_file.txt exists on the OBC before downloading.

        In the VIOLET2.py SSH session run:
            ls -lh test_data/larger_file.txt

        If missing, generate it:
            python3 -c "print('A' * 400)" > test_data/larger_file.txt
        """
        print("\n[Sub-test B – Step 4 pre-check]  On the OBC SSH session confirm:")
        print("  ls -lh test_data/larger_file.txt")
        print("If missing, generate it:")
        print("  python3 -c \"print('A' * 400)\" > test_data/larger_file.txt")

        assert _ask(
            "Does test_data/larger_file.txt exist on the OBC (> 248 bytes)?"
        ), "larger_file.txt not present on OBC – generate it before continuing."

    def test_subtestB_transfer_announced_two_packets(self):
        """
        In the EARTH.py terminal type:
            download test_data/larger_file.txt

        Expected output immediately:
            Transfer announced: 2 packets incoming (seq=N)
        """
        print("\n[Sub-test B – Step 5]  In the EARTH.py terminal type:")
        print("  download test_data/larger_file.txt")
        print("Expected first line of output:")
        print("  Transfer announced: 2 packets incoming (seq=N)")

        assert _ask(
            "Did the terminal print 'Transfer announced: 2 packets incoming'?"
        ), "Transfer announcement for 2-packet download not seen."

    def test_subtestB_both_fragments_received(self):
        """
        Both fragments should arrive and be acknowledged:
            [1/2] type=0x06  pkt 1/2  payload_len=248
            [2/2] type=0x08  pkt 2/2  payload_len=153
            Downloaded test_data/larger_file.txt -> .../tmp_downloads/larger_file.txt
        """
        print("\n[Sub-test B – Step 6]  Observe the rest of the EARTH.py output:")
        print("  [1/2] type=0x06  pkt 1/2  payload_len=248")
        print("  [2/2] type=0x08  pkt 2/2  payload_len=153")
        print("  Downloaded test_data/larger_file.txt -> .../tmp_downloads/larger_file.txt")

        assert _ask(
            "Did both fragments arrive (type 0x06 and 0x08) with a 'Downloaded' confirmation?"
        ), "Multi-packet download did not complete with the expected fragment types."

    def test_subtestB_fragment_types_correct(self):
        """
        Confirm fragment type bytes match the VIOLET2 protocol:
            First fragment:  type=0x06  (RESP_MULTI_START)
            Last fragment:   type=0x08  (RESP_MULTI_END)
        """
        print("\n[Sub-test B – type byte check]  Confirm type bytes in EARTH.py output:")
        print("  First fragment: type=0x06  (RESP_MULTI_START)")
        print("  Last fragment:  type=0x08  (RESP_MULTI_END)")

        assert _ask(
            "Are the type bytes 0x06 (start) and 0x08 (end) as expected?"
        ), "Fragment type bytes do not match expected RESP_MULTI_START / RESP_MULTI_END values."


class TestVerification2SubtestC_InterruptionHandlingAndResume:
    """
    Sub-test C – Interruption handling and resume capability.

    Initiates a multi-packet download and interrupts it mid-transfer with
    Ctrl+C, then resumes it.
    """

    def test_subtestC_ctrl_c_aborts_transfer(self):
        """
        Step 7 – Initiate a download and interrupt it mid-transfer.

        In the EARTH.py terminal type:
            download test_data/larger_file.txt

        IMMEDIATELY after the 'Transfer announced' line appears, press Ctrl+C.

        Expected output:
            Download aborted by user.
            Partial file saved to .../tmp_downloads/larger_file.txt.partial
            Resume data saved to .../tmp_downloads/larger_file.txt.resume.json
            Missing fragments: [N]  (M/2)
            Use 'resume larger_file.txt' to continue this download.
        """
        print("\n[Sub-test C – Step 7]  In the EARTH.py terminal type:")
        print("  download test_data/larger_file.txt")
        print("Then press Ctrl+C immediately after 'Transfer announced' appears.")
        print("Expected output:")
        print("  Download aborted by user.")
        print("  Partial file saved to .../tmp_downloads/larger_file.txt.partial")
        print("  Resume data saved to .../tmp_downloads/larger_file.txt.resume.json")
        print("  Missing fragments: [N]  (M/2)")
        print("  Use 'resume larger_file.txt' to continue this download.")

        assert _ask(
            "Did Ctrl+C produce the 'Download aborted by user' message with partial/resume paths?"
        ), "Ctrl+C interruption did not produce the expected abort message."

    def test_subtestC_partial_and_resume_files_exist(self):
        """
        Step 9 – Verify that both the partial file and the resume JSON exist.

        On the Earth PC run:
            ls tmp_downloads/larger_file.txt.partial
            ls tmp_downloads/larger_file.txt.resume.json
        """
        print("\n[Sub-test C – Step 9]  On the Earth PC verify both files exist:")
        print("  ls tmp_downloads/larger_file.txt.partial")
        print("  ls tmp_downloads/larger_file.txt.resume.json")

        assert _ask(
            "Do both .partial and .resume.json files exist in tmp_downloads/?"
        ), ".partial or .resume.json file not found after interruption."

    def test_subtestC_resume_retains_received_fragments(self):
        """
        Step 10-11 – Resume the interrupted download.

        In the EARTH.py terminal type:
            resume larger_file.txt

        Expected output confirms already-received fragments are kept:
            Resuming download of test_data/larger_file.txt
            Already have M/2 fragments, missing: [N]

        The transfer should then complete and print:
            Downloaded test_data/larger_file.txt -> .../tmp_downloads/larger_file.txt
        """
        print("\n[Sub-test C – Step 10-11]  In the EARTH.py terminal type:")
        print("  resume larger_file.txt")
        print("Expected output:")
        print("  Resuming download of test_data/larger_file.txt")
        print("  Already have M/2 fragments, missing: [N]")
        print("  ... (re-requests only missing fragment) ...")
        print("  Downloaded test_data/larger_file.txt -> .../tmp_downloads/larger_file.txt")

        assert _ask(
            "Did resume retain already-received fragments and re-request only the missing one(s)?"
        ), "Resume command did not retain existing fragments or did not complete the download."

    def test_subtestC_resumed_file_content_matches_original(self):
        """
        Verify the final downloaded file content matches the original on the OBC.

        On the Earth PC run:
            cat tmp_downloads/larger_file.txt

        Compare with the file on the OBC:
            cat test_data/larger_file.txt  (in an SSH session)

        Both should contain 400 'A' characters followed by a newline.
        """
        print("\n[Sub-test C – content verification]")
        print("On Earth PC:  cat tmp_downloads/larger_file.txt")
        print("On OBC:       cat test_data/larger_file.txt  (via SSH)")
        print("Both should show 400 'A' characters (and a trailing newline).")

        assert _ask(
            "Does the resumed downloaded file content match the original file on the OBC?"
        ), "Resumed download content does not match the original file on the OBC."
