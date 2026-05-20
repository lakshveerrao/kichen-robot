from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

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
MOTIONS = {
    "front-back": (("UP", "STIR_FORWARD"), ("DOWN", "STIR_BACK")),
    "left-right": (("LEFT", "STIR_LEFT"), ("RIGHT", "STIR_RIGHT")),
}


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rule-based OpenCV automatic arm-only stirring.")
    parser.add_argument("--cameras", nargs="+", type=int, default=None, help="Camera indices to use.")
    parser.add_argument(
        "--motion",
        choices=["auto", "front-back", "left-right"],
        default="auto",
        help="Sweep motion. auto switches pattern when visual activity is low.",
    )
    parser.add_argument("--cycles", type=int, default=6, help="Maximum stir cycles.")
    parser.add_argument("--pause", type=float, default=0.4, help="Pause at each endpoint.")
    parser.add_argument("--speed-scale", type=float, default=None, help="Override config speed_scale.")
    parser.add_argument("--min-change", type=float, default=4.0, help="Low activity threshold for auto switching.")
    parser.add_argument("--roi", nargs=4, type=int, metavar=("X", "Y", "W", "H"), help="Camera ROI in pixels.")
    parser.add_argument("--preview", action="store_true", help="Show camera preview with ROI. Press q to stop.")
    parser.add_argument("--dry-run", action="store_true", help="Use cameras and print decisions without moving robot.")
    parser.add_argument("--yes", action="store_true", help="Do not wait for Enter before movement.")
    parser.add_argument("--no-park", action="store_true", help="Do not move to PARK after the final cycle.")
    return parser.parse_args()


def load_pose(config: dict, names: tuple[str, ...]) -> tuple[str, dict[str, float]]:
    positions_path = Path(config.get("positions_file", "positions.json"))
    positions = load_json(positions_path)
    for name in names:
        if name in positions and positions[name] is not None:
            return name, validate_position(positions[name])
    expected = " or ".join(names)
    raise RobotApiError(f"Position {expected} is null or missing. Save it before auto stirring.")


