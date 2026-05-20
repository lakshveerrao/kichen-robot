from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


CONFIG_PATH = Path("config.json")


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local SO-101 leader-to-follower teleoperation without Solo CLI.")
    parser.add_argument("--leader-port", default=None, help="Leader arm port, for example COM8.")
    parser.add_argument("--follower-port", default=None, help="Follower arm port, for example COM7.")
    parser.add_argument("--leader-id", default=None, help="Leader calibration id.")
    parser.add_argument("--follower-id", default=None, help="Follower calibration id.")
    parser.add_argument("--fps", type=float, default=60.0)
    parser.add_argument("--max-relative-target", type=float, default=5.0)
    parser.add_argument("--yes", action="store_true")
    return parser.parse_args()


def import_lerobot_classes() -> tuple[Any, Any, Any, Any]:
    try:
        from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig
        from lerobot.teleoperators.so_leader import SO101Leader, SO101LeaderConfig
    except ImportError as exc:
        raise RuntimeError("Could not import SO-101 leader/follower classes from LeRobot.") from exc
    return SO101Leader, SO101LeaderConfig, SO101Follower, SO101FollowerConfig


def main() -> int:
    args = parse_args()
    if args.fps <= 0 or args.fps > 120:
        print("--fps must be > 0 and <= 120.")
        return 1
    if args.max_relative_target <= 0 or args.max_relative_target > 30:
        print("--max-relative-target must be > 0 and <= 30.")
        return 1
    if not CONFIG_PATH.exists():
        print("Missing config.json. Run: pbl setup --port COM7 --leader-port COM8")
        return 1

    leader = None
    follower = None
    try:
        config = load_json(CONFIG_PATH)
        leader_port = args.leader_port or config.get("leader_port") or "COM8"
        follower_port = args.follower_port or config.get("robot_port") or config.get("follower_port") or "COM7"
        leader_id = args.leader_id or config.get("leader_id") or "1"
        follower_id = args.follower_id or config.get("follower_id") or config.get("robot_id") or "kitchen_stirrer_follower"

        SO101Leader, SO101LeaderConfig, SO101Follower, SO101FollowerConfig = import_lerobot_classes()
        print("PBL local teleop. No Solo CLI required.")
        print(f"leader_port={leader_port}, follower_port={follower_port}")
        print(f"leader_id={leader_id}, follower_id={follower_id}, fps={args.fps}")
        print("Move the leader arm to control the follower arm. Press Ctrl+C to stop.")
        if not args.yes:
            input("Press Enter to connect teleop, or Ctrl+C to cancel.")

        leader = SO101Leader(SO101LeaderConfig(port=leader_port, id=str(leader_id)))
        follower = SO101Follower(
            SO101FollowerConfig(
                port=follower_port,
                id=str(follower_id),
                max_relative_target=args.max_relative_target,
                cameras={},
            )
        )

        leader.connect()
        follower.connect()
        print("Leader and follower connected. Starting teleop.")

        interval = 1.0 / args.fps
        next_print = time.time()
        while True:
            started = time.perf_counter()
            action = leader.get_action()
            follower.send_action(action)
            now = time.time()
            if now >= next_print:
                print("Teleop running. Press Ctrl+C to stop.")
                next_print = now + 5.0
            elapsed = time.perf_counter() - started
            sleep_time = interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
    except KeyboardInterrupt:
        print("\nTeleop stopped by user.")
        return 0
    except Exception as exc:
        print(f"Local teleop failed: {exc}")
        return 1
    finally:
        for device, name in ((leader, "leader"), (follower, "follower")):
            if device is None:
                continue
            try:
                if not hasattr(device, "is_connected") or device.is_connected:
                    device.disconnect()
                    print(f"{name} disconnected.")
            except Exception as exc:
                print(f"Warning: {name} disconnect failed: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
