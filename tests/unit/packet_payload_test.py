#Payload Packet Size Tests
#Associated Requirement: R-G0G-003

#Verifies that AX.25 packet payload per frame is 100 bytes or more and less than 256 bytes,
#and that payloads of 256 bytes or more are fragmented and reassembled correctly.

#NOTE: waiting on implementation for functions such as: pad_payload(), validate_payload(), and fragment_payload().

# Import(s)
import pytest

# Constants
MIN_PAYLOAD_SIZE = 100
MAX_PAYLOAD_SIZE = 256  # 256 and above triggers fragmentation

# Placeholder functions (until utils.py exists)
def pad_payload(payload: bytes) -> bytes: # pad payload to MIN_PAYLOAD_SIZE if below minimum.
    raise NotImplementedError("pad_payload() not yet implemented in packet_utils.py")

def validate_payload(payload: bytes) -> bool: # return true if payload is within valid size range. 
    raise NotImplementedError("validate_payload() not yet implemented in packet_utils.py")

def fragment_payload(payload: bytes) -> list[bytes]: # fragment payload into chunks each below MAX_PAYLOAD_SIZE
    raise NotImplementedError("fragment_payload() not yet implemented in packet_utils.py")

# Test 1: below minimum payload size (99 bytes)
class TestBelowMinimumPayload:

    def test_payload_below_minimum_is_padded(self): # a payload below 100 bytes should be padded up to 100 bytes.
        payload = b"A" * 99
        padded = pad_payload(payload)
        assert len(padded) >= MIN_PAYLOAD_SIZE, (
            f"Expected padded payload to be at least {MIN_PAYLOAD_SIZE} bytes, got {len(padded)}"
        )

    def test_payload_below_minimum_fails_validation(self): # a payload below 100 bytes should fail validation."""
        payload = b"A" * 99
        assert not validate_payload(payload), (
            "Expected validate_payload() to return False for payload below minimum size"
        )

# Test 2: at minimum payload size (100 bytes)
class TestAtMinimumPayload:

    def test_payload_at_minimum_passes_validation(self): # a payload of exactly 100 bytes should pass validation.
        payload = b"A" * 100
        assert validate_payload(payload), (
            "Expected validate_payload() to return True for payload at minimum size"
        )

    def test_payload_at_minimum_is_not_fragmented(self): # a payload of exactly 100 bytes should not be fragmented."""
        payload = b"A" * 100
        fragments = fragment_payload(payload)
        assert len(fragments) == 1, (
            f"Expected 1 fragment for minimum size payload, got {len(fragments)}"
        )

# Test 3: At maximum payload size (255 bytes)
class TestAtMaximumPayload:

    def test_payload_at_maximum_passes_validation(self): # a payload of exactly 255 bytes should pass validation."""
        payload = b"A" * 255
        assert validate_payload(payload), (
            "Expected validate_payload() to return True for payload at maximum size"
        )

    def test_payload_at_maximum_is_not_fragmented(self): # a payload of 255 bytes should not be fragmented."""
        payload = b"A" * 255
        fragments = fragment_payload(payload)
        assert len(fragments) == 1, (
            f"Expected 1 fragment for maximum size payload, got {len(fragments)}"
        )

# Test 4: Above maximum payload size (256+ bytes)
class TestAboveMaximumPayload:

    def test_payload_above_maximum_is_fragmented(self): # a payload of 256 bytes or more should be fragmented into valid chunks."""
        payload = b"A" * 256
        fragments = fragment_payload(payload)
        assert len(fragments) > 1, (
            "Expected payload of 256 bytes to be split into multiple fragments"
        )

    def test_all_fragments_below_maximum_size(self): # each fragment should be below 256 bytes."""
        payload = b"A" * 512
        fragments = fragment_payload(payload)
        for i, fragment in enumerate(fragments):
            assert len(fragment) < MAX_PAYLOAD_SIZE, (
                f"Fragment {i} exceeds maximum size: {len(fragment)} bytes"
            )

    def test_fragments_reassemble_correctly(self): # reassembled fragments should equal the original payload."""
        payload = b"A" * 512
        fragments = fragment_payload(payload)
        reassembled = b"".join(fragments)
        assert reassembled == payload, (
            "Reassembled payload does not match original"
        )

    def test_large_payload_above_maximum_fails_validation(self): # a payload of 256 bytes or more should fail single-frame validation."""
        payload = b"A" * 256
        assert not validate_payload(payload), (
            "Expected validate_payload() to return False for payload of 256 bytes or more"
        )
