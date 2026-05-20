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

PLAN = (
    ("CUP_APPROACH", "open", "approach cup"),
    ("CUP_GRASP", "tight", "grasp cup"),
    ("CUP_LIFT", "tight", "lift cup"),
    ("CUP_POUR", "tight", "pour cup"),
    ("CUP_LIFT", "tight", "lift cup back"),
    ("CUP_PLACE", "tight", "place cup"),
    ("CUP_RELEASE", "open", "release cup"),
    ("STIRRER_APPROACH", "open", "approach stick"),
    ("STIRRER_GRASP", "tight", "grasp stick"),
    ("STIRRER_LIFT", "tight", "lift stick"),
    ("STIRRER_READY", "tight", "ready to stir"),
)

STIR_POSES = ("STIR_FORWARD", "STIR_BACK", "STIR_LEFT", "STIR_RIGHT")
FINISH_POSES = ("LIFT", "PARK")


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smart full upma helper: cup pickup, stick pickup, tight hold, stir, park."
    )
    parser.add_argument("--speed-scale", type=float, default=None)
    parser.add_argument("--pause", type=float, default=0.25)
    parser.add_argument("--stir-cycles", type=int, default=5)
    parser.add_argument("--tight", type=float, default=-5.0, help="Tight gripper value. Lower is tighter here.")
    parser.add_argument("--open", type=float, default=30.0, help="Open gripper value.")
    parser.add_argument("--release-at-end", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    return parser.parse_args()


def required_pose_names() -> set[str]:
    names = {name for name, _, _ in PLAN}
    names.update(STIR_POSES)
    names.update(FINISH_POSES)
    return names


def load_positions(config: dict) -> dict[str, dict[str, float]]:
    positions_path = Path(config.get("positions_file", "positions.json"))
    raw = load_json(positions_path)
    loaded: dict[str, dict[str, float]] = {}
    missing = []
    for name in sorted(required_pose_names()):
        if name not in raw or raw[name] is None:
            missing.append(name)
        else:
            loaded[name] = validate_position(raw[name])
    if missing:
        raise RobotApiError(f"Missing calibrated poses in {positions_path}: {', '.join(missing)}")
    return loaded


def pose_with_grip(pose: dict[str, float], grip_value: float) -> dict[str, float]:
    updated = dict(pose)
    updated[GRIPPER_JOINT] = grip_value
    return updated


def main() -> int:
    args = parse_args()
    if not CONFIG_PATH.exists():
        print("Missing config.json.")
        return 1
    if args.pause < 0 or args.pause > 10:
        print("--pause must be between 0 and 10.")
        return 1
    if args.stir_cycles < 1 or args.stir_cycles > 30:
        print("--stir-cycles must be between 1 and 30.")
        return 1

    robot = None
    try:
        config = load_json(CONFIG_PATH)
        positions = load_positions(config)
        speed_scale = args.speed_scale if args.speed_scale is not None else config.get("speed_scale", DEFAULT_SPEED_SCALE)

        run_plan: list[tuple[str, float, str]] = []
        for name, grip_mode, label in PLAN:
            run_plan.append((name, args.tight if grip_mode == "tight" else args.open, label))
        for cycle in range(1, args.stir_cycles + 1):
            for name in STIR_POSES:
                run_plan.append((name, args.tight, f"stir cycle {cycle}"))
        for name in FINISH_POSES:
            run_plan.append((name, args.tight, "finish"))
        if args.release_at_end:
            run_plan.append(("PARK", args.open, "release at park"))

        print("Smart upma runner")
        print(f"speed_scale={speed_scale}, pause={args.pause}, tight={args.tight}, open={args.open}")
        for name, grip_value, label in run_plan:
            print(f"  {label}: {name}, {GRIPPER_JOINT}={grip_value}")

        if args.dry_run:
            print("Dry run only. No movement.")
            return 0

        if not args.yes:
            input("Press Enter to run smart upma sequence, or Ctrl+C to cancel.")

        print(f"Connecting to SO-101 follower on {config.get('robot_port')}...")
        robot = connect_robot(config)
        print("Robot connected.")

        for name, grip_value, label in run_plan:
            print(f"{label}: moving to {name} with {GRIPPER_JOINT}={grip_value}")
            move_to_position(robot, pose_with_grip(positions[name], grip_value), speed_scale)
            time.sleep(args.pause)

        print("Smart upma sequence complete.")
        return 0
    except KeyboardInterrupt:
        print("\nCtrl+C received. Stopping robot now.")
        stop_robot(robot)
        return 130
    except Exception as exc:
        print(f"Smart upma runner failed: {exc}")
        return 1
    finally:
        disconnect_robot(robot)
        print("Disconnected.")


if __name__ == "__main__":
    raise SystemExit(main())
