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
DEFAULT_SEQUENCE = ["HOME", "ABOVE_BOWL", "STIR_DEPTH", "LIFT", "PARK"]


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay saved SO-101 follower positions slowly.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print steps without moving.")
    parser.add_argument("--yes", action="store_true", help="Do not wait for Enter before movement.")
    parser.add_argument("--sequence", nargs="+", default=DEFAULT_SEQUENCE, help="Named positions to replay.")
    return parser.parse_args()


def load_and_validate_sequence(config: dict, sequence: list[str]) -> dict[str, dict[str, float]]:
    positions_path = Path(config.get("positions_file", "positions.json"))
    positions = load_json(positions_path)
    selected: dict[str, dict[str, float]] = {}
    for name in sequence:
        if name not in positions:
            raise RobotApiError(f"Position {name!r} is not in {positions_path}.")
        if positions[name] is None:
            raise RobotApiError(f"Position {name!r} is null. Save it before replay.")
        selected[name] = validate_position(positions[name])
    return selected


def main() -> int:
    args = parse_args()
    if not CONFIG_PATH.exists():
        raise SystemExit("Missing config.json. Copy config.example.json to config.json and edit robot_port.")

    robot = None
    try:
        config = load_json(CONFIG_PATH)
        speed_scale = config.get("speed_scale", DEFAULT_SPEED_SCALE)
        move_delay_seconds = float(config.get("move_delay_seconds", 2.0))
        selected = load_and_validate_sequence(config, args.sequence)

        print("Replay sequence:")
        for name in args.sequence:
            print(f"  {name}")
        print(f"speed_scale={speed_scale}")
        print("Keep hand near power switch. Make sure the bowl area is empty. Press Ctrl+C to stop.")

        if args.dry_run:
            print("Dry run only. No robot connection or movement will happen.")
            for name in args.sequence:
                print(f"Moving to {name}")
            return 0

        if not args.yes:
            input("Press Enter to start movement, or Ctrl+C to cancel.")

        print(f"Connecting to SO-101 follower on {config.get('robot_port')}...")
        robot = connect_robot(config)
        print("Robot connected. Starting slow replay.")

        for name in args.sequence:
            print(f"Moving to {name}")
            move_to_position(robot, selected[name], speed_scale)
            time.sleep(move_delay_seconds)

        print("Replay complete.")
        return 0
    except KeyboardInterrupt:
        print("\nCtrl+C received. Stopping robot now.")
        stop_robot(robot)
        return 130
    except Exception as exc:
        print(f"Replay failed: {exc}")
        return 1
    finally:
        disconnect_robot(robot)
        print("Disconnected.")


if __name__ == "__main__":
    raise SystemExit(main())
