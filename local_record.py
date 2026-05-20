from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from camera_runtime import BackgroundCameraSet, choose_cameras, log_rerun_text, start_rerun
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
    parser.add_argument("--camera-mode", choices=["ask", "yes", "no"], default="ask")
    parser.add_argument("--camera-fps", type=float, default=30.0)
    parser.add_argument("--camera-width", type=int, default=640)
    parser.add_argument("--camera-height", type=int, default=480)
    parser.add_argument("--camera-save-dir", default="recordings/latest/cameras")
    parser.add_argument("--rerun", action="store_true", help="Stream camera frames and robot data to Rerun.")
    parser.add_argument("--rerun-spawn", action="store_true", help="Compatibility option. --rerun opens the viewer by default.")
    parser.add_argument("--no-rerun-spawn", action="store_true", help="Log to Rerun without opening the viewer.")
    parser.add_argument("--rerun-every", type=int, default=5, help="Log every N camera/record frames to Rerun.")
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
    cameras = None
    rr = None
    try:
        config = load_json(CONFIG_PATH)
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Recording follower poses to {out_path}")
        print(f"seconds={args.seconds}, fps={args.fps}")
        configured_cameras = [int(index) for index in config.get("camera_indices", [0])]
        camera_indices = choose_cameras(args.camera_mode, configured_cameras, args.camera_width, args.camera_height)
        if not args.yes:
            input("Press Enter to connect and record, or Ctrl+C to cancel.")
        if args.rerun:
            rr = start_rerun("pbl_so101_record", spawn=not args.no_rerun_spawn)
        cameras = BackgroundCameraSet(
            camera_indices,
            args.camera_width,
            args.camera_height,
            args.camera_fps,
            Path(args.camera_save_dir) if camera_indices else None,
            rerun=rr,
            rerun_every=args.rerun_every,
        )
        cameras.start()
        robot = connect_robot(config)
        start = time.time()
        interval = 1.0 / args.fps
        count = 0
        with out_path.open("w", encoding="utf-8") as f:
            while time.time() - start < args.seconds:
                timestamp = time.time()
                position = read_current_position(robot)
                camera_state = cameras.snapshot() if cameras is not None else {}
                f.write(json.dumps({"t": timestamp, "position": position, "camera_state": camera_state}) + "\n")
                if rr is not None and count % max(1, args.rerun_every) == 0:
                    log_rerun_text(rr, "robot/position", {"t": timestamp, "position": position})
                    log_rerun_text(rr, "robot/camera_state", camera_state)
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
        if cameras is not None:
            cameras.stop()
        print("Disconnected.")


if __name__ == "__main__":
    raise SystemExit(main())
