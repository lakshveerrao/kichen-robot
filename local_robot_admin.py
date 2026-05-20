from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


CONFIG_PATH = Path("config.json")


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local SO-101 motor setup and calibration without Solo CLI.")
    parser.add_argument("--action", choices=["setup-motors", "calibrate"], required=True)
    parser.add_argument("--device", choices=["leader", "follower", "all"], required=True)
    parser.add_argument("--robot-type", choices=["auto", "so101"], default="auto")
    parser.add_argument("--leader-port", default=None)
    parser.add_argument("--follower-port", default=None)
    parser.add_argument("--leader-id", default=None)
    parser.add_argument("--follower-id", default=None)
    parser.add_argument("--yes", action="store_true")
    return parser.parse_args()


def import_lerobot_classes() -> tuple[Any, Any, Any, Any]:
    try:
        from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig
        from lerobot.teleoperators.so_leader import SO101Leader, SO101LeaderConfig
    except ImportError as exc:
        raise RuntimeError("Could not import SO-101 leader/follower classes from LeRobot.") from exc
    return SO101Leader, SO101LeaderConfig, SO101Follower, SO101FollowerConfig


def selected_devices(device: str) -> tuple[str, ...]:
    if device == "all":
        return ("leader", "follower")
    return (device,)


def main() -> int:
    args = parse_args()
    if not CONFIG_PATH.exists():
        print("Missing config.json. Run: pbl setup --port COM7 --leader-port COM8")
        return 1

    try:
        config = load_json(CONFIG_PATH)
        robot_type = "so101" if args.robot_type == "auto" else args.robot_type
        leader_port = args.leader_port or config.get("leader_port") or "COM8"
        follower_port = args.follower_port or config.get("robot_port") or config.get("follower_port") or "COM7"
        leader_id = args.leader_id or config.get("leader_id") or "1"
        follower_id = args.follower_id or config.get("follower_id") or config.get("robot_id") or "kitchen_stirrer_follower"
        SO101Leader, SO101LeaderConfig, SO101Follower, SO101FollowerConfig = import_lerobot_classes()

        print("PBL local robot admin. No Solo CLI required.")
        print(f"Auto-detected robot type: {robot_type.upper()}")
        print(f"action={args.action}, device={args.device}")
        print(f"leader_port={leader_port}, leader_id={leader_id}")
        print(f"follower_port={follower_port}, follower_id={follower_id}")

        if args.action == "setup-motors":
            print()
            print("Motor ID setup changes servo IDs.")
            print("LeRobot will ask you to connect only one motor at a time.")
            print("Follow the prompt exactly before pressing Enter.")
        else:
            print()
            print("Calibration records joint ranges.")
            print("Move joints through their full safe ranges when LeRobot asks.")

        if not args.yes:
            input("Press Enter to continue, or Ctrl+C to cancel.")

        for device in selected_devices(args.device):
            if device == "leader":
                robot = SO101Leader(SO101LeaderConfig(port=leader_port, id=str(leader_id)))
                label = "leader"
            else:
                robot = SO101Follower(
                    SO101FollowerConfig(
                        port=follower_port,
                        id=str(follower_id),
                        max_relative_target=5.0,
                        cameras={},
                    )
                )
                label = "follower"

            print(f"Starting {args.action} for {label}.")
            try:
                if args.action == "setup-motors":
                    robot.setup_motors()
                else:
                    robot.connect(calibrate=False)
                    robot.calibrate()
                print(f"{label} {args.action} complete.")
            finally:
                try:
                    if hasattr(robot, "is_connected") and robot.is_connected:
                        robot.disconnect()
                except Exception as exc:
                    print(f"Warning: could not disconnect {label}: {exc}")

        print("Robot admin action complete.")
        return 0
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 130
    except Exception as exc:
        print(f"Robot admin failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
