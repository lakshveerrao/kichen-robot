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


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a calibrated named-pose action sequence.")
    parser.add_argument("--sequence", nargs="+", required=True, help="Position names to execute in order.")
    parser.add_argument("--speed-scale", type=float, default=None)
    parser.add_argument("--pause", type=float, default=0.4)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    return parser.parse_args()


def load_poses(config: dict, sequence: list[str]) -> dict[str, dict[str, float]]:
    positions_path = Path(config.get("positions_file", "positions.json"))
    positions = load_json(positions_path)
    selected: dict[str, dict[str, float]] = {}
    missing = []
    for name in sequence:
        if name in selected:
            continue
        if name not in positions or positions[name] is None:
            missing.append(name)
        else:
            selected[name] = validate_position(positions[name])
    if missing:
        raise RobotApiError(
            "Missing calibrated poses: "
            + ", ".join(missing)
            + f". Save them first with: pbl save-pose NAME --force"
        )
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
        speed_scale = args.speed_scale if args.speed_scale is not None else config.get("speed_scale", DEFAULT_SPEED_SCALE)
        print("Generic pose action:")
        for name in args.sequence:
            print(f"  {name}")
        print(f"speed_scale={speed_scale}, pause={args.pause}")
        if args.dry_run:
            load_poses(config, args.sequence)
            print("Dry run only. Poses exist and no robot movement happened.")
            return 0
        if not args.yes:
            input("Press Enter to start pose action, or Ctrl+C to cancel.")
        poses = load_poses(config, args.sequence)
        robot = connect_robot(config)
        for name in args.sequence:
            print(f"Moving to {name}")
            move_to_position(robot, poses[name], speed_scale)
            time.sleep(args.pause)
        print("Generic pose action complete.")
        return 0
    except KeyboardInterrupt:
        print("\nStop requested. Stopping robot now.")
        stop_robot(robot)
        return 130
    except Exception as exc:
        print(f"Generic pose action failed: {exc}")
        return 1
    finally:
        disconnect_robot(robot)
        print("Disconnected.")


if __name__ == "__main__":
    raise SystemExit(main())
