"""
Verification 1 – Communication Protocol Compliance
Associated Requirement: R-G0G-001
Test Type: Conformance

Verify that AX.25 protocol is used for all communications between the Earth
ground station and VIOLET2. Confirm correct frame structure including callsigns,
control byte, PID byte, and FCS across both uplink and downlink directions.

Prerequisites (handled by hardware/conftest.py session fixture):
    SP1 – Physical hardware setup complete.
    SP2 – Earth Station running (LimeSDR.py + EARTH.py), ping succeeded.
    SP3 – OBC running (Lime_Mini_v5_headless.py + VIOLET2.py).

Run with:
    pytest tests/hardware/verification1_communication_protocol_compliance_test.py -v -s
"""

import pytest


def _ask(prompt: str) -> bool:
    response = input(f"\n{prompt} (y/n): ").strip().lower()
    return response == "y"


class TestVerification1CommunicationProtocolCompliance:
    """
    Table 4: Verification 1 – Communication Protocol Compliance

    All sub-tests use the 'ping' command sent from the EARTH.py terminal.
    Observations are made in the LimeSDR.py debug terminal and the
    VIOLET2.py terminal on the OBC.
    """

    def test_step4_ping_returns_pong(self):
        """
        Step 4 – Confirm the link is active via ping.

        In the EARTH.py terminal type:
            ping

        Expected response:
            Pong! Round-trip time: XXXX.X ms
        """
        print("\n[Step 4] In the EARTH.py terminal type: ping")
        print("Expected: Pong! Round-trip time: XXXX.X ms")

        assert _ask(
            "Did 'ping' return a Pong response with a round-trip time?"
        ), "Ping did not return a Pong – link is not active."

    def test_step5_ax25_destination_callsign_bytes(self):
        """
        Step 5a – Confirm destination callsign bytes in VIOLET2.py output.

        In the VIOLET2.py terminal on the OBC, look for:
            [VIOLET2 Transmission]: Bytes 0x00 - 0x05: 56 45 39 43 4E 42
        That hex decodes to:  VE9CNB  (Earth station destination callsign)
        """
        print("\n[Step 5a] In the VIOLET2.py terminal on the OBC confirm:")
        print("  [VIOLET2 Transmission]: Bytes 0x00-0x05: 56 45 39 43 4E 42  (VE9CNB)")

        assert _ask(
            "Do you see destination callsign bytes 56 45 39 43 4E 42 (VE9CNB)?"
        ), "Destination callsign bytes not found or incorrect."

    def test_step5_ax25_source_callsign_bytes(self):
        """
        Step 5b – Confirm source callsign bytes in VIOLET2.py output.

        In the VIOLET2.py terminal on the OBC, look for:
            [RECEIVED DATA]: Bytes 0x06 - 0x0B: 56 45 39 56 4C 54
        That hex decodes to:  VE9VLT  (satellite source callsign)
        """
        print("\n[Step 5b] In the VIOLET2.py terminal on the OBC confirm:")
        print("  [RECEIVED DATA]: Bytes 0x06-0x0B: 56 45 39 56 4C 54  (VE9VLT)")

        assert _ask(
            "Do you see source callsign bytes 56 45 39 56 4C 54 (VE9VLT)?"
        ), "Source callsign bytes not found or incorrect."

    def test_step5_ax25_ssid_bytes(self):
        """
        Step 5c – Confirm SSID bytes.

        In the VIOLET2.py terminal on the OBC look for:
            Byte 0x0C: 60  (destination SSID)
            Byte 0x0D: E0  (source SSID)
        """
        print("\n[Step 5c] In the VIOLET2.py terminal on the OBC confirm:")
        print("  Byte 0x0C: 60  (destination SSID)")
        print("  Byte 0x0D: E0  (source SSID)")

        assert _ask(
            "Do you see SSID bytes 0x0C=60 and 0x0D=E0?"
        ), "SSID bytes not found or incorrect."

    def test_step5_ax25_control_byte(self):
        """
        Step 5d – Confirm control byte is 0x03 (UI frame).

        In the VIOLET2.py terminal on the OBC look for:
            Byte 0x0E: 03  (control – unnumbered information frame)

        Also confirm in LimeSDR.py PDU hex dump.
        """
        print("\n[Step 5d] Confirm control byte in VIOLET2.py and LimeSDR.py output:")
        print("  Byte 0x0E: 03  (control – UI frame)")

        assert _ask(
            "Is the control byte 0x03?"
        ), "Control byte is not 0x03."

    def test_step5_ax25_pid_byte(self):
        """
        Step 5e – Confirm PID byte is 0xF0 (no layer 3).

        In the VIOLET2.py terminal on the OBC look for:
            Byte 0x0F: F0  (PID – no layer 3 protocol)

        Also confirm in LimeSDR.py PDU hex dump.
        """
        print("\n[Step 5e] Confirm PID byte in VIOLET2.py and LimeSDR.py output:")
        print("  Byte 0x0F: F0  (PID – no layer 3)")

        assert _ask(
            "Is the PID byte 0xF0?"
        ), "PID byte is not 0xF0."

    def test_step5_pdu_length_and_callsigns_in_limesdr(self):
        """
        Step 5f – Confirm PDU length and callsigns in LimeSDR.py debug output.

        In the LimeSDR.py terminal on the Earth PC look for the
        VERBOSE PDU DEBUG PRINT block:
            pdu_length = 116
            Destination callsign: 56 45 39 56 4C 54  (VE9VLT)
            Source callsign:      56 45 39 43 4E 42  (VE9CNB)
        """
        print("\n[Step 5f] In the LimeSDR.py debug terminal confirm:")
        print("  pdu_length = 116")
        print("  Destination callsign bytes: 56 45 39 56 4C 54  (VE9VLT)")
        print("  Source callsign bytes:      56 45 39 43 4E 42  (VE9CNB)")

        assert _ask(
            "Does LimeSDR.py show pdu_length=116 with the correct callsign bytes?"
        ), "PDU length or callsign bytes in LimeSDR.py are incorrect."

    def test_step6_violet2_header_decoded_with_checksum_ok(self):
        """
        Step 6 – Confirm VIOLET2 header is decoded correctly on the OBC.

        In the VIOLET2.py terminal on the OBC look for:
            [VIOLET2 Header]: type=0xB0  seq=N  pkt 1/1  payload_len=22  checksum=OK
            [VIOLET2] ping received, sending pong
        """
        print("\n[Step 6] In the VIOLET2.py terminal on the OBC confirm:")
        print("  [VIOLET2 Header]: type=0xB0  seq=N  pkt 1/1  payload_len=22  checksum=OK")
        print("  [VIOLET2] ping received, sending pong")

        assert _ask(
            "Does the VIOLET2 header show type=0xB0, pkt 1/1, checksum=OK, and 'ping received'?"
        ), "VIOLET2 header decode or ping handler did not produce the expected output."

    def test_step7_downlink_callsigns_reversed_in_limesdr(self):
        """
        Step 7 – Confirm the OBC downlink response also uses AX.25.

        After the OBC sends its pong, a SECOND PDU block should appear in
        LimeSDR.py. Check that the callsigns are reversed relative to the
        uplink frame:
            Source callsign:      VE9VLT  (satellite is now the sender)
            Destination callsign: VE9CNB  (Earth is now the destination)
        """
        print("\n[Step 7] In the LimeSDR.py terminal look for a SECOND PDU block after")
        print("the pong is sent. Confirm callsigns are reversed:")
        print("  Source:      VE9VLT")
        print("  Destination: VE9CNB")

        assert _ask(
            "Does the downlink PDU block show source=VE9VLT and destination=VE9CNB?"
        ), "Downlink AX.25 callsigns are not reversed or the downlink PDU was not observed."
