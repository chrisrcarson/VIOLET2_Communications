"""
Hardware test suite shared setup.

Run all hardware tests with:
    pytest tests/hardware/ -v -s

The -s flag is REQUIRED to see prompts and type responses.

Before running, complete SP1 (physical hardware setup) as described in Table 1
of the test plan. SP2 and SP3 are walked through interactively below.
"""

import pytest


def _ask(prompt: str) -> bool:
    """Prompt the tester and return True if they answer 'y'."""
    response = input(f"\n{prompt} (y/n): ").strip().lower()
    return response == "y"


@pytest.fixture(scope="session", autouse=True)
def hardware_setup():
    """
    Session-scoped fixture that walks through SP1, SP2, and SP3 once before
    any hardware test runs. If the tester cannot complete setup, all tests
    are skipped.
    """
    print("\n" + "=" * 65)
    print("  VIOLET2 HARDWARE TEST SUITE")
    print("  Run with: pytest tests/hardware/ -v -s")
    print("=" * 65)

    # ------------------------------------------------------------------
    # SP1 – Physical Hardware Setup
    # ------------------------------------------------------------------
    print("\n--- SP1: Physical Hardware Setup ---")
    print("1. Put on ESD wrist strap; work on ESD-safe mat.")
    print("2. Power on Earth Station PC. Connect LimeSDR (full-size) via USB.")
    print("3. Establish RF paths between LimeSDR and LimeSDR Mini:")
    print("   a. LimeSDR TX  -> 40 dB attenuator -> LimeSDR Mini RX  (145.91 MHz VHF downlink)")
    print("   b. LimeSDR Mini TX -> 40 dB attenuator -> LimeSDR RX   (436.83 MHz UHF uplink)")
    print("   All SMA connections hand-tight.")
    print("4. Connect LimeSDR Mini to OBC_SDR PCB via USB.")
    print("5. Connect PocketBeagle 2 (USB-C port) to Windows PC.")
    print("6. Apply 5 V to pin H2.25 or H2.26 on OBC_SDR PCB.")

    if not _ask("SP1 complete?"):
        pytest.skip("SP1 not complete – skipping all hardware tests.")

    # ------------------------------------------------------------------
    # SP3 – Initialize VIOLET2 Satellite Simulator (OBC)
    # (Initialize OBC before Earth station so it is ready to receive.)
    # ------------------------------------------------------------------
    print("\n--- SP3: Initialize VIOLET2 Satellite Simulator (OBC) ---")
    print("1. On Windows PC open a terminal and SSH to PocketBeagle 2:")
    print("     ssh debian@192.168.7.2   (password: beagle)")
    print("2. In the SSH session run:")
    print("     python3 Lime_Mini_v5_headless.py   <-- keep this session open")
    print("3. Open a SECOND SSH session to PocketBeagle 2 and run:")
    print("     python3 VIOLET2.py")
    print("   The VIOLET2 prompt should appear. When SP2 is also running")
    print("   this terminal will print received data and header parse output.")

    if not _ask("SP3 complete (Lime_Mini_v5_headless.py and VIOLET2.py both running)?"):
        pytest.skip("SP3 not complete – skipping all hardware tests.")

    # ------------------------------------------------------------------
    # SP2 – Initialize Earth Ground Station
    # ------------------------------------------------------------------
    print("\n--- SP2: Initialize Earth Ground Station ---")
    print("1. On Earth Station PC open a terminal, navigate to the project")
    print("   repo and run:")
    print("     python3 LimeSDR.py   <-- keep this terminal open")
    print("2. In the SAME terminal (or the script initialises automatically)")
    print("   verify the LimeSDR GUI shows RX Out / TX Sink / RX Source")
    print("   waterfall plots.")
    print("3. Open a SECOND terminal on the Earth PC and run:")
    print("     python3 EARTH.py")
    print("   The prompt should show:  VIOLET2>")
    print("4. Type 'ping' at the VIOLET2> prompt.")
    print("   A successful response looks like:")
    print("     Pong! Round-trip time: XXXX.X ms")
    print("   If ping times out after 4 attempts, do NOT proceed –")
    print("   recheck SP1 connections.")

    if not _ask("SP2 complete AND ping returned a Pong response?"):
        pytest.skip("SP2 not complete or ping failed – skipping all hardware tests.")

    print("\nAll setup procedures confirmed. Starting hardware tests...\n")
    yield
    print("\n" + "=" * 65)
    print("  Hardware test session complete.")
    print("=" * 65)
