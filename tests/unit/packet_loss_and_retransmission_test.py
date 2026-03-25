# Packet Loss and Retransmission Tests
# Verifies that the system correctly detects partial packet loss (bytes dropped from
# the start, middle, or end of a single packet or a multi-packet sequence) and that
# retransmitting the original packet allows data to be recovered and reassembled.

from __future__ import annotations

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

# Build a valid single VIOLET2 packet (8-byte header + padded application data).
def _makeSinglePacket(payload: bytes) -> bytes:
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
def _dropStart(packet: bytes, n: int) -> bytes:
    return packet[n:]


# Simulate losing n bytes starting at byte offset inside a received packet.
def _dropMiddle(packet: bytes, offset: int, n: int) -> bytes:
    return packet[:offset] + packet[offset + n:]


# Simulate losing the last n bytes of a received packet.
def _dropEnd(packet: bytes, n: int) -> bytes:
    return packet[:-n] if n > 0 else packet


# Return True only when the packet parsed cleanly with a complete payload.
# A plain checksum error is caught by the 'error' key. A subtler failure
# mode - end-byte truncation - leaves the header intact but returns fewer
# payload bytes than the header declared; this check catches both.
def _parseIsSuccessful(result: dict) -> bool:
    if "error" in result:
        return False
    # If fewer bytes arrived than the header declared, the tail was truncated.
    if len(result.get("payload", b"")) < result.get("payload_len", 0):
        return False
    return True


# Simulate packet delivery with an ACK/NACK-driven retransmission loop.
# The first parse attempt uses receivedPacket (which may be corrupted).
# If it fails, the sender is notified (NACK), and each subsequent attempt
# uses originalPacket, modelling a clean retransmission.
# Returns (parsed_result, retransmissions_needed). retransmissions_needed is 0
# when the first delivery already succeeded.
def _attemptParseWithRetransmission(
    originalPacket: bytes,
    receivedPacket: bytes,
    maxRetries: int = 3,
) -> tuple[dict, int]:
    result = parseViolet2Packet(receivedPacket)
    if _parseIsSuccessful(result):
        return result, 0  # delivered successfully on first attempt, no retransmission needed

    for retry in range(1, maxRetries + 1):
        result = parseViolet2Packet(originalPacket)  # clean retransmission
        if _parseIsSuccessful(result):
            return result, retry

    return result, maxRetries  # all retransmissions exhausted


