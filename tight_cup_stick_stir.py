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
GRIPPER_JOINT = "gripper.pos"

CUP_SEQUENCE = (
    ("CUP_APPROACH", "open"),
    ("CUP_GRASP", "tight"),
    ("CUP_LIFT", "tight"),
    ("CUP_POUR", "tight"),
    ("CUP_LIFT", "tight"),
    ("CUP_PLACE", "tight"),
    ("CUP_RELEASE", "open"),
)

STICK_SEQUENCE = (
    ("STIRRER_APPROACH", "open"),
    ("STIRRER_GRASP", "tight"),
    ("STIRRER_LIFT", "tight"),
    ("STIRRER_READY", "tight"),
)

STIR_SEQUENCE = (
    "STIR_FORWARD",
    "STIR_BACK",
    "STIR_LEFT",
    "STIR_RIGHT",
)

FINISH_SEQUENCE = (
    "LIFT",
    "PARK",
)


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pick ingredient cup, pick spoon/stirrer stick with tight grip, then stir."
    )
    parser.add_argument("--speed-scale", type=float, default=None)
    parser.add_argument("--pause", type=float, default=0.3)
    parser.add_argument("--stir-cycles", type=int, default=5)
    parser.add_argument(
        "--grip-value",
        type=float,
        default=-5.0,
        help="Tight gripper.pos value. Lower is tighter on this setup.",
    )
    parser.add_argument(
        "--open-value",
        type=float,
        default=30.0,
        help="Loose/open gripper.pos value for approach and release.",
    )
    parser.add_argument("--release-at-end", action="store_true", help="Open gripper after PARK.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    return parser.parse_args()


def load_positions(config: dict, names: set[str]) -> dict[str, dict[str, float]]:
    positions_path = Path(config.get("positions_file", "positions.json"))
    raw_positions = load_json(positions_path)
    positions: dict[str, dict[str, float]] = {}
    for name in sorted(names):
        if name not in raw_positions or raw_positions[name] is None:
            raise RobotApiError(f"Position {name!r} is missing or null in {positions_path}.")
        positions[name] = validate_position(raw_positions[name])
    return positions


def with_gripper(position: dict[str, float], value: float) -> dict[str, float]:
    adjusted = dict(position)
    adjusted[GRIPPER_JOINT] = value
    return adjusted


def main() -> int:
    args = parse_args()
    if args.pause < 0 or args.pause > 10:
        print("--pause must be between 0 and 10 seconds.")
        return 1
    if args.stir_cycles < 1 or args.stir_cycles > 30:
        print("--stir-cycles must be between 1 and 30.")
        return 1
    if not CONFIG_PATH.exists():
        print("Missing config.json. Copy config.example.json to config.json and edit robot_port.")
        return 1

    robot = None
    try:
        config = load_json(CONFIG_PATH)
        needed = {
            name
            for name, _ in CUP_SEQUENCE + STICK_SEQUENCE
        } | set(STIR_SEQUENCE) | set(FINISH_SEQUENCE)
        positions = load_positions(config, needed)
        speed_scale = args.speed_scale if args.speed_scale is not None else config.get("speed_scale", DEFAULT_SPEED_SCALE)

        plan: list[tuple[str, float]] = []
        for name, grip_mode in CUP_SEQUENCE:
            plan.append((name, args.grip_value if grip_mode == "tight" else args.open_value))
        for name, grip_mode in STICK_SEQUENCE:
            plan.append((name, args.grip_value if grip_mode == "tight" else args.open_value))
        for _ in range(args.stir_cycles):
            for name in STIR_SEQUENCE:
                plan.append((name, args.grip_value))
        for name in FINISH_SEQUENCE:
            plan.append((name, args.grip_value))
        if args.release_at_end:
            plan.append(("PARK", args.open_value))

        print("Tight cup + stick/stirrer full sequence")
        print(
            f"speed_scale={speed_scale}, pause={args.pause}, stir_cycles={args.stir_cycles}, "
            f"grip_value={args.grip_value}, open_value={args.open_value}"
        )
        print("Plan:")
        for name, grip_value in plan:
            print(f"  {name} with {GRIPPER_JOINT}={grip_value}")

        if args.dry_run:
            print("Dry run only. No robot connection or movement will happen.")
            return 0

        if not args.yes:
            input("Press Enter to run the full tight-grip sequence, or Ctrl+C to cancel.")

        print(f"Connecting to SO-101 follower on {config.get('robot_port')}...")
        robot = connect_robot(config)
        print("Robot connected.")

        for name, grip_value in plan:
            print(f"Moving to {name} with {GRIPPER_JOINT}={grip_value}")
            move_to_position(robot, with_gripper(positions[name], grip_value), speed_scale)
            time.sleep(args.pause)

        print("Full tight-grip cup + stick/stirrer sequence complete.")
        return 0
    except KeyboardInterrupt:
        print("\nCtrl+C received. Stopping robot now.")
        stop_robot(robot)
        return 130
    except Exception as exc:
        print(f"Full tight-grip sequence failed: {exc}")
        return 1
    finally:
        disconnect_robot(robot)
        print("Disconnected.")


if __name__ == "__main__":
    raise SystemExit(main())
