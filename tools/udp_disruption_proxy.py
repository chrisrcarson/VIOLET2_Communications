import argparse
import random
import select
import socket
import time

AX25_HEADER_LEN = 16
VIOLET2_HEADER_LEN = 8

MSG_NACK = 0xA1
RESP_MULTI_START = 0x06
RESP_MULTI_CONT = 0x07
RESP_MULTI_END = 0x08


def parse_violet2_header(frame: bytes):
    if len(frame) < AX25_HEADER_LEN + VIOLET2_HEADER_LEN:
        return None

    base = AX25_HEADER_LEN
    msg_type = frame[base + 0]
    seq_num = frame[base + 1]
    total_pkt = frame[base + 2]
    pkt_idx = frame[base + 3]

    return {
        "msg_type": msg_type,
        "seq_num": seq_num,
        "total_pkt": total_pkt,
        "pkt_idx": pkt_idx,
    }


def parse_nack_seq(frame: bytes):
    parsed = parse_violet2_header(frame)
    if not parsed or parsed["msg_type"] != MSG_NACK:
        return None

    payload_offset = AX25_HEADER_LEN + VIOLET2_HEADER_LEN
    if len(frame) <= payload_offset:
        return None

    return frame[payload_offset]


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "UDP disruption proxy between EARTH and VIOLET2. "
            "Use this in a third terminal to simulate missing early fragments."
        )
    )
    parser.add_argument("--listen-earth-tx", type=int, default=27101, help="Proxy port that receives EARTH uplink")
    parser.add_argument("--forward-violet-rx", type=int, default=27201, help="VIOLET2 receive port")
    parser.add_argument("--listen-violet-tx", type=int, default=27200, help="Proxy port that receives VIOLET2 downlink")
    parser.add_argument("--forward-earth-rx", type=int, default=27100, help="EARTH receive port")
    parser.add_argument(
        "--mode",
        choices=["late-start", "drop-start-once", "random-chaos"],
        default="late-start",
        help=(
            "late-start holds fragment 0 until NACK; "
            "drop-start-once drops first fragment 0 and passes retransmits; "
            "random-chaos applies random drop/delay/duplicate/reorder to downlink multi-packet responses"
        ),
    )
    parser.add_argument(
        "--release-timeout",
        type=float,
        default=3.0,
        help="Auto-release held start fragment after this many seconds if no NACK arrives",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-packet details",
    )
    parser.add_argument(
        "--max-disruptions",
        type=int,
        default=1,
        help="Maximum number of start-fragment disruptions to inject across the whole run",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional random seed for reproducible random-chaos behavior",
    )
    parser.add_argument("--drop-rate", type=float, default=0.20, help="Probability of dropping an eligible packet in random-chaos mode")
    parser.add_argument("--delay-rate", type=float, default=0.25, help="Probability of delaying an eligible packet in random-chaos mode")
    parser.add_argument("--duplicate-rate", type=float, default=0.10, help="Probability of duplicating an eligible packet in random-chaos mode")
    parser.add_argument("--reorder-rate", type=float, default=0.20, help="Probability of reordering adjacent eligible packets in random-chaos mode")
    parser.add_argument("--max-delay-ms", type=int, default=1200, help="Maximum random delay (ms) for delayed packets in random-chaos mode")
    return parser


def log(message: str):
    print(f"[proxy] {message}")