def open_camera(cv2: Any, index: int, width: int, height: int, fps: int):
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap.release()
        cap = cv2.VideoCapture(index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    if not cap.isOpened():
        cap.release()
        return None
    return cap


def read_gray_roi(cv2: Any, cap: Any, roi: tuple[int, int, int, int] | None):
    ok, frame = cap.read()
    if not ok or frame is None:
        return None, None
    h, w = frame.shape[:2]
    if roi is None:
        margin_x = int(w * 0.2)
        margin_y = int(h * 0.2)
        x, y, rw, rh = margin_x, margin_y, w - 2 * margin_x, h - 2 * margin_y
    else:
        x, y, rw, rh = roi
        x = max(0, min(x, w - 1))
        y = max(0, min(y, h - 1))
        rw = max(1, min(rw, w - x))
        rh = max(1, min(rh, h - y))
    crop = frame[y : y + rh, x : x + rw]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    return gray, (frame, (x, y, rw, rh))


def camera_activity(cv2: Any, cameras: list[tuple[int, Any]], previous: dict[int, Any], roi):
    scores: list[float] = []
    previews = []
    for index, cap in cameras:
        gray, preview = read_gray_roi(cv2, cap, roi)
        if gray is None:
            continue
        if index in previous:
            diff = cv2.absdiff(previous[index], gray)
            scores.append(float(diff.mean()))
        previous[index] = gray
        if preview is not None:
            previews.append((index, preview))
    if not scores:
        return 0.0, previews
    return sum(scores) / len(scores), previews


def show_previews(cv2: Any, previews) -> bool:
    for index, (frame, roi) in previews:
        x, y, w, h = roi
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.imshow(f"camera_{index}", frame)
    return (cv2.waitKey(1) & 0xFF) == ord("q")


def other_motion(motion: str) -> str:
    return "front-back" if motion == "left-right" else "left-right"


def main() -> int:
    args = parse_args()
    if args.cycles <= 0 or args.cycles > 50:
        print("--cycles must be > 0 and <= 50.")
        return 1
    if not CONFIG_PATH.exists():
        print("Missing config.json.")
        return 1

    try:
        import cv2
    except ImportError:
        print("OpenCV is not installed.")
        return 1

    config = load_json(CONFIG_PATH)
    width = int(config.get("camera_width", 640))
    height = int(config.get("camera_height", 480))
    fps = int(config.get("camera_fps", 30))
    camera_indices = args.cameras if args.cameras is not None else config.get("camera_indices", [0, 1])
    speed_scale = args.speed_scale if args.speed_scale is not None else config.get("speed_scale", DEFAULT_SPEED_SCALE)
    roi = tuple(args.roi) if args.roi else None

    pose_names: dict[str, tuple[str, str]] = {}
    poses: dict[str, dict[str, float]] = {}
    for motion, pair in MOTIONS.items():
        first_name, first_pose = load_pose(config, pair[0])
        second_name, second_pose = load_pose(config, pair[1])
        pose_names[motion] = (first_name, second_name)
        poses[first_name] = first_pose
        poses[second_name] = second_pose
    park_name, park_pose = load_pose(config, ("PARK",)) if not args.no_park else ("PARK", None)

    cameras = []
    robot = None
    try:
        for index in camera_indices:
            cap = open_camera(cv2, int(index), width, height, fps)
            if cap is None:
                print(f"Camera {index}: failed to open")
            else:
                print(f"Camera {index}: open")
                cameras.append((int(index), cap))
        if not cameras:
            print("No cameras available. Refusing automatic OpenCV stirring.")
            return 1

        active_motion = "left-right" if args.motion == "auto" else args.motion
        previous: dict[int, Any] = {}

        print("OpenCV automatic stirring, no training.")
        print("Uses frame-change activity in the bowl ROI to choose/repeat saved sweep poses.")
        print("This controls only the SO-101 arm. It does not control the 360-degree servo.")
        print("Keep hand near power switch. Press Ctrl+C to stop.")
        print(f"motion={args.motion}, starting_motion={active_motion}, cycles={args.cycles}, speed_scale={speed_scale}")

        activity, previews = camera_activity(cv2, cameras, previous, roi)
        if args.preview and show_previews(cv2, previews):
            return 0

        if args.dry_run:
            print("Dry run only. Cameras are active, robot will not move.")
        elif not args.yes:
            input("Press Enter to connect and start OpenCV auto stirring, or Ctrl+C to cancel.")

        if not args.dry_run:
            print(f"Connecting to SO-101 follower on {config.get('robot_port')}...")
            robot = connect_robot(config)
            print("Robot connected.")

        low_activity_count = 0
        for cycle in range(1, args.cycles + 1):
            first_name, second_name = pose_names[active_motion]
            print(f"Cycle {cycle}: motion={active_motion}")
            for pose_name in (first_name, second_name):
                print(f"Moving to {pose_name}")
                if not args.dry_run:
                    move_to_position(robot, poses[pose_name], speed_scale)
                time.sleep(args.pause)
                activity, previews = camera_activity(cv2, cameras, previous, roi)
                print(f"OpenCV activity={activity:.2f}")
                if args.preview and show_previews(cv2, previews):
                    raise KeyboardInterrupt

            if args.motion == "auto":
                if activity < args.min_change:
                    low_activity_count += 1
                else:
                    low_activity_count = 0
                if low_activity_count >= 1:
                    active_motion = other_motion(active_motion)
                    low_activity_count = 0
                    print(f"Low visual activity. Switching to {active_motion}.")

        if park_pose is not None:
            print(f"Moving to {park_name}")
            if not args.dry_run:
                move_to_position(robot, park_pose, speed_scale)

        print("OpenCV auto stirring complete.")
        return 0
    except KeyboardInterrupt:
        print("\nStop requested. Stopping robot now.")
        stop_robot(robot)
        return 130
    except Exception as exc:
        print(f"OpenCV auto stirring failed: {exc}")
        return 1
    finally:
        disconnect_robot(robot)
        for _, cap in cameras:
            cap.release()
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass
        print("Disconnected.")


if __name__ == "__main__":
    raise SystemExit(main())
