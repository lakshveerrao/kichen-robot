from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from robot_api import connect_robot, disconnect_robot, read_current_position


CONFIG_PATH = Path("config.json")


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record SO-101 follower joint poses to JSONL.")
    parser.add_argument("--out", default="recordings/latest/observations.jsonl")
    parser.add_argument("--seconds", type=float, default=20.0)
    parser.add_argument("--fps", type=float, default=10.0)
    parser.add_argument("--yes", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.seconds <= 0 or args.seconds > 3600:
        print("--seconds must be > 0 and <= 3600.")
        return 1
    if args.fps <= 0 or args.fps > 60:
        print("--fps must be > 0 and <= 60.")
        return 1
    if not CONFIG_PATH.exists():
        print("Missing config.json.")
        return 1

    robot = None
    try:
        config = load_json(CONFIG_PATH)
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Recording follower poses to {out_path}")
        print(f"seconds={args.seconds}, fps={args.fps}")
        if not args.yes:
            input("Press Enter to connect and record, or Ctrl+C to cancel.")
        robot = connect_robot(config)
        start = time.time()
        interval = 1.0 / args.fps
        count = 0
        with out_path.open("w", encoding="utf-8") as f:
            while time.time() - start < args.seconds:
                timestamp = time.time()
                position = read_current_position(robot)
                f.write(json.dumps({"t": timestamp, "position": position}) + "\n")
                count += 1
                time.sleep(interval)
        print(f"Recorded {count} frames.")
        return 0
    except KeyboardInterrupt:
        print("\nRecording stopped.")
        return 130
    except Exception as exc:
        print(f"Recording failed: {exc}")
        return 1
    finally:
        disconnect_robot(robot)
        print("Disconnected.")


if __name__ == "__main__":
    raise SystemExit(main())
