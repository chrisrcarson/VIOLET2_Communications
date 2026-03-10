# Packet Loss and Retransmission Tests
# Verifies that the system correctly detects partial packet loss (bytes dropped from
# the start, middle, or end of a single packet or a multi-packet sequence) and that
# retransmitting the original packet allows data to be recovered and reassembled.

import pytest
from test_utils import (
    _buildViolet2Header,
    _padApplicationData,
    parseViolet2Packet,
    violet2ProtocolBuilder,
    VIOLET2_HEADER_LEN,
    VIOLET2_MIN_APP_DATA,
    VIOLET2_MAX_APP_DATA,
    RESP_SINGLE,
)

# Helper functions

# Build a valid single VIOLET2 packet (8-byte header + padded application data).
def _make_single_packet(payload: bytes) -> bytes:
    padded = _padApplicationData(payload)
    header = _buildViolet2Header(
        messageType=RESP_SINGLE,
        sequenceNumber=0,
        totalPackets=1,
        packetIndex=0,
        payloadLength=len(payload),
    )
    return header + padded


# Simulate losing the first n bytes of a received packet.
def _drop_start(packet: bytes, n: int) -> bytes:
    return packet[n:]


# Simulate losing n bytes starting at byte offset inside a received packet.
def _drop_middle(packet: bytes, offset: int, n: int) -> bytes:
    return packet[:offset] + packet[offset + n:]


# Simulate losing the last n bytes of a received packet.
def _drop_end(packet: bytes, n: int) -> bytes:
    return packet[:-n] if n > 0 else packet


# Return True only when the packet parsed cleanly with a complete payload.
# A plain checksum error is caught by the 'error' key. A subtler failure
# mode - end-byte truncation - leaves the header intact but returns fewer
# payload bytes than the header declared; this check catches both.
def _parse_is_successful(result: dict) -> bool:
    if "error" in result:
        return False
    # If fewer bytes arrived than the header declared, the tail was truncated.
    if len(result.get("payload", b"")) < result.get("payload_len", 0):
        return False
    return True


# Simulate packet delivery with an ACK/NACK-driven retransmission loop.
# The first parse attempt uses received_packet (which may be corrupted).
# If it fails, the sender is notified (NACK), and each subsequent attempt
# uses original_packet, modelling a clean retransmission.
# Returns (parsed_result, retransmissions_needed). retransmissions_needed is 0
# when the first delivery already succeeded.
def _attempt_parse_with_retransmission(
    original_packet: bytes,
    received_packet: bytes,
    max_retries: int = 3,
) -> tuple[dict, int]:
    result = parseViolet2Packet(received_packet)
    if _parse_is_successful(result):
        return result, 0  # delivered successfully on first attempt, no retransmission needed

    for retry in range(1, max_retries + 1):
        result = parseViolet2Packet(original_packet)  # clean retransmission
        if _parse_is_successful(result):
            return result, retry

    return result, max_retries  # all retransmissions exhausted


# Test 1: Bytes dropped from the start

