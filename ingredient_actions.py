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
    stop_robot,
    validate_position,
)


CONFIG_PATH = Path("config.json")
ACTIONS = {
    "cup": ("CUP_APPROACH", "CUP_GRASP", "CUP_LIFT", "CUP_POUR", "CUP_LIFT", "CUP_PLACE", "CUP_RELEASE"),
    "stirrer": ("STIRRER_APPROACH", "STIRRER_GRASP", "STIRRER_LIFT", "STIRRER_READY"),
    "all": (
        "CUP_APPROACH",
        "CUP_GRASP",
        "CUP_LIFT",
        "CUP_POUR",
        "CUP_LIFT",
        "CUP_PLACE",
        "CUP_RELEASE",
        "STIRRER_APPROACH",
        "STIRRER_GRASP",
        "STIRRER_LIFT",
        "STIRRER_READY",
    ),
}


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay calibrated cup and side-stirrer pickup actions.")
    parser.add_argument("--action", choices=sorted(ACTIONS), required=True)
    parser.add_argument("--pause", type=float, default=0.4)
    parser.add_argument("--speed-scale", type=float, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    return parser.parse_args()


def load_action_poses(config: dict, pose_names: tuple[str, ...]) -> dict[str, dict[str, float]]:
    positions_path = Path(config.get("positions_file", "positions.json"))
    positions = load_json(positions_path)
    selected: dict[str, dict[str, float]] = {}
    for name in pose_names:
        if name in selected:
            continue
        if name not in positions or positions[name] is None:
            raise RobotApiError(f"Position {name!r} is missing or null in {positions_path}.")
        selected[name] = validate_position(positions[name])
    return selected


def main() -> int:
    args = parse_args()
    if args.pause < 0 or args.pause > 10:
        print("--pause must be between 0 and 10 seconds.")
        return 1
    if not CONFIG_PATH.exists():
        print("Missing config.json.")
        return 1

    robot = None
    try:
        config = load_json(CONFIG_PATH)
        pose_names = ACTIONS[args.action]
        poses = {} if args.dry_run else load_action_poses(config, pose_names)
        speed_scale = args.speed_scale if args.speed_scale is not None else config.get("speed_scale", DEFAULT_SPEED_SCALE)

        print(f"Ingredient action: {args.action}")
        print(f"speed_scale={speed_scale}, pause={args.pause}")
        print("Keep hand near power switch. Press Ctrl+C to stop.")
        for name in pose_names:
            print(f"  {name}")

        if args.dry_run:
            print("Dry run only. No movement will happen.")
            return 0

        if not args.yes:
            input("Press Enter to start ingredient action, or Ctrl+C to cancel.")

        print(f"Connecting to SO-101 follower on {config.get('robot_port')}...")
        robot = connect_robot(config)
        print("Robot connected.")

        for name in pose_names:
            print(f"Moving to {name}")
            move_to_position(robot, poses[name], speed_scale)
            time.sleep(args.pause)

        print("Ingredient action complete.")
        return 0
    except KeyboardInterrupt:
        print("\nStop requested. Stopping robot now.")
        stop_robot(robot)
        return 130
    except Exception as exc:
        print(f"Ingredient action failed: {exc}")
        return 1
    finally:
        disconnect_robot(robot)
        print("Disconnected.")


if __name__ == "__main__":
    raise SystemExit(main())
