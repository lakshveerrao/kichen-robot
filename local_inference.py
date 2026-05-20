from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from robot_api import DEFAULT_SPEED_SCALE, connect_robot, disconnect_robot, move_to_position, stop_robot, validate_position


CONFIG_PATH = Path("config.json")


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay a locally trained pose-sequence policy.")
    parser.add_argument("--policy", default="models/latest_policy.json")
    parser.add_argument("--speed-scale", type=float, default=None)
    parser.add_argument("--pause", type=float, default=0.05)
    parser.add_argument("--max-steps", type=int, default=None)
    parser.add_argument("--yes", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    policy_path = Path(args.policy)
    if not policy_path.exists():
        print(f"Missing policy: {policy_path}")
        return 1
    if args.pause < 0 or args.pause > 5:
        print("--pause must be between 0 and 5.")
        return 1
    if not CONFIG_PATH.exists():
        print("Missing config.json.")
        return 1

    robot = None
    try:
        config = load_json(CONFIG_PATH)
        policy = load_json(policy_path)
        positions = [validate_position(position) for position in policy.get("positions", [])]
        if args.max_steps is not None:
            positions = positions[: args.max_steps]
        if not positions:
            print("Policy has no positions.")
            return 1
        speed_scale = args.speed_scale if args.speed_scale is not None else config.get("speed_scale", DEFAULT_SPEED_SCALE)
        print(f"Replaying policy {policy_path}")
        print(f"poses={len(positions)}, speed_scale={speed_scale}, pause={args.pause}")
        if not args.yes:
            input("Press Enter to connect and replay policy, or Ctrl+C to cancel.")
        robot = connect_robot(config)
        for index, position in enumerate(positions, start=1):
            print(f"Policy step {index}/{len(positions)}")
            move_to_position(robot, position, speed_scale)
            time.sleep(args.pause)
        print("Policy replay complete.")
        return 0
    except KeyboardInterrupt:
        print("\nStop requested.")
        stop_robot(robot)
        return 130
    except Exception as exc:
        print(f"Inference failed: {exc}")
        return 1
    finally:
        disconnect_robot(robot)
        print("Disconnected.")


if __name__ == "__main__":
    raise SystemExit(main())