# Losing bytes off the front of a packet corrupts the VIOLET2 Layer-2 header,
# causing a checksum mismatch or a 'too short' error. The receiver should
# trigger a retransmission and successfully parse the clean copy.
class TestBytesDroppedFromStart:

    def test_single_dropped_start_byte_is_detected(self): # Dropping 1 byte from the start must be detected as a parse error.
        payload = b"DROP_START_1" + b"\x00" * 80
        packet  = _make_single_packet(payload)
        corrupted = _drop_start(packet, 1)

        result = parseViolet2Packet(corrupted)

        assert "error" in result, (
            "Expected a parse error when 1 leading byte is dropped"
        )

    def test_multiple_dropped_start_bytes_are_detected(self): # Dropping 2, 4, and a full header's worth of bytes from the start must each raise an error.
        payload = b"DROP_START_MULTI" + b"\x00" * 76
        packet  = _make_single_packet(payload)

        for drop_count in [2, 4, VIOLET2_HEADER_LEN]:
            corrupted = _drop_start(packet, drop_count)
            result    = parseViolet2Packet(corrupted)
            assert "error" in result, (
                f"Expected parse error when {drop_count} leading byte(s) are dropped"
            )

    # Dropping exactly VIOLET2_HEADER_LEN bytes exposes only the application
    # data to the parser, which should fail due to corrupted field values.
    def test_dropping_entire_header_from_start_is_detected(self):
        payload   = b"FULL_HDR_DROP" + b"\x00" * 79
        packet    = _make_single_packet(payload)
        corrupted = _drop_start(packet, VIOLET2_HEADER_LEN)

        result = parseViolet2Packet(corrupted)

        assert "error" in result, (
            "Expected parse error when the entire VIOLET2 header is stripped from the front"
        )

    def test_retransmission_recovers_from_start_byte_loss(self): # After start-byte loss is detected, one retransmission delivers the correct payload.
        payload   = b"RETX_START_OK" + b"\x00" * 79
        packet    = _make_single_packet(payload)
        corrupted = _drop_start(packet, 3)

        result, retransmissions = _attempt_parse_with_retransmission(packet, corrupted)

        assert "error" not in result, (
            f"Expected successful parse after retransmission, got: {result}"
        )
        assert retransmissions >= 1, (
            "Expected at least one retransmission to have been needed"
        )
        assert result["payload"] == payload, (
            "Payload recovered after retransmission does not match the original"
        )


# Test 2: Bytes dropped from the middle

