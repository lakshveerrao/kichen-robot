from __future__ import annotations

import argparse
import json
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


HELP_TEXT = """
Manual commands:
  a  pan left
  d  pan right
  w  wrist forward
  s  wrist back
  r  lift up
  f  lift down
  c  return to start center
  p  stop/relax now
  q  quit
"""


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manual SO-101 relative movement control.")
    parser.add_argument("--pan-deg", type=float, default=5.0)
    parser.add_argument("--wrist-deg", type=float, default=5.0)
    parser.add_argument("--lift-deg", type=float, default=2.0)
    parser.add_argument("--speed-scale", type=float, default=None)
    parser.add_argument("--yes", action="store_true", help="Do not wait for Enter before connecting.")
    parser.add_argument("--hold-at-end", action="store_true", help="Keep torque on at exit instead of stopping.")
    return parser.parse_args()


def apply_delta(current: dict[str, float], key: str, delta: float) -> dict[str, float]:
    target = dict(current)
    target[key] = target[key] + delta
    return target


def main() -> int:
    args = parse_args()
    if args.pan_deg <= 0 or args.pan_deg > 45:
        print("--pan-deg must be > 0 and <= 45.")
        return 1
    if args.wrist_deg <= 0 or args.wrist_deg > 45:
        print("--wrist-deg must be > 0 and <= 45.")
        return 1
    if args.lift_deg <= 0 or args.lift_deg > 15:
        print("--lift-deg must be > 0 and <= 15.")
        return 1
    if not CONFIG_PATH.exists():
        print("Missing config.json.")
        return 1

    robot = None
    try:
        config = load_json(CONFIG_PATH)
        speed_scale = args.speed_scale if args.speed_scale is not None else config.get("speed_scale", DEFAULT_SPEED_SCALE)

        print("Manual SO-101 control. No ChatGPT, no cameras, no auto decisions.")
        print("Keep hand near power switch. Type p to stop/relax, q to quit.")
        print(f"pan={args.pan_deg}, wrist={args.wrist_deg}, lift={args.lift_deg}, speed_scale={speed_scale}")
        if not args.yes:
            input("Press Enter to connect, or Ctrl+C to cancel.")

        print(f"Connecting to SO-101 follower on {config.get('robot_port')}...")
        robot = connect_robot(config)
        current = read_current_position(robot)
        center = dict(current)
        print("Robot connected. Start center captured.")
        print(HELP_TEXT)

        while True:
            command = input("manual> ").strip().lower()
            if command == "":
                continue
            if command == "h":
                print(HELP_TEXT)
                continue
            if command == "q":
                print("Quit requested.")
                break
            if command == "p":
                print("Stopping/relaxing robot now.")
                stop_robot(robot)
                current = read_current_position(robot)
                continue
            if command == "c":
                print("Returning to start center.")
                move_to_position(robot, center, speed_scale)
                current = dict(center)
                continue

            moves = {
                "a": ("shoulder_pan.pos", -args.pan_deg, "pan left"),
                "d": ("shoulder_pan.pos", args.pan_deg, "pan right"),
                "w": ("wrist_flex.pos", -args.wrist_deg, "wrist forward"),
                "s": ("wrist_flex.pos", args.wrist_deg, "wrist back"),
                "r": ("shoulder_lift.pos", args.lift_deg, "lift up"),
                "f": ("shoulder_lift.pos", -args.lift_deg, "lift down"),
            }
            if command not in moves:
                print("Unknown command. Type h for help.")
                continue

            key, delta, label = moves[command]
            print(f"Moving {label}")
            target = apply_delta(current, key, delta)
            move_to_position(robot, target, speed_scale)
            current = read_current_position(robot)

        if not args.hold_at_end:
            print("Stopping robot at end.")
            stop_robot(robot)
        return 0
    except KeyboardInterrupt:
        print("\nCtrl+C received. Stopping robot now.")
        stop_robot(robot)
        return 130
    except Exception as exc:
        print(f"Manual control failed: {exc}")
        return 1
    finally:
        disconnect_robot(robot)
        print("Disconnected.")


if __name__ == "__main__":
    raise SystemExit(main())
