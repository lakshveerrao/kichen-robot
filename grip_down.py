from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from robot_api import (
    DEFAULT_SPEED_SCALE,
    RobotApiError,
    connect_robot,
    disconnect_robot,
    move_to_position,
    read_current_position,
    stop_robot,
    validate_position,
)


CONFIG_PATH = Path("config.json")
GRIPPER_JOINT = "gripper.pos"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Grip at the current pose, then move to DOWN.")
    parser.add_argument(
        "--grip-value",
        type=float,
        default=-5.0,
        help="Target gripper.pos value for gripping. On this setup, lower values tighten the gripper.",
    )
    parser.add_argument("--pause", type=float, default=0.5, help="Pause after gripping before moving down.")
    parser.add_argument("--speed-scale", type=float, default=None, help="Override config speed_scale.")
    parser.add_argument("--dry-run", action="store_true", help="Print the action without moving.")
    parser.add_argument("--yes", action="store_true", help="Do not wait for Enter before movement.")
    return parser.parse_args()


def load_down_pose(config: dict) -> dict[str, float]:
    positions_path = Path(config.get("positions_file", "positions.json"))
    positions = load_json(positions_path)
    if "DOWN" not in positions or positions["DOWN"] is None:
        raise RobotApiError(f"Position 'DOWN' is missing or null in {positions_path}.")
    return validate_position(positions["DOWN"])


def main() -> int:
    args = parse_args()
    if args.pause < 0 or args.pause > 10:
        print("--pause must be between 0 and 10 seconds.")
        return 1
    if not CONFIG_PATH.exists():
        print("Missing config.json. Copy config.example.json to config.json and edit robot_port.")
        return 1

    robot = None
    try:
        config = load_json(CONFIG_PATH)
        down_pose = load_down_pose(config)
        if GRIPPER_JOINT not in down_pose:
            raise RobotApiError(f"DOWN pose is missing {GRIPPER_JOINT}.")

        speed_scale = args.speed_scale if args.speed_scale is not None else config.get("speed_scale", DEFAULT_SPEED_SCALE)
        print("Grip and down")
        print(f"grip_value={args.grip_value}, pause={args.pause}, speed_scale={speed_scale}")
        print("Steps:")
        print(f"  1. Set current {GRIPPER_JOINT} to {args.grip_value}")
        print("  2. Move to DOWN with the same gripper value")

        if args.dry_run:
            print("Dry run only. No robot connection or movement will happen.")
            return 0

        if not args.yes:
            input("Press Enter to grip and move down, or Ctrl+C to cancel.")

        print(f"Connecting to SO-101 follower on {config.get('robot_port')}...")
        robot = connect_robot(config)
        print("Robot connected.")

        current_pose = read_current_position(robot)
        grip_pose = dict(current_pose)
        grip_pose[GRIPPER_JOINT] = args.grip_value

        down_with_grip = dict(down_pose)
        down_with_grip[GRIPPER_JOINT] = args.grip_value

        print("Gripping at current position.")
        move_to_position(robot, grip_pose, speed_scale)
        time.sleep(args.pause)

        print("Moving to DOWN.")
        move_to_position(robot, down_with_grip, speed_scale)

        print("Grip and down complete.")
        return 0
    except KeyboardInterrupt:
        print("\nCtrl+C received. Stopping robot now.")
        stop_robot(robot)
        return 130
    except Exception as exc:
        print(f"Grip and down failed: {exc}")
        return 1
    finally:
        disconnect_robot(robot)
        print("Disconnected.")


if __name__ == "__main__":
    raise SystemExit(main())