# Losing bytes from inside a packet corrupts internal header or payload bytes.
# Header-region drops cause a checksum mismatch. Payload-region drops shorten
# the recovered data relative to the declared payloadLength. Both cases must
# be detected, and retransmission must restore the original payload.
class TestBytesDroppedFromMiddle:

    # Dropping bytes from the 6-byte header core shifts every subsequent field,
    # causing a guaranteed checksum mismatch.
    def test_header_region_middle_drop_causes_checksum_mismatch(self):
        payload   = b"HDR_MID_DROP" + b"\x00" * 80
        packet    = _make_single_packet(payload)
        corrupted = _drop_middle(packet, offset=2, n=2)  # excise totalPackets + packetIndex

        result = parseViolet2Packet(corrupted)

        assert "error" in result, (
            "Expected a checksum-mismatch error when 2 header bytes are dropped from the middle"
        )

    # Dropping bytes from the payload area leaves the header intact (no checksum
    # error) but shortens the returned data relative to the declared payloadLength.
    def test_payload_region_middle_drop_shortens_recovered_data(self):
        payload   = b"PAYLOAD_MID_DROP" + b"\x00" * 76
        packet    = _make_single_packet(payload)

        # Drop 4 bytes from the middle of the application-data section
        mid_offset = VIOLET2_HEADER_LEN + (VIOLET2_MIN_APP_DATA // 2)
        corrupted  = _drop_middle(packet, offset=mid_offset, n=4)

        result = parseViolet2Packet(corrupted)

        # The parser must either flag an error or return fewer bytes than expected
        data_damaged = (
            "error" in result
            or len(result.get("payload", b"")) < len(payload)
        )
        assert data_damaged, (
            "Expected payload-region middle drop to yield an error or a truncated payload"
        )

    def test_retransmission_recovers_from_middle_byte_loss(self): # A retransmission after mid-packet loss restores the complete payload.
        payload   = b"RETX_MID_OK" + b"\x00" * 81
        packet    = _make_single_packet(payload)
        corrupted = _drop_middle(packet, offset=3, n=2)

        result, retransmissions = _attempt_parse_with_retransmission(packet, corrupted)

        assert "error" not in result, (
            f"Expected successful parse after retransmission, got: {result}"
        )
        assert retransmissions >= 1, (
            "Expected at least one retransmission to have been needed"
        )
        assert result["payload"] == payload, (
            "Payload recovered after retransmission does not match the original"
        )


# Test 3: Bytes dropped from the end

# Losing bytes off the tail of a packet truncates the application data,
# producing fewer payload bytes than the header's payloadLength field declares.
# Retransmission must deliver all bytes intact.
class TestBytesDroppedFromEnd:

    def test_end_byte_drop_truncates_payload(self): # Dropping bytes from the end of a packet must result in a shorter-than-declared payload.
        payload   = b"END_DROP_TEST" + b"\x00" * 79
        packet    = _make_single_packet(payload)
        corrupted = _drop_end(packet, 10)

        result = parseViolet2Packet(corrupted)

        data_shortened = (
            "error" in result
            or len(result.get("payload", b"")) < len(payload)
        )
        assert data_shortened, (
            "Expected a truncated payload or an error when 10 trailing bytes are dropped"
        )

    # Keeping only the VIOLET2 header (no application data) must yield an empty
    # or absent payload, not a crash, and never silently return the full payload.
    def test_dropping_all_payload_bytes_leaves_bare_header(self):
        payload     = b"BARE_HEADER_TEST" + b"\x00" * 76
        packet      = _make_single_packet(payload)
        header_only = packet[:VIOLET2_HEADER_LEN]

        result = parseViolet2Packet(header_only)

        # If it parses without error, the returned payload must be empty
        if "error" not in result:
            assert len(result["payload"]) == 0, (
                "Expected zero payload bytes when all application data is stripped from tail"
            )

    def test_retransmission_recovers_from_end_byte_loss(self): # A retransmission after tail-byte loss restores the complete payload.
        payload   = b"RETX_END_OK" + b"\x00" * 81
        packet    = _make_single_packet(payload)
        corrupted = _drop_end(packet, 8)

        result, retransmissions = _attempt_parse_with_retransmission(packet, corrupted)

        assert "error" not in result, (
            f"Expected successful parse after retransmission, got: {result}"
        )
        assert retransmissions >= 1, (
            "Expected at least one retransmission to have been needed"
        )
        assert result["payload"] == payload, (
            "Payload recovered after retransmission does not match the original"
        )


# Test 4: Byte loss in a multi-packet sequence

# When one or more packets within a VIOLET2 multi-packet sequence are corrupted,
# the receiver must detect exactly which packets failed (via per-packet parse
# errors), request selective retransmission of those packets, and correctly
# reassemble the full payload once the missing packets are re-delivered.
class TestByteLossInMultiPacketSequence:

    def _build_multi_packets(self, payload: bytes) -> list[bytes]: # Build a VIOLET2 multi-packet sequence using violet2ProtocolBuilder.
        packets = violet2ProtocolBuilder(payload)
        assert len(packets) > 1, (
            "Test payload must span multiple VIOLET2 packets; "
            f"increase payload size above {VIOLET2_MAX_APP_DATA} bytes"
        )
        return packets

    # 4a: Detection of corruption at each position

    def test_corruption_in_first_packet_is_detected(self): # A corrupted first packet (header middle-byte loss) must be flagged as an error.
        payload = b"MULTI_START_DROP_" * 20            # comfortably above MAX_APP_DATA
        packets = self._build_multi_packets(payload)

        # Drop totalPackets+packetIndex bytes from the header (offset 2, n=2).
        # This shifts pl_hi/pl_lo into those fields and causes a guaranteed
        # checksum mismatch regardless of the global sequence counter.
        corrupted_first = _drop_middle(packets[0], offset=2, n=2)
        result = parseViolet2Packet(corrupted_first)

        assert "error" in result, (
            "Expected parse error for a corrupted first packet in a multi-packet sequence"
        )

    def test_corruption_in_middle_packet_is_detected(self): # A corrupted mid-sequence packet (middle-byte loss) must be flagged as an error.
        # 16 * 50 = 800 bytes → ceil(800/248) = 4 packets, guaranteeing a true middle packet.
        payload = b"MULTI_MID_DROP__" * 50
        packets = self._build_multi_packets(payload)
        assert len(packets) >= 3, (
            "Need at least 3 packets to test mid-sequence corruption"
        )

        mid_idx   = len(packets) // 2
        corrupted = _drop_middle(packets[mid_idx], offset=2, n=2)
        result    = parseViolet2Packet(corrupted)

        assert "error" in result, (
            f"Expected parse error for corrupted packet at index {mid_idx}"
        )

    def test_corruption_in_last_packet_is_detected(self): # A corrupted final packet (end-byte loss) must be flagged or return truncated data.
        payload = b"MULTI_END_DROP__" * 20
        packets = self._build_multi_packets(payload)

        corrupted_last = _drop_end(packets[-1], 6)
        result         = parseViolet2Packet(corrupted_last)

        data_damaged = (
            "error" in result
            or len(result.get("payload", b"")) < len(packets[-1]) - VIOLET2_HEADER_LEN
        )
        assert data_damaged, (
            "Expected corrupted last packet to be detected or return truncated payload"
        )

    # 4b: Selective packet retransmission restores full sequence

    # When exactly one packet in a sequence is corrupted:
    #   1. Per-packet parsing identifies that specific packet as the failed one.
    #   2. Selective retransmission (re-delivering only failed packets) restores the sequence.
    #   3. Reassembly of the clean sequence exactly reproduces the original payload.
    def test_selective_retransmission_restores_full_payload(self):
        payload = b"FULL_SEQUENCE_RETRANSMIT_" * 15     # ~375 bytes, 2 or more packets
        packets = self._build_multi_packets(payload)

        corrupt_idx     = 1
        corrupted_copy  = _drop_middle(packets[corrupt_idx], offset=3, n=4)

        # Simulate reception: every packet arrives, but one is corrupted
        received = list(packets)
        received[corrupt_idx] = corrupted_copy

        # Pass 1: parse every received packet 
        pass1_results = [parseViolet2Packet(p) for p in received]
        failed_indices = [i for i, r in enumerate(pass1_results) if "error" in r]

        assert corrupt_idx in failed_indices, (
            f"Expected packet {corrupt_idx} to be identified as failed after first pass"
        )

        # NACK: retransmit only the failed packets 
        for idx in failed_indices:
            received[idx] = packets[idx]        # replace with clean original

        # Pass 2: re-parse the corrected sequence 
        pass2_results = [parseViolet2Packet(p) for p in received]
        errors_after_retx = [r for r in pass2_results if "error" in r]

        assert len(errors_after_retx) == 0, (
            f"Expected no errors after selective retransmission, got: {errors_after_retx}"
        )

        # Reassemble and verify
        reassembled = b"".join(r["payload"] for r in pass2_results)
        assert reassembled == payload, (
            "Reassembled payload after selective retransmission does not match the original"
        )

    # When every packet in a sequence is corrupted, the receiver must identify
    # all of them as failed and retransmitting all of them must restore the original payload.
    def test_all_packets_corrupt_require_full_retransmission(self):
        # 16 * 70 = 1120 bytes → 5 packets, so every position is well-exercised.
        payload = b"ALL_PKT_CORRUPT_" * 70
        packets = self._build_multi_packets(payload)

        # Drop the totalPackets+packetIndex bytes (offset 2, n=2) from every packet.
        # This reliably shifts pl_hi/pl_lo into those header fields, producing a
        # checksum mismatch in each packet independently of the sequence counter.
        received = [_drop_middle(p, offset=2, n=2) for p in packets]

        # All must be detected as errors
        pass1_results = [parseViolet2Packet(p) for p in received]
        failed_indices = [i for i, r in enumerate(pass1_results) if "error" in r]

        assert len(failed_indices) == len(packets), (
            f"Expected all {len(packets)} packets to be flagged as failed, "
            f"got {len(failed_indices)}"
        )

        # Retransmit all
        pass2_results = [parseViolet2Packet(p) for p in packets]
        errors_after_retx = [r for r in pass2_results if "error" in r]

        assert len(errors_after_retx) == 0, (
            f"Expected no errors after full retransmission, got: {errors_after_retx}"
        )

        reassembled = b"".join(r["payload"] for r in pass2_results)
        assert reassembled == payload, (
            "Reassembled payload after full retransmission does not match the original"
        )


# Test 5: Retransmission behaviour

# End-to-end retransmission-loop properties: clean packets need no retry,
# one corrupt delivery triggers exactly one retransmission, and a source that
# always sends corrupt data exhausts the retry budget without recovery.
class TestRetransmissionBehaviour:

    def test_clean_packet_requires_no_retransmission(self): # An uncorrupted packet is parsed successfully on the first attempt (0 retransmissions).
        payload = b"NO_RETX_NEEDED" + b"\x00" * 78
        packet  = _make_single_packet(payload)

        result, retransmissions = _attempt_parse_with_retransmission(packet, packet)

        assert "error" not in result, (
            f"Expected clean packet to parse without error, got: {result}"
        )
        assert retransmissions == 0, (
            "Expected zero retransmissions for an uncorrupted packet"
        )

    # When the first delivery is corrupt but the retransmission is clean,
    # recovery happens on the very first retry.
    def test_single_corrupt_delivery_needs_exactly_one_retransmission(self):
        payload   = b"ONE_RETX_ONLY" + b"\x00" * 79
        packet    = _make_single_packet(payload)
        corrupted = _drop_start(packet, 1)

        result, retransmissions = _attempt_parse_with_retransmission(packet, corrupted)

        assert "error" not in result, (
            f"Expected successful parse after retransmission, got: {result}"
        )
        assert retransmissions == 1, (
            f"Expected exactly 1 retransmission, got {retransmissions}"
        )
        assert result["payload"] == payload, (
            "Payload after retransmission does not match original"
        )

    def test_start_byte_loss_retransmission_restores_correct_checksum_ok_flag(self): # The parsed result after a successful retransmission must report checksum_ok = True.
        payload   = b"CHECKSUM_FLAG_TEST" + b"\x00" * 74
        packet    = _make_single_packet(payload)
        corrupted = _drop_start(packet, 2)

        result, _ = _attempt_parse_with_retransmission(packet, corrupted)

        assert result.get("checksum_ok") is True, (
            "Expected checksum_ok=True in the result of a successfully retransmitted packet"
        )

    # If every copy the sender can offer is also corrupt (e.g., the source data
    # is permanently damaged), the retransmission loop must exhaust max_retries
    # and return a final error rather than looping forever.
    def test_persistently_corrupt_source_exhausts_retry_budget(self):
        payload          = b"ALWAYS_BAD" + b"\x00" * 82
        original_packet  = _make_single_packet(payload)
        always_corrupted = _drop_start(original_packet, 4)

        # Pass always_corrupted as both the received AND the "original" to
        # simulate a source that can only ever produce a corrupt copy.
        result, retransmissions = _attempt_parse_with_retransmission(
            always_corrupted, always_corrupted, max_retries=3
        )

        assert "error" in result, (
            "Expected a final error when every retransmission attempt is also corrupted"
        )
        assert retransmissions == 3, (
            f"Expected max_retries (3) retransmissions to be exhausted, got {retransmissions}"
        )

    def test_middle_byte_loss_retransmission_restores_full_payload(self): # Retransmission after middle-byte loss returns the exact original payload bytes.
        payload   = b"MID_FULL_PAYLOAD_RESTORE" + b"\x00" * 68
        packet    = _make_single_packet(payload)
        # Drop packetIndex+pl_hi (offset 3, n=2): shifts checksum byte to pl_lo
        # position, causing a deterministic checksum mismatch for this payload.
        corrupted = _drop_middle(packet, offset=3, n=2)

        result, retransmissions = _attempt_parse_with_retransmission(packet, corrupted)

        assert "error" not in result
        assert retransmissions >= 1
        assert result["payload"] == payload, (
            "Payload restored after middle-byte-loss retransmission does not match original"
        )

    def test_end_byte_loss_retransmission_restores_full_payload(self): # Retransmission after end-byte loss returns the exact original payload bytes.
        payload   = b"END_FULL_PAYLOAD_RESTORE" + b"\x00" * 68
        packet    = _make_single_packet(payload)
        corrupted = _drop_end(packet, 5)

        result, retransmissions = _attempt_parse_with_retransmission(packet, corrupted)

        assert "error" not in result
        assert retransmissions >= 1
        assert result["payload"] == payload, (
            "Payload restored after end-byte-loss retransmission does not match original"
        )