# Test 1: Bytes dropped from the start
class TestBytesDroppedFromStart:

    # dropping 1 byte from the start must be detected as a parse error.
    def testSingleDroppedStartByteIsDetected(self): 
        payload = b"DROP_START_1" + b"\x00" * 80
        packet  = _makeSinglePacket(payload)
        corrupted = _dropStart(packet, 1)

        result = parseViolet2Packet(corrupted)

        assert "error" in result, (
            "Expected a parse error when 1 leading byte is dropped"
        )

    # dropping 2, 4, and a full header's worth of bytes from the start must each raise an error.
    def testMultipleDroppedStartBytesAreDetected(self): 
        payload = b"DROP_START_MULTI" + b"\x00" * 76
        packet  = _makeSinglePacket(payload)

        for drop_count in [2, 4, VIOLET2_HEADER_LEN]:
            corrupted = _dropStart(packet, drop_count)
            result    = parseViolet2Packet(corrupted)
            assert "error" in result, (
                f"Expected parse error when {drop_count} leading byte(s) are dropped"
            )

    # dropping exactly VIOLET2_HEADER_LEN bytes exposes only the application data to the parser, which should fail due to corrupted field values.
    def testDroppingEntireHeaderFromStartIsDetected(self):
        payload   = b"FULL_HDR_DROP" + b"\x00" * 79
        packet    = _makeSinglePacket(payload)
        corrupted = _dropStart(packet, VIOLET2_HEADER_LEN)

        result = parseViolet2Packet(corrupted)

        assert "error" in result, (
            "Expected parse error when the entire VIOLET2 header is stripped from the front"
        )

    # after start-byte loss is detected, one retransmission delivers the correct payload.
    def testRetransmissionRecoversFromStartByteLoss(self): 
        payload   = b"RETX_START_OK" + b"\x00" * 79
        packet    = _makeSinglePacket(payload)
        corrupted = _dropStart(packet, 3)

        result, retransmissions = _attemptParseWithRetransmission(packet, corrupted)

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
class TestBytesDroppedFromMiddle:

    # dropping bytes from the 6-byte header core shifts every subsequent field, causing a guaranteed checksum mismatch.
    def testHeaderRegionMiddleDropCausesChecksumMismatch(self):
        payload   = b"HDR_MID_DROP" + b"\x00" * 80
        packet    = _makeSinglePacket(payload)
        corrupted = _dropMiddle(packet, offset=2, n=2) 

        result = parseViolet2Packet(corrupted)

        assert "error" in result, (
            "Expected a checksum-mismatch error when 2 header bytes are dropped from the middle"
        )

    # dropping bytes from the payload area leaves the header intact (no checksum error) but shortens the returned data relative to the declared payloadLength.
    def testPayloadRegionMiddleDropShortensRecoveredData(self):
        payload   = b"PAYLOAD_MID_DROP" + b"\x00" * 76
        packet    = _makeSinglePacket(payload)

        # drop 4 bytes from the middle of the application-data section
        mid_offset = VIOLET2_HEADER_LEN + (VIOLET2_MIN_APP_DATA // 2)
        corrupted  = _dropMiddle(packet, offset=mid_offset, n=4)

        result = parseViolet2Packet(corrupted)

        # the parser must either flag an error or return fewer bytes than expected
        data_damaged = (
            "error" in result
            or len(result.get("payload", b"")) < len(payload)
        )
        assert data_damaged, (
            "Expected payload-region middle drop to yield an error or a truncated payload"
        )

    # a retransmission after mid-packet loss restores the complete payload.
    def testRetransmissionRecoversFromMiddleByteLoss(self): 
        payload   = b"RETX_MID_OK" + b"\x00" * 81
        packet    = _makeSinglePacket(payload)
        corrupted = _dropMiddle(packet, offset=3, n=2)

        result, retransmissions = _attemptParseWithRetransmission(packet, corrupted)

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
class TestBytesDroppedFromEnd:

    # dropping bytes from the end of a packet must result in a shorter-than-declared payload.
    def testEndByteDropTruncatesPayload(self): 
        payload   = b"END_DROP_TEST" + b"\x00" * 79
        packet    = _makeSinglePacket(payload)
        corrupted = _dropEnd(packet, 10)

        result = parseViolet2Packet(corrupted)

        data_shortened = (
            "error" in result
            or len(result.get("payload", b"")) < len(payload)
        )
        assert data_shortened, (
            "Expected a truncated payload or an error when 10 trailing bytes are dropped"
        )

    # keeping only the VIOLET2 header (no application data) must yield an empty or absent payload, not a crash, and never silently return the full payload.
    def testDroppingAllPayloadBytesLeavesBareHeader(self):
        payload     = b"BARE_HEADER_TEST" + b"\x00" * 76
        packet      = _makeSinglePacket(payload)
        header_only = packet[:VIOLET2_HEADER_LEN]

        result = parseViolet2Packet(header_only)

        # if it parses without error, the returned payload must be empty
        if "error" not in result:
            assert len(result["payload"]) == 0, (
                "Expected zero payload bytes when all application data is stripped from tail"
            )

    # a retransmission after tail-byte loss restores the complete payload.
    def testRetransmissionRecoversFromEndByteLoss(self): 
        payload   = b"RETX_END_OK" + b"\x00" * 81
        packet    = _makeSinglePacket(payload)
        corrupted = _dropEnd(packet, 8)

        result, retransmissions = _attemptParseWithRetransmission(packet, corrupted)

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
class TestByteLossInMultiPacketSequence:

    # build a VIOLET2 multi-packet sequence using violet2ProtocolBuilder.
    def _buildMultiPackets(self, payload: bytes) -> list[bytes]: 
        packets = violet2ProtocolBuilder(payload)
        assert len(packets) > 1, (
            "Test payload must span multiple VIOLET2 packets; "
            f"increase payload size above {VIOLET2_MAX_APP_DATA} bytes"
        )
        return packets

    # 4a: Detection of corruption at each position

    # a corrupted first packet (header middle-byte loss) must be flagged as an error.
    def testCorruptionInFirstPacketIsDetected(self): 
        payload = b"MULTI_START_DROP_" * 20     
        packets = self._buildMultiPackets(payload)

        corruptedFirst = _dropMiddle(packets[0], offset=2, n=2)
        result = parseViolet2Packet(corruptedFirst)

        assert "error" in result, (
            "Expected parse error for a corrupted first packet in a multi-packet sequence"
        )

    # a corrupted mid-sequence packet (middle-byte loss) must be flagged as an error.
    def testCorruptionInMiddlePacketIsDetected(self): 
        payload = b"MULTI_MID_DROP__" * 50
        packets = self._buildMultiPackets(payload)
        assert len(packets) >= 3, (
            "Need at least 3 packets to test mid-sequence corruption"
        )

        mid_idx   = len(packets) // 2
        corrupted = _dropMiddle(packets[mid_idx], offset=2, n=2)
        result    = parseViolet2Packet(corrupted)

        assert "error" in result, (
            f"Expected parse error for corrupted packet at index {mid_idx}"
        )

    # a corrupted final packet (end-byte loss) must be flagged or return truncated data.
    def testCorruptionInLastPacketIsDetected(self): 
        payload = b"MULTI_END_DROP__" * 20
        packets = self._buildMultiPackets(payload)

        corrupted_last = _dropEnd(packets[-1], 6)
        result         = parseViolet2Packet(corrupted_last)

        data_damaged = (
            "error" in result
            or len(result.get("payload", b"")) < len(packets[-1]) - VIOLET2_HEADER_LEN
        )
        assert data_damaged, (
            "Expected corrupted last packet to be detected or return truncated payload"
        )

    # 4b: Selective packet retransmission restores full sequence

    # when exactly one packet in a sequence is corrupted:
    #   1. per-packet parsing identifies that specific packet as the failed one.
    #   2. selective retransmission (re-delivering only failed packets) restores the sequence.
    #   3. reassembly of the clean sequence exactly reproduces the original payload.
    def testSelectiveRetransmissionRestoresFullPayload(self):
        payload = b"FULL_SEQUENCE_RETRANSMIT_" * 15     
        packets = self._buildMultiPackets(payload)

        corrupt_idx     = 1
        corrupted_copy  = _dropMiddle(packets[corrupt_idx], offset=3, n=4)

        received = list(packets)
        received[corrupt_idx] = corrupted_copy

        # pass 1: parse every received packet 
        pass1_results = [parseViolet2Packet(p) for p in received]
        failed_indices = [i for i, r in enumerate(pass1_results) if "error" in r]

        assert corrupt_idx in failed_indices, (
            f"Expected packet {corrupt_idx} to be identified as failed after first pass"
        )

        # NACK: retransmit only the failed packets 
        for idx in failed_indices:
            received[idx] = packets[idx] # replace with clean original

        # pass 2: re-parse the corrected sequence 
        pass2_results = [parseViolet2Packet(p) for p in received]
        errors_after_retx = [r for r in pass2_results if "error" in r]

        assert len(errors_after_retx) == 0, (
            f"Expected no errors after selective retransmission, got: {errors_after_retx}"
        )

        # reassemble and verify
        reassembled = b"".join(r["payload"] for r in pass2_results)
        assert reassembled == payload, (
            "Reassembled payload after selective retransmission does not match the original"
        )

    # when every packet in a sequence is corrupted, the receiver must identify all of them as failed and retransmitting all of them must restore the original payload.
    def testAllPacketsCorruptRequireFullRetransmission(self):
        payload = b"ALL_PKT_CORRUPT_" * 70
        packets = self._buildMultiPackets(payload)

        received = [_dropMiddle(p, offset=2, n=2) for p in packets]

        pass1_results = [parseViolet2Packet(p) for p in received]
        failed_indices = [i for i, r in enumerate(pass1_results) if "error" in r]

        assert len(failed_indices) == len(packets), (
            f"Expected all {len(packets)} packets to be flagged as failed, "
            f"got {len(failed_indices)}"
        )

        # retransmit all
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
class TestRetransmissionBehaviour:

    # an uncorrupted packet is parsed successfully on the first attempt (0 retransmissions).
    def testCleanPacketRequiresNoRetransmission(self): 
        payload = b"NO_RETX_NEEDED" + b"\x00" * 78
        packet  = _makeSinglePacket(payload)

        result, retransmissions = _attemptParseWithRetransmission(packet, packet)

        assert "error" not in result, (
            f"Expected clean packet to parse without error, got: {result}"
        )
        assert retransmissions == 0, (
            "Expected zero retransmissions for an uncorrupted packet"
        )

    # when the first delivery is corrupt but the retransmission is clean, recovery happens on the very first retry.
    def testSingleCorruptDeliveryNeedsExactlyOneRetransmission(self):
        payload   = b"ONE_RETX_ONLY" + b"\x00" * 79
        packet    = _makeSinglePacket(payload)
        corrupted = _dropStart(packet, 1)

        result, retransmissions = _attemptParseWithRetransmission(packet, corrupted)

        assert "error" not in result, (
            f"Expected successful parse after retransmission, got: {result}"
        )
        assert retransmissions == 1, (
            f"Expected exactly 1 retransmission, got {retransmissions}"
        )
        assert result["payload"] == payload, (
            "Payload after retransmission does not match original"
        )

    # the parsed result after a successful retransmission must report checksum_ok = True.
    def testStartByteLossRetransmissionRestoresCorrectChecksumOkFlag(self): 
        payload   = b"CHECKSUM_FLAG_TEST" + b"\x00" * 74
        packet    = _makeSinglePacket(payload)
        corrupted = _dropStart(packet, 2)

        result, _ = _attemptParseWithRetransmission(packet, corrupted)

        assert result.get("checksum_ok") is True, (
            "Expected checksum_ok=True in the result of a successfully retransmitted packet"
        )

    # if every copy the sender can offer is also corrupt (e.g., the source data is permanently damaged), the retransmission loop must exhaust maxRetries and return a final error rather than looping forever.
    def testPersistentlyCorruptSourceExhaustsRetryBudget(self):
        payload          = b"ALWAYS_BAD" + b"\x00" * 82
        originalPacket  = _makeSinglePacket(payload)
        always_corrupted = _dropStart(originalPacket, 4)

        result, retransmissions = _attemptParseWithRetransmission(
            always_corrupted, always_corrupted, maxRetries=3
        )

        assert "error" in result, (
            "Expected a final error when every retransmission attempt is also corrupted"
        )
        assert retransmissions == 3, (
            f"Expected maxRetries (3) retransmissions to be exhausted, got {retransmissions}"
        )

    # retransmission after middle-byte loss returns the exact original payload bytes.
    def testMiddleByteLossRetransmissionRestoresFullPayload(self): 
        payload   = b"MID_FULL_PAYLOAD_RESTORE" + b"\x00" * 68
        packet    = _makeSinglePacket(payload)
        corrupted = _dropMiddle(packet, offset=3, n=2)

        result, retransmissions = _attemptParseWithRetransmission(packet, corrupted)

        assert "error" not in result
        assert retransmissions >= 1
        assert result["payload"] == payload, (
            "Payload restored after middle-byte-loss retransmission does not match original"
        )

    # retransmission after end-byte loss returns the exact original payload bytes.
    def testEndByteLossRetransmissionRestoresFullPayload(self): 
        payload   = b"END_FULL_PAYLOAD_RESTORE" + b"\x00" * 68
        packet    = _makeSinglePacket(payload)
        corrupted = _dropEnd(packet, 5)

        result, retransmissions = _attemptParseWithRetransmission(packet, corrupted)

        assert "error" not in result
        assert retransmissions >= 1
        assert result["payload"] == payload, (
            "Payload restored after end-byte-loss retransmission does not match original"
        )
