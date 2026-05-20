from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path
from typing import Any

from robot_api import (
    DEFAULT_SPEED_SCALE,
    connect_robot,
    disconnect_robot,
    move_to_position,
    read_current_position,
    stop_robot,
)


CONFIG_PATH = Path("config.json")


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Live camera-guided bounded RL-style stirring.")
    parser.add_argument("--cameras", nargs="+", type=int, default=None, help="Camera indices to use.")
    parser.add_argument("--steps", type=int, default=20, help="Maximum learning/control steps.")
    parser.add_argument("--pan-deg", type=float, default=8.0, help="Left/right pan delta from center.")
    parser.add_argument("--wrist-deg", type=float, default=8.0, help="Forward/back wrist flex delta from center.")
    parser.add_argument("--lift-deg", type=float, default=4.0, help="Small shoulder lift delta from center.")
    parser.add_argument("--speed-scale", type=float, default=None, help="Override config speed_scale.")
    parser.add_argument("--pause", type=float, default=0.25, help="Pause after each move before scoring camera activity.")
    parser.add_argument("--epsilon", type=float, default=0.25, help="Exploration probability from 0 to 1.")
    parser.add_argument("--roi", nargs=4, type=int, metavar=("X", "Y", "W", "H"), help="Camera ROI in pixels.")
    parser.add_argument("--preview", action="store_true", help="Show camera preview windows. Press q to stop.")
    parser.add_argument("--dry-run", action="store_true", help="Open cameras and print decisions without moving.")
    parser.add_argument("--yes", action="store_true", help="Do not wait for Enter before movement.")
    parser.add_argument("--no-return-center", action="store_true", help="Do not return to the starting pose at the end.")
    parser.add_argument("--hold-at-end", action="store_true", help="Keep torque on at the end instead of stopping.")
    return parser.parse_args()


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


def build_actions(args: argparse.Namespace) -> dict[str, dict[str, float]]:
    return {
        "pan_left": {"shoulder_pan.pos": -args.pan_deg},
        "pan_right": {"shoulder_pan.pos": args.pan_deg},
        "wrist_forward": {"wrist_flex.pos": -args.wrist_deg},
        "wrist_back": {"wrist_flex.pos": args.wrist_deg},
        "lift_up": {"shoulder_lift.pos": args.lift_deg},
        "lift_down": {"shoulder_lift.pos": -args.lift_deg},
        "center": {},
    }


def apply_delta(center: dict[str, float], delta: dict[str, float]) -> dict[str, float]:
    target = dict(center)
    for key, value in delta.items():
        if key not in target:
            raise KeyError(f"Robot position does not include {key}")
        target[key] = center[key] + value
    return target


def choose_action(q_values: dict[str, float], epsilon: float) -> str:
    if random.random() < epsilon:
        return random.choice(list(q_values))
    return max(q_values, key=q_values.get)


def main() -> int:
    args = parse_args()
    if args.steps <= 0 or args.steps > 100:
        print("--steps must be > 0 and <= 100.")
        return 1
    if not 0 <= args.epsilon <= 1:
        print("--epsilon must be between 0 and 1.")
        return 1
    if args.pan_deg <= 0 or args.pan_deg > 20 or args.wrist_deg <= 0 or args.wrist_deg > 20 or args.lift_deg < 0 or args.lift_deg > 10:
        print("Deltas too large. Use pan/wrist <= 20 degrees and lift <= 10 degrees.")
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
            print("No cameras available. Refusing live control.")
            return 1

        print("Live camera-guided bounded RL-style stirring.")
        print("No saved poses are required. The current arm pose becomes the center.")
        print("Actions are small relative moves around that center; reward is OpenCV frame-change activity.")
        print("Keep hand near power switch. Press Ctrl+C to stop.")
        print(f"steps={args.steps}, epsilon={args.epsilon}, speed_scale={speed_scale}")

        previous: dict[int, Any] = {}
        activity, previews = camera_activity(cv2, cameras, previous, roi)
        if args.preview and show_previews(cv2, previews):
            return 0

        if args.dry_run:
            print("Dry run only. Cameras are active, robot will not move.")
            center = {
                "shoulder_pan.pos": 0.0,
                "shoulder_lift.pos": 0.0,
                "elbow_flex.pos": 0.0,
                "wrist_flex.pos": 0.0,
                "wrist_roll.pos": 0.0,
                "gripper.pos": 0.0,
            }
        else:
            if not args.yes:
                input("Press Enter to connect and start live control, or Ctrl+C to cancel.")
            print(f"Connecting to SO-101 follower on {config.get('robot_port')}...")
            robot = connect_robot(config)
            center = read_current_position(robot)
            print("Robot connected. Current pose captured as center.")

        actions = build_actions(args)
        q_values = {name: 0.0 for name in actions}
        counts = {name: 0 for name in actions}

        for step in range(1, args.steps + 1):
            action_name = choose_action(q_values, args.epsilon)
            target = apply_delta(center, actions[action_name])
            print(f"Step {step}: action={action_name}")
            if not args.dry_run:
                move_to_position(robot, target, speed_scale)
            time.sleep(args.pause)

            reward, previews = camera_activity(cv2, cameras, previous, roi)
            counts[action_name] += 1
            q_values[action_name] += (reward - q_values[action_name]) / counts[action_name]
            print(f"Reward(activity)={reward:.2f} learned_score={q_values[action_name]:.2f}")

            if args.preview and show_previews(cv2, previews):
                raise KeyboardInterrupt

        if not args.no_return_center:
            print("Returning to starting center pose")
            if not args.dry_run:
                move_to_position(robot, center, speed_scale)

        if not args.hold_at_end:
            print("Stopping robot at end")
            stop_robot(robot)

        print("Learned action scores:")
        for name, value in sorted(q_values.items(), key=lambda item: item[1], reverse=True):
            print(f"  {name}: {value:.2f} from {counts[name]} tries")
        print("Live RL-style stirring complete.")
        return 0
    except KeyboardInterrupt:
        print("\nStop requested. Stopping robot now.")
        stop_robot(robot)
        return 130
    except Exception as exc:
        print(f"Live RL-style stirring failed: {exc}")
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
