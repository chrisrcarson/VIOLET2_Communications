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

# Constants (mirrored from test_utils for backward compatibility)
MIN_PAYLOAD_SIZE = VIOLET2_MIN_APP_DATA
MAX_PAYLOAD_SIZE = VIOLET2_MAX_APP_DATA

# Test 1: below minimum payload size
class TestBelowMinimumPayload:

    def test_payload_below_minimum_is_padded(self): # a payload below MIN should be padded up to MIN.
        payload = b"A" * (MIN_PAYLOAD_SIZE - 1)
        padded = pad_payload(payload)
        assert len(padded) >= MIN_PAYLOAD_SIZE, (
            f"Expected padded payload to be at least {MIN_PAYLOAD_SIZE} bytes, got {len(padded)}"
        )

    def test_payload_below_minimum_fails_validation(self): # a payload below MIN should fail validation.
        payload = b"A" * (MIN_PAYLOAD_SIZE - 1)
        assert not validate_payload(payload), (
            "Expected validate_payload() to return False for payload below minimum size"
        )

# Test 2: at minimum payload size
class TestAtMinimumPayload:

    def test_payload_at_minimum_passes_validation(self): # a payload of exactly MIN should pass validation.
        payload = b"A" * MIN_PAYLOAD_SIZE
        assert validate_payload(payload), (
            "Expected validate_payload() to return True for payload at minimum size"
        )

    def test_payload_at_minimum_is_not_fragmented(self): # a payload of exactly MIN should not be fragmented.
        payload = b"A" * MIN_PAYLOAD_SIZE
        fragments = fragment_payload(payload)
        assert len(fragments) == 1, (
            f"Expected 1 fragment for minimum size payload, got {len(fragments)}"
        )

# Test 3: At maximum payload size
class TestAtMaximumPayload:

    def test_payload_at_maximum_passes_validation(self): # a payload of exactly MAX should pass validation.
        payload = b"A" * MAX_PAYLOAD_SIZE
        assert validate_payload(payload), (
            "Expected validate_payload() to return True for payload at maximum size"
        )

    def test_payload_at_maximum_is_not_fragmented(self): # a payload of exactly MAX should not be fragmented.
        payload = b"A" * MAX_PAYLOAD_SIZE
        fragments = fragment_payload(payload)
        assert len(fragments) == 1, (
            f"Expected 1 fragment for maximum size payload, got {len(fragments)}"
        )

# Test 4: Above maximum payload size
class TestAboveMaximumPayload:

    def test_payload_above_maximum_is_fragmented(self): # a payload above MAX should be fragmented into valid chunks.
        payload = b"A" * (MAX_PAYLOAD_SIZE + 1)
        fragments = fragment_payload(payload)
        assert len(fragments) > 1, (
            "Expected payload of 256 bytes to be split into multiple fragments"
        )

    def test_all_fragments_below_maximum_size(self): # each fragment should be at most MAX.
        payload = b"A" * (MAX_PAYLOAD_SIZE * 2 + 16)
        fragments = fragment_payload(payload)
        for i, fragment in enumerate(fragments):
            assert len(fragment) <= MAX_PAYLOAD_SIZE, (
                f"Fragment {i} exceeds maximum size: {len(fragment)} bytes"
            )

    def test_fragments_reassemble_correctly(self): # reassembled fragments should equal the original payload.
        payload = b"A" * 512
        fragments = fragment_payload(payload)
        reassembled = b"".join(fragments)
        assert reassembled == payload, (
            "Reassembled payload does not match original"
        )

    def test_large_payload_above_maximum_fails_validation(self): # a payload above MAX should fail single-frame validation.
        payload = b"A" * (MAX_PAYLOAD_SIZE + 1)
        assert not validate_payload(payload), (
            "Expected validate_payload() to return False for payload of 256 bytes or more"
        )
