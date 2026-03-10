# Payload Packet Size Tests
# Associated Requirement: R-G0G-003
# Verifies that AX.25 packet payload per frame is within the VIOLET2 min/max sizes,
# and that payloads above max are fragmented and reassembled correctly.

import pytest
from test_utils import (
    pad_payload,
    validate_payload,
    fragment_payload,
    VIOLET2_MIN_APP_DATA,
    VIOLET2_MAX_APP_DATA,
)

MIN_PAYLOAD_SIZE = VIOLET2_MIN_APP_DATA
MAX_PAYLOAD_SIZE = VIOLET2_MAX_APP_DATA

# Test 1: below minimum payload size
class TestBelowMinimumPayload:

    # a payload below MIN should be padded up to MIN.
    def testPayloadBelowMinimumIsPadded(self): 
        payload = b"A" * (MIN_PAYLOAD_SIZE - 1)
        padded = pad_payload(payload)
        assert len(padded) >= MIN_PAYLOAD_SIZE, (
            f"Expected padded payload to be at least {MIN_PAYLOAD_SIZE} bytes, got {len(padded)}"
        )

     # a payload below MIN should fail validation.
    def testPayloadBelowMinimumFailsValidation(self):
        payload = b"A" * (MIN_PAYLOAD_SIZE - 1)
        assert not validate_payload(payload), (
            "Expected validate_payload() to return False for payload below minimum size"
        )

# Test 2: at minimum payload size
class TestAtMinimumPayload:

    # a payload of exactly MIN should pass validation.
    def testPayloadAtMinimumPassesValidation(self): 
        payload = b"A" * MIN_PAYLOAD_SIZE
        assert validate_payload(payload), (
            "Expected validate_payload() to return True for payload at minimum size"
        )

    # a payload of exactly MIN should not be fragmented.
    def testPayloadAtMinimumIsNotFragmented(self): 
        payload = b"A" * MIN_PAYLOAD_SIZE
        fragments = fragment_payload(payload)
        assert len(fragments) == 1, (
            f"Expected 1 fragment for minimum size payload, got {len(fragments)}"
        )

# Test 3: At maximum payload size
class TestAtMaximumPayload:

    # a payload of exactly MAX should pass validation.
    def testPayloadAtMaximumPassesValidation(self): 
        payload = b"A" * MAX_PAYLOAD_SIZE
        assert validate_payload(payload), (
            "Expected validate_payload() to return True for payload at maximum size"
        )

    # a payload of exactly MAX should not be fragmented.
    def testPayloadAtMaximumIsNotFragmented(self): 
        payload = b"A" * MAX_PAYLOAD_SIZE
        fragments = fragment_payload(payload)
        assert len(fragments) == 1, (
            f"Expected 1 fragment for maximum size payload, got {len(fragments)}"
        )

# Test 4: Above maximum payload size
class TestAboveMaximumPayload:

    # a payload above MAX should be fragmented into valid chunks.
    def testPayloadAboveMaximumIsFragmented(self): 
        payload = b"A" * (MAX_PAYLOAD_SIZE + 1)
        fragments = fragment_payload(payload)
        assert len(fragments) > 1, (
            "Expected payload of 256 bytes to be split into multiple fragments"
        )

    # each fragment should be at most MAX.
    def testAllFragmentsBelowMaximumSize(self): 
        payload = b"A" * (MAX_PAYLOAD_SIZE * 2 + 16)
        fragments = fragment_payload(payload)
        for i, fragment in enumerate(fragments):
            assert len(fragment) <= MAX_PAYLOAD_SIZE, (
                f"Fragment {i} exceeds maximum size: {len(fragment)} bytes"
            )

    # reassembled fragments should equal the original payload.
    def testFragmentsReassembleCorrectly(self): 
        payload = b"A" * 512
        fragments = fragment_payload(payload)
        reassembled = b"".join(fragments)
        assert reassembled == payload, (
            "Reassembled payload does not match original"
        )

    # a payload above MAX should fail single-frame validation.
    def testLargePayloadAboveMaximumFailsValidation(self): 
        payload = b"A" * (MAX_PAYLOAD_SIZE + 1)
        assert not validate_payload(payload), (
            "Expected validate_payload() to return False for payload of 256 bytes or more"
        )
