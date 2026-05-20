from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from camera_runtime import BackgroundCameraSet, choose_cameras, log_rerun_text, start_rerun


CONFIG_PATH = Path("config.json")


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local SO-101 leader-to-follower teleoperation without Solo CLI.")
    parser.add_argument("--leader-port", default=None, help="Leader arm port, for example COM8.")
    parser.add_argument("--follower-port", default=None, help="Follower arm port, for example COM7.")
    parser.add_argument("--leader-id", default=None, help="Leader calibration id.")
    parser.add_argument("--follower-id", default=None, help="Follower calibration id.")
    parser.add_argument("--fps", type=float, default=60.0)
    parser.add_argument("--camera-mode", choices=["ask", "yes", "no"], default="ask")
    parser.add_argument("--camera-fps", type=float, default=30.0)
    parser.add_argument("--camera-width", type=int, default=640)
    parser.add_argument("--camera-height", type=int, default=480)
    parser.add_argument("--camera-save-dir", default=None)
    parser.add_argument("--rerun", action="store_true", help="Stream camera frames and robot data to Rerun.")
    parser.add_argument("--rerun-spawn", action="store_true", help="Compatibility option. --rerun opens the viewer by default.")
    parser.add_argument("--no-rerun-spawn", action="store_true", help="Log to Rerun without opening the viewer.")
    parser.add_argument("--rerun-every", type=int, default=5, help="Log every N camera/control frames to Rerun.")
    parser.add_argument("--max-relative-target", type=float, default=5.0)
    parser.add_argument("--yes", action="store_true")
    return parser.parse_args()


def import_lerobot_classes() -> tuple[Any, Any, Any, Any]:
    try:
        from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig
        from lerobot.teleoperators.so_leader import SO101Leader, SO101LeaderConfig
    except ImportError as exc:
        raise RuntimeError("Could not import SO-101 leader/follower classes from LeRobot.") from exc
    return SO101Leader, SO101LeaderConfig, SO101Follower, SO101FollowerConfig


def add_write_retries(device: Any) -> None:
    bus = getattr(device, "bus", None)
    original_write = getattr(bus, "write", None)
    if not callable(original_write):
        return

    def write_with_retry(*args: Any, **kwargs: Any):
        kwargs["num_retry"] = max(int(kwargs.get("num_retry", 1)), 5)
        return original_write(*args, **kwargs)

    bus.write = write_with_retry


def main() -> int:
    args = parse_args()
    if args.fps <= 0 or args.fps > 120:
        print("--fps must be > 0 and <= 120.")
        return 1
    if args.max_relative_target <= 0 or args.max_relative_target > 30:
        print("--max-relative-target must be > 0 and <= 30.")
        return 1
    if not CONFIG_PATH.exists():
        print("Missing config.json. Run: pbl setup --port COM7 --leader-port COM8")
        return 1

    leader = None
    follower = None
    cameras = None
    rr = None
    try:
        config = load_json(CONFIG_PATH)
        leader_port = args.leader_port or config.get("leader_port") or "COM8"
        follower_port = args.follower_port or config.get("robot_port") or config.get("follower_port") or "COM7"
        leader_id = args.leader_id or config.get("leader_id") or "1"
        follower_id = args.follower_id or config.get("follower_id") or config.get("robot_id") or "kitchen_stirrer_follower"

        SO101Leader, SO101LeaderConfig, SO101Follower, SO101FollowerConfig = import_lerobot_classes()
        print("PBL local teleop. No Solo CLI required.")
        print(f"leader_port={leader_port}, follower_port={follower_port}")
        print(f"leader_id={leader_id}, follower_id={follower_id}, fps={args.fps}")
        print("Move the leader arm to control the follower arm. Press Ctrl+C to stop.")
        configured_cameras = [int(index) for index in config.get("camera_indices", [0])]
        camera_indices = choose_cameras(args.camera_mode, configured_cameras, args.camera_width, args.camera_height)
        if not args.yes:
            input("Press Enter to connect teleop, or Ctrl+C to cancel.")

        if args.rerun:
            rr = start_rerun("pbl_so101_teleop", spawn=not args.no_rerun_spawn)
        cameras = BackgroundCameraSet(
            camera_indices,
            args.camera_width,
            args.camera_height,
            args.camera_fps,
            Path(args.camera_save_dir) if args.camera_save_dir else None,
            rerun=rr,
            rerun_every=args.rerun_every,
        )
        cameras.start()
        if camera_indices:
            print(f"Camera capture running in background: {camera_indices}")

        leader = SO101Leader(SO101LeaderConfig(port=leader_port, id=str(leader_id)))
        follower = SO101Follower(
            SO101FollowerConfig(
                port=follower_port,
                id=str(follower_id),
                max_relative_target=args.max_relative_target,
                cameras={},
            )
        )
        add_write_retries(leader)
        add_write_retries(follower)

        leader.connect()
        follower.connect()
        print("Leader and follower connected. Starting teleop.")

        interval = 1.0 / args.fps
        next_print = time.time()
        frame_count = 0
        while True:
            started = time.perf_counter()
            action = leader.get_action()
            follower.send_action(action)
            frame_count += 1
            now = time.time()
            if rr is not None and frame_count % max(1, args.rerun_every) == 0:
                log_rerun_text(rr, "robot/action", action)
            if now >= next_print:
                camera_state = cameras.snapshot() if cameras is not None else {}
                print(f"Teleop running. Press Ctrl+C to stop. cameras={camera_state}")
                log_rerun_text(rr, "robot/status", {"mode": "teleop", "fps": args.fps, "cameras": camera_state})
                next_print = now + 5.0
            elapsed = time.perf_counter() - started
            sleep_time = interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
    except KeyboardInterrupt:
        print("\nTeleop stopped by user.")
        return 0
    except Exception as exc:
        print(f"Local teleop failed: {exc}")
        return 1
    finally:
        for device, name in ((leader, "leader"), (follower, "follower")):
            if device is None:
                continue
            try:
                if not hasattr(device, "is_connected") or device.is_connected:
                    device.disconnect()
                    print(f"{name} disconnected.")
            except Exception as exc:
                print(f"Warning: {name} disconnect failed: {exc}")
        if cameras is not None:
            cameras.stop()


if __name__ == "__main__":
    raise SystemExit(main())
