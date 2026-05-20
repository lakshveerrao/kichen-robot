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
MOTIONS = {
    "up-down": (("UP", "STIR_FORWARD"), ("DOWN", "STIR_BACK")),
    "front-back": (("UP", "STIR_FORWARD"), ("DOWN", "STIR_BACK")),
    "left-right": (("LEFT", "STIR_LEFT"), ("RIGHT", "STIR_RIGHT")),
    "clockwise": (("STIR_FORWARD",), ("STIR_RIGHT",), ("STIR_BACK",), ("STIR_LEFT",)),
    "anticlockwise": (("STIR_FORWARD",), ("STIR_LEFT",), ("STIR_BACK",), ("STIR_RIGHT",)),
}


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repeat safe arm-only stirring motions.")
    parser.add_argument(
        "--motion",
        choices=sorted(MOTIONS),
        required=True,
        help="Arm-only stirring pattern to replay.",
    )
    parser.add_argument("--cycles", type=int, default=3, help="Number of stir repeats.")
    parser.add_argument("--pause", type=float, default=0.5, help="Pause between each endpoint.")
    parser.add_argument("--speed-scale", type=float, default=None, help="Override config speed_scale.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print steps without moving.")
    parser.add_argument("--yes", action="store_true", help="Do not wait for Enter before movement.")
    return parser.parse_args()


def load_pose(config: dict, names: tuple[str, ...]) -> tuple[str, dict[str, float]]:
    positions_path = Path(config.get("positions_file", "positions.json"))
    positions = load_json(positions_path)
    for name in names:
        if name in positions and positions[name] is not None:
            return name, validate_position(positions[name])
    expected = " or ".join(names)
    raise RobotApiError(f"Position {expected} is null or missing. Save it before stirring.")


def main() -> int:
    args = parse_args()
    if args.cycles <= 0 or args.cycles > 30:
        print("--cycles must be > 0 and <= 30.")
        return 1
    if not CONFIG_PATH.exists():
        print("Missing config.json. Copy config.example.json to config.json and edit robot_port.")
        return 1

    robot = None
    try:
        config = load_json(CONFIG_PATH)
        waypoint_candidates = MOTIONS[args.motion]
        waypoints = [load_pose(config, names) for names in waypoint_candidates]
        speed_scale = args.speed_scale if args.speed_scale is not None else config.get("speed_scale", DEFAULT_SPEED_SCALE)

        print(f"Stir motion: {args.motion}")
        print("Waypoints:")
        for name, _ in waypoints:
            print(f"  {name}")
        print(f"cycles={args.cycles}, pause={args.pause}, speed_scale={speed_scale}")
        print("Keep hand near power switch. Make sure the bowl area is empty. Press Ctrl+C to stop.")
        print("This controls only the SO-101 arm. It does not control the 360-degree stirring servo.")

        if args.dry_run:
            print("Dry run only. No robot connection or movement will happen.")
            for cycle in range(1, args.cycles + 1):
                for name, _ in waypoints:
                    print(f"Cycle {cycle}: Moving to {name}")
            return 0

        if not args.yes:
            input("Press Enter to start stirring motion, or Ctrl+C to cancel.")

        print(f"Connecting to SO-101 follower on {config.get('robot_port')}...")
        robot = connect_robot(config)
        print("Robot connected. Starting slow stirring motion.")

        for cycle in range(1, args.cycles + 1):
            for name, pose in waypoints:
                print(f"Cycle {cycle}: Moving to {name}")
                move_to_position(robot, pose, speed_scale)
                time.sleep(args.pause)

        print("Stir motion complete.")
        return 0
    except KeyboardInterrupt:
        print("\nCtrl+C received. Stopping robot now.")
        stop_robot(robot)
        return 130
    except Exception as exc:
        print(f"Stir motion failed: {exc}")
        return 1
    finally:
        disconnect_robot(robot)
        print("Disconnected.")


if __name__ == "__main__":
    raise SystemExit(main())
