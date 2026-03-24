
def validate_ax25_header(
    raw_data: bytes,
    expected_dest_callsign: str,
    expected_dest_ssid_hex: str,
    expected_src_callsign: str,
    expected_src_ssid_hex: str,
    expected_control_hex: str,
    expected_pid_hex: str,
    header_len: int = 16,
) -> bool:
    """
    Validate an AX.25 header against expected values.
    Returns: True if the header is valid, False otherwise.
    """
    if len(raw_data) < header_len:
        return False

    dest_ok = raw_data[0:6] == expected_dest_callsign.encode("ascii")
    dest_ssid_ok = raw_data[6:7] == bytes.fromhex(expected_dest_ssid_hex)
    src_ok = raw_data[7:13] == expected_src_callsign.encode("ascii")
    src_ssid_ok = raw_data[13:14] == bytes.fromhex(expected_src_ssid_hex)
    control_ok = raw_data[14:15] == bytes.fromhex(expected_control_hex)
    pid_ok = raw_data[15:16] == bytes.fromhex(expected_pid_hex)

    return (
        dest_ok
        and dest_ssid_ok
        and src_ok
        and src_ssid_ok
        and control_ok
        and pid_ok
    )