def main():
    args = build_parser().parse_args()

    rng = random.Random(args.seed)

    earth_rx_addr = ("127.0.0.1", args.forward_earth_rx)
    violet_rx_addr = ("127.0.0.1", args.forward_violet_rx)

    uplink_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    uplink_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    uplink_sock.bind(("127.0.0.1", args.listen_earth_tx))

    downlink_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    downlink_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    downlink_sock.bind(("127.0.0.1", args.listen_violet_tx))

    tx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # seq -> {"packet": bytes, "held_at": float}
    held_start = {}
    # list of pending delayed downlink packets: {"send_at": float, "packet": bytes, "reason": str}
    delayed_downlink = []
    # a single packet held to swap ordering with the next eligible packet in random-chaos mode
    reorder_hold = None
    # seq values that already had start disruption applied
    disrupted_once = set()
    disruptions_done = 0

    log(
        "started "
        f"earth_tx_in={args.listen_earth_tx} -> violet_rx={args.forward_violet_rx}, "
        f"violet_tx_in={args.listen_violet_tx} -> earth_rx={args.forward_earth_rx}, "
        f"mode={args.mode}"
    )

    try:
        while True:
            now = time.time()

            # Release delayed packets whose send time has arrived.
            if delayed_downlink:
                due = [item for item in delayed_downlink if item["send_at"] <= now]
                delayed_downlink = [item for item in delayed_downlink if item["send_at"] > now]
                for item in due:
                    tx_sock.sendto(item["packet"], earth_rx_addr)
                    if args.verbose:
                        log(f"released delayed packet ({item['reason']})")

            # If no partner packet arrived for reorder swap in time, release held packet.
            if reorder_hold is not None and reorder_hold["release_at"] <= now:
                tx_sock.sendto(reorder_hold["packet"], earth_rx_addr)
                if args.verbose:
                    log(
                        "released reorder-held packet without swap "
                        f"seq={reorder_hold['seq']} pkt={reorder_hold['pkt_idx'] + 1}/{reorder_hold['total_pkt']}"
                    )
                reorder_hold = None

            # Auto-release safety in late-start mode if no NACK arrives.
            if args.mode == "late-start" and held_start:
                for seq, state in list(held_start.items()):
                    if now - state["held_at"] >= args.release_timeout:
                        tx_sock.sendto(state["packet"], earth_rx_addr)
                        del held_start[seq]
                        log(f"auto-released held start fragment for seq={seq}")

            readable, _, _ = select.select([uplink_sock, downlink_sock], [], [], 0.2)

            for sock in readable:
                data, _ = sock.recvfrom(65535)

                # EARTH -> Proxy -> VIOLET2
                if sock is uplink_sock:
                    nack_seq = parse_nack_seq(data)
                    if nack_seq is not None and nack_seq in held_start:
                        tx_sock.sendto(held_start[nack_seq]["packet"], earth_rx_addr)
                        del held_start[nack_seq]
                        log(f"released held start fragment due to NACK for seq={nack_seq}")

                    tx_sock.sendto(data, violet_rx_addr)
                    if args.verbose:
                        parsed = parse_violet2_header(data)
                        if parsed:
                            log(
                                "uplink "
                                f"type=0x{parsed['msg_type']:02X} seq={parsed['seq_num']} "
                                f"pkt={parsed['pkt_idx'] + 1}/{parsed['total_pkt']}"
                            )
                    continue

                # VIOLET2 -> Proxy -> EARTH
                parsed = parse_violet2_header(data)
                if not parsed:
                    tx_sock.sendto(data, earth_rx_addr)
                    continue

                msg_type = parsed["msg_type"]
                seq = parsed["seq_num"]
                pkt_idx = parsed["pkt_idx"]
                total_pkt = parsed["total_pkt"]

                is_multi_resp = msg_type in (RESP_MULTI_START, RESP_MULTI_CONT, RESP_MULTI_END) and total_pkt > 1

                if args.mode == "random-chaos" and is_multi_resp:
                    # Random drop: simulate packet loss on arbitrary fragments.
                    if rng.random() < max(0.0, min(1.0, args.drop_rate)):
                        log(
                            f"random drop seq={seq} pkt={pkt_idx + 1}/{total_pkt}"
                        )
                        continue

                    # Random reorder by holding one packet and swapping with next eligible packet.
                    if reorder_hold is None and rng.random() < max(0.0, min(1.0, args.reorder_rate)):
                        hold_seconds = max(0.0, args.max_delay_ms) / 1000.0
                        reorder_hold = {
                            "packet": data,
                            "release_at": now + hold_seconds,
                            "seq": seq,
                            "pkt_idx": pkt_idx,
                            "total_pkt": total_pkt,
                        }
                        log(
                            f"random reorder hold seq={seq} pkt={pkt_idx + 1}/{total_pkt}"
                        )
                        continue

                    if reorder_hold is not None:
                        tx_sock.sendto(data, earth_rx_addr)
                        tx_sock.sendto(reorder_hold["packet"], earth_rx_addr)
                        log(
                            "random reorder swap "
                            f"sent seq={seq} pkt={pkt_idx + 1}/{total_pkt} before held seq={reorder_hold['seq']} pkt={reorder_hold['pkt_idx'] + 1}/{reorder_hold['total_pkt']}"
                        )
                        reorder_hold = None
                        continue

                    # Random delay: send later with jitter.
                    if rng.random() < max(0.0, min(1.0, args.delay_rate)):
                        delay_ms = rng.randint(1, max(1, args.max_delay_ms))
                        delayed_downlink.append(
                            {
                                "send_at": now + (delay_ms / 1000.0),
                                "packet": data,
                                "reason": f"random delay {delay_ms}ms seq={seq} pkt={pkt_idx + 1}/{total_pkt}",
                            }
                        )
                        log(
                            f"random delay seq={seq} pkt={pkt_idx + 1}/{total_pkt} by {delay_ms}ms"
                        )
                    else:
                        tx_sock.sendto(data, earth_rx_addr)

                    # Random duplicate: optionally schedule a second copy of same packet.
                    if rng.random() < max(0.0, min(1.0, args.duplicate_rate)):
                        dup_delay_ms = rng.randint(10, max(10, min(250, args.max_delay_ms)))
                        delayed_downlink.append(
                            {
                                "send_at": now + (dup_delay_ms / 1000.0),
                                "packet": data,
                                "reason": f"random duplicate +{dup_delay_ms}ms seq={seq} pkt={pkt_idx + 1}/{total_pkt}",
                            }
                        )
                        log(
                            f"random duplicate seq={seq} pkt={pkt_idx + 1}/{total_pkt} in {dup_delay_ms}ms"
                        )

                    if args.verbose:
                        log(
                            "downlink "
                            f"type=0x{msg_type:02X} seq={seq} pkt={pkt_idx + 1}/{total_pkt}"
                        )
                    continue

                should_disrupt_start = (
                    is_multi_resp
                    and pkt_idx == 0
                    and seq not in disrupted_once
                    and disruptions_done < max(0, args.max_disruptions)
                )

                if should_disrupt_start:
                    disrupted_once.add(seq)
                    disruptions_done += 1

                    if args.mode == "drop-start-once":
                        log(
                            f"dropped first start fragment for seq={seq} "
                            f"({disruptions_done}/{max(0, args.max_disruptions)})"
                        )
                        continue

                    held_start[seq] = {"packet": data, "held_at": time.time()}
                    log(
                        f"held first start fragment for seq={seq}; waiting for NACK "
                        f"({disruptions_done}/{max(0, args.max_disruptions)})"
                    )
                    continue

                tx_sock.sendto(data, earth_rx_addr)
                if args.verbose:
                    log(
                        "downlink "
                        f"type=0x{msg_type:02X} seq={seq} pkt={pkt_idx + 1}/{total_pkt}"
                    )

    except KeyboardInterrupt:
        log("stopped")
    finally:
        uplink_sock.close()
        downlink_sock.close()
        tx_sock.close()


if __name__ == "__main__":
    main()
