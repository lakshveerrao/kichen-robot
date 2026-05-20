from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from robot_api import (
    DEFAULT_SPEED_SCALE,
    connect_robot,
    disconnect_robot,
    move_to_position,
    read_current_position,
    stop_robot,
)


CONFIG_PATH = Path("config.json")
PAN_KEY = "shoulder_pan.pos"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sweep only the SO-101 shoulder pan joint.")
    parser.add_argument("--degrees", type=float, default=15.0, help="Degrees left/right from current pan.")
    parser.add_argument("--cycles", type=int, default=1, help="Number of left-right sweep cycles.")
    parser.add_argument("--speed-scale", type=float, default=None, help="Override config speed_scale.")
    parser.add_argument("--pause", type=float, default=0.5, help="Pause after each sweep point.")
    parser.add_argument("--dry-run", action="store_true", help="Print targets without moving.")
    parser.add_argument("--yes", action="store_true", help="Do not wait for Enter before movement.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.degrees <= 0 or args.degrees > 45:
        print("--degrees must be > 0 and <= 45 for this safety test.")
        return 1
    if args.cycles <= 0 or args.cycles > 10:
        print("--cycles must be > 0 and <= 10.")
        return 1
    if not CONFIG_PATH.exists():
        print("Missing config.json. Copy config.example.json to config.json and edit robot_port.")
        return 1

    robot = None
    try:
        config = load_json(CONFIG_PATH)
        speed_scale = args.speed_scale if args.speed_scale is not None else config.get("speed_scale", DEFAULT_SPEED_SCALE)

        print("Pan sweep safety test.")
        print("Only shoulder_pan.pos will move. All other joints stay at their current positions.")
        print("Keep hand near power switch. Make sure the bowl area is empty. Press Ctrl+C to stop.")
        print(f"degrees=+/-{args.degrees}, cycles={args.cycles}, speed_scale={speed_scale}")

        if args.dry_run:
            print("Dry run only. No robot connection or movement will happen.")
            print("Targets after reading current pan would be: center, left, right, center.")
            return 0

        if not args.yes:
            input("Press Enter to connect and start the pan sweep, or Ctrl+C to cancel.")

        print(f"Connecting to SO-101 follower on {config.get('robot_port')}...")
        robot = connect_robot(config)
        current = read_current_position(robot)
        if PAN_KEY not in current:
            print(f"Robot observation did not include {PAN_KEY}.")
            return 1

        center = current[PAN_KEY]
        left = center - args.degrees
        right = center + args.degrees
        print(f"Current pan: {center}")
        print(f"Sweeping pan from {left} to {right}")

        center_pose = dict(current)
        left_pose = dict(current)
        right_pose = dict(current)
        left_pose[PAN_KEY] = left
        right_pose[PAN_KEY] = right

        print("Moving to sweep left")
        move_to_position(robot, left_pose, speed_scale)
        time.sleep(args.pause)

        for cycle in range(1, args.cycles + 1):
            print(f"Cycle {cycle}: moving to sweep right")
            move_to_position(robot, right_pose, speed_scale)
            time.sleep(args.pause)
            print(f"Cycle {cycle}: moving to sweep left")
            move_to_position(robot, left_pose, speed_scale)
            time.sleep(args.pause)

        print("Returning to center")
        move_to_position(robot, center_pose, speed_scale)
        print("Pan sweep complete.")
        return 0
    except KeyboardInterrupt:
        print("\nCtrl+C received. Stopping robot now.")
        stop_robot(robot)
        return 130
    except Exception as exc:
        print(f"Pan sweep failed: {exc}")
        return 1
    finally:
        disconnect_robot(robot)
        print("Disconnected.")


if __name__ == "__main__":
    raise SystemExit(main())
