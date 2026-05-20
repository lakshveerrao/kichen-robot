from __future__ import annotations

import argparse
import json
from pathlib import Path

from robot_api import connect_robot, disconnect_robot, read_current_position


CONFIG_PATH = Path("config.json")
DEFAULT_POSITION_NAMES = {
    "HOME",
    "ABOVE_BOWL",
    "STIR_DEPTH",
    "LIFT",
    "PARK",
    "UP",
    "DOWN",
    "LEFT",
    "RIGHT",
    "STIR_FORWARD",
    "STIR_BACK",
    "STIR_LEFT",
    "STIR_RIGHT",
    "CUP_APPROACH",
    "CUP_GRASP",
    "CUP_LIFT",
    "CUP_POUR",
    "CUP_PLACE",
    "CUP_RELEASE",
    "STIRRER_APPROACH",
    "STIRRER_GRASP",
    "STIRRER_LIFT",
    "STIRRER_READY",
}


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Save the current SO-101 joint position.")
    parser.add_argument("name", help="Position name, for example HOME or ABOVE_BOWL.")
    parser.add_argument("--force", action="store_true", help="Allow saving a new unknown position name.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not CONFIG_PATH.exists():
        raise SystemExit("Missing config.json. Copy config.example.json to config.json and edit robot_port.")

    config = load_json(CONFIG_PATH)
    positions_path = Path(config.get("positions_file", "positions.json"))
    positions = load_json(positions_path) if positions_path.exists() else {}

    if args.name not in positions and args.name not in DEFAULT_POSITION_NAMES and not args.force:
        print(f"Refusing unknown position name {args.name!r}. Use --force to create it.")
        return 1

    robot = None
    try:
        print(f"Connecting to SO-101 follower on {config.get('robot_port')}...")
        robot = connect_robot(config)
        position = read_current_position(robot)
        positions[args.name] = position
        save_json(positions_path, positions)
        print(f"Saved {args.name} to {positions_path}:")
        for key, value in position.items():
            print(f"  {key}: {value}")
        return 0
    except Exception as exc:
        print(f"Failed to save position: {exc}")
        return 1
    finally:
        disconnect_robot(robot)
        print("Disconnected.")


if __name__ == "__main__":
    raise SystemExit(main())
