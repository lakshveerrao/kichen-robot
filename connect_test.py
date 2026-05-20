from __future__ import annotations

import json
from pathlib import Path

from robot_api import RobotApiError, connect_robot, disconnect_robot, read_current_position


CONFIG_PATH = Path("config.json")


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise SystemExit("Missing config.json. Copy config.example.json to config.json and edit robot_port.")
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    robot = None
    try:
        config = load_config()
        print(f"Connecting to SO-101 follower on {config.get('robot_port')}...")
        robot = connect_robot(config)
        print("SUCCESS: robot connected.")
        try:
            position = read_current_position(robot)
            print("Current joint positions:")
            for key, value in position.items():
                print(f"  {key}: {value}")
        except Exception as exc:
            print(f"Connected, but could not read joint positions: {exc}")
        return 0
    except (RobotApiError, Exception) as exc:
        print(f"FAILURE: {exc}")
        return 1
    finally:
        disconnect_robot(robot)
        print("Disconnected.")


if __name__ == "__main__":
    raise SystemExit(main())
