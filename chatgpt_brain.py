from __future__ import annotations

import argparse
import base64
import json
import os
import time
from pathlib import Path
from typing import Any

from openai import OpenAI

from robot_api import (
    DEFAULT_SPEED_SCALE,
    connect_robot,
    disconnect_robot,
    move_to_position,
    read_current_position,
    stop_robot,
)


CONFIG_PATH = Path("config.json")
ALLOWED_ACTIONS = {
    "pan_left",
    "pan_right",
    "wrist_forward",
    "wrist_back",
    "lift_up",
    "lift_down",
    "center",
    "park",
    "stop",
}
FREE_DELTA_KEYS = {
    "shoulder_pan.pos",
    "shoulder_lift.pos",
    "elbow_flex.pos",
    "wrist_flex.pos",
    "wrist_roll.pos",
    "gripper.pos",
}


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ChatGPT API brain for bounded SO-101 movement.")
    parser.add_argument("--model", default=os.environ.get("CHATGPT_ROBOT_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--cameras", nargs="+", type=int, default=None)
    parser.add_argument("--steps", type=int, default=10)
    parser.add_argument("--pan-deg", type=float, default=5.0)
    parser.add_argument("--wrist-deg", type=float, default=5.0)
    parser.add_argument("--lift-deg", type=float, default=2.0)
    parser.add_argument("--wide", action="store_true", help="Use wider default relative motion limits.")
    parser.add_argument("--free-delta", action="store_true", help="Let ChatGPT return bounded relative joint deltas.")
    parser.add_argument("--max-delta", type=float, default=None, help="Max absolute delta per joint for --free-delta.")
    parser.add_argument("--speed-scale", type=float, default=None)
    parser.add_argument("--pause", type=float, default=0.3)
    parser.add_argument("--roi", nargs=4, type=int, metavar=("X", "Y", "W", "H"))
    parser.add_argument("--send-image-every", type=int, default=0, help="Send a small image every N steps. 0 disables.")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Ask ChatGPT but do not move robot.")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--no-return-center", action="store_true")
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


def read_roi(cv2: Any, cap: Any, roi: tuple[int, int, int, int] | None):
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
    return gray, (frame, crop, (x, y, rw, rh))


def camera_state(cv2: Any, cameras: list[tuple[int, Any]], previous: dict[int, Any], roi):
    activity_scores: list[float] = []
    brightness_scores: list[float] = []
    previews = []
    image_frame = None
    for index, cap in cameras:
        gray, preview = read_roi(cv2, cap, roi)
        if gray is None:
            continue
        brightness_scores.append(float(gray.mean()))
        if index in previous:
            diff = cv2.absdiff(previous[index], gray)
            activity_scores.append(float(diff.mean()))
        previous[index] = gray
        if preview is not None:
            frame, crop, roi_box = preview
            previews.append((index, frame, roi_box))
            if image_frame is None:
                image_frame = crop
    activity = sum(activity_scores) / len(activity_scores) if activity_scores else 0.0
    brightness = sum(brightness_scores) / len(brightness_scores) if brightness_scores else 0.0
    return {"activity": activity, "brightness": brightness}, previews, image_frame


def show_previews(cv2: Any, previews) -> bool:
    for index, frame, roi in previews:
        x, y, w, h = roi
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.imshow(f"camera_{index}", frame)
    return (cv2.waitKey(1) & 0xFF) == ord("q")


def encode_image(cv2: Any, frame: Any) -> str | None:
    if frame is None:
        return None
    resized = cv2.resize(frame, (320, 240))
    ok, encoded = cv2.imencode(".jpg", resized, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
    if not ok:
        return None
    return base64.b64encode(encoded.tobytes()).decode("ascii")


def build_actions(args: argparse.Namespace) -> dict[str, dict[str, float]]:
    return {
        "pan_left": {"shoulder_pan.pos": -args.pan_deg},
        "pan_right": {"shoulder_pan.pos": args.pan_deg},
        "wrist_forward": {"wrist_flex.pos": -args.wrist_deg},
        "wrist_back": {"wrist_flex.pos": args.wrist_deg},
        "lift_up": {"shoulder_lift.pos": args.lift_deg},
        "lift_down": {"shoulder_lift.pos": -args.lift_deg},
        "center": {},
        "park": {},
        "stop": {},
    }


def apply_delta(center: dict[str, float], delta: dict[str, float]) -> dict[str, float]:
    target = dict(center)
    for key, value in delta.items():
        if key not in target:
            raise KeyError(f"Robot position does not include {key}")
        target[key] = center[key] + value
    return target


def extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    return json.loads(text)


def ask_chatgpt(
    client: OpenAI,
    model: str,
    state: dict,
    image_b64: str | None,
    free_delta: bool,
) -> dict:
    if free_delta:
        instructions = (
            "You are a safety-bounded robot stirring planner. "
            "Choose small relative joint deltas that should improve stirring from camera feedback. "
            "Return only JSON with keys: action, deltas, reason. "
            "Use action='move' to move, action='center' to return to center, or action='stop' if unsafe. "
            "Deltas must be relative degrees/units and must stay within the provided max_delta_per_joint. "
            "Do not output absolute joint targets."
        )
    else:
        instructions = (
            "You are a safety-bounded robot stirring planner. "
            "Choose exactly one action from the allowed list. "
            "Prefer actions that increase mixing activity, vary direction, and avoid repeated useless moves. "
            "Return only JSON with keys: action, reason. "
            "Do not invent joint angles. Do not request any action outside the allowed list. "
            "If state looks unsafe, choose stop."
        )
    state_text = json.dumps(state, indent=2)
    content: list[dict[str, Any]] = [
        {
            "type": "input_text",
            "text": (
                "Robot/camera state:\n"
                f"{state_text}\n\n"
                + (
                    "Return JSON like {\"action\":\"move\",\"deltas\":{\"shoulder_pan.pos\":10},\"reason\":\"...\"}."
                    if free_delta
                    else f"Allowed actions: {sorted(ALLOWED_ACTIONS)}\nReturn JSON like {{\"action\":\"pan_left\",\"reason\":\"...\"}}."
                )
            ),
        }
    ]
    if image_b64 is not None:
        content.append(
            {
                "type": "input_image",
                "image_url": f"data:image/jpeg;base64,{image_b64}",
            }
        )

    response = client.responses.create(
        model=model,
        instructions=instructions,
        input=[{"role": "user", "content": content}],
    )
    text = response.output_text
    decision = extract_json(text)
    action = str(decision.get("action", "")).strip()
    allowed = {"move", "center", "stop"} if free_delta else ALLOWED_ACTIONS
    if action not in allowed:
        raise ValueError(f"ChatGPT returned disallowed action: {action!r}")
    return {
        "action": action,
        "deltas": decision.get("deltas", {}),
        "reason": str(decision.get("reason", "")),
    }


def validate_free_deltas(raw_deltas: Any, max_delta: float) -> dict[str, float]:
    if not isinstance(raw_deltas, dict):
        raise ValueError("ChatGPT move action did not include a deltas object.")
    deltas: dict[str, float] = {}
    for key, value in raw_deltas.items():
        if key not in FREE_DELTA_KEYS:
            raise ValueError(f"ChatGPT returned disallowed joint key: {key!r}")
        number = float(value)
        if abs(number) > max_delta:
            raise ValueError(f"ChatGPT delta for {key}={number} exceeds max_delta={max_delta}.")
        deltas[key] = number
    return deltas


def main() -> int:
    args = parse_args()
    if args.wide:
        args.pan_deg = max(args.pan_deg, 25.0)
        args.wrist_deg = max(args.wrist_deg, 25.0)
        args.lift_deg = max(args.lift_deg, 8.0)
        if args.max_delta is None:
            args.max_delta = 25.0
    if args.max_delta is None:
        args.max_delta = max(args.pan_deg, args.wrist_deg, args.lift_deg)
    if args.steps <= 0 or args.steps > 100:
        print("--steps must be > 0 and <= 100.")
        return 1
    if args.pan_deg <= 0 or args.pan_deg > 45 or args.wrist_deg <= 0 or args.wrist_deg > 45 or args.lift_deg < 0 or args.lift_deg > 15:
        print("Deltas too large. Use pan/wrist <= 45 degrees and lift <= 15 degrees.")
        return 1
    if args.max_delta <= 0 or args.max_delta > 45:
        print("--max-delta must be > 0 and <= 45.")
        return 1
    if not os.environ.get("OPENAI_API_KEY"):
        print("Missing OPENAI_API_KEY environment variable.")
        return 1
    if not CONFIG_PATH.exists():
        print("Missing config.json.")
        return 1

    try:
        import cv2
    except ImportError:
        print("OpenCV is not installed.")
        return 1

    client = OpenAI()
    config = load_json(CONFIG_PATH)
    width = int(config.get("camera_width", 640))
    height = int(config.get("camera_height", 480))
    fps = int(config.get("camera_fps", 30))
    camera_indices = args.cameras if args.cameras is not None else config.get("camera_indices", [0, 1])
    speed_scale = args.speed_scale if args.speed_scale is not None else config.get("speed_scale", DEFAULT_SPEED_SCALE)
    roi = tuple(args.roi) if args.roi else None
    actions = build_actions(args)

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
            print("No cameras available. Refusing ChatGPT robot control.")
            return 1

        print("ChatGPT API robot brain.")
        if args.free_delta:
            print("The model returns relative joint deltas; this script validates them before moving.")
        else:
            print("The model chooses from a fixed safe action list; this script executes only bounded small moves.")
        print("Keep hand near power switch. Press Ctrl+C to stop.")
        print(f"model={args.model}, steps={args.steps}, speed_scale={speed_scale}")

        previous: dict[int, Any] = {}
        cam_metrics, previews, image_frame = camera_state(cv2, cameras, previous, roi)
        if args.preview and show_previews(cv2, previews):
            return 0

        if args.dry_run:
            print("Dry run only. ChatGPT will be called, robot will not move.")
            center = {
                "shoulder_pan.pos": 0.0,
                "shoulder_lift.pos": 0.0,
                "elbow_flex.pos": 0.0,
                "wrist_flex.pos": 0.0,
                "wrist_roll.pos": 0.0,
                "gripper.pos": 0.0,
            }
            current = dict(center)
        else:
            if not args.yes:
                input("Press Enter to connect and let ChatGPT choose bounded moves, or Ctrl+C to cancel.")
            print(f"Connecting to SO-101 follower on {config.get('robot_port')}...")
            robot = connect_robot(config)
            center = read_current_position(robot)
            current = dict(center)
            print("Robot connected. Current pose captured as safe center.")

        last_actions: list[str] = []
        for step in range(1, args.steps + 1):
            cam_metrics, previews, image_frame = camera_state(cv2, cameras, previous, roi)
            image_b64 = None
            if args.send_image_every > 0 and step % args.send_image_every == 0:
                image_b64 = encode_image(cv2, image_frame)

            state = {
                "step": step,
                "camera": cam_metrics,
                "current_position": current,
                "safe_center_position": center,
                "allowed_relative_deltas": actions,
                "free_delta_mode": args.free_delta,
                "allowed_delta_joint_keys": sorted(FREE_DELTA_KEYS),
                "max_delta_per_joint": args.max_delta,
                "recent_actions": last_actions[-5:],
                "safety": {
                    "bounded_around_center": True,
                    "max_pan_delta_deg": args.pan_deg,
                    "max_wrist_delta_deg": args.wrist_deg,
                    "max_lift_delta_deg": args.lift_deg,
                },
            }
            decision = ask_chatgpt(client, args.model, state, image_b64, args.free_delta)
            action = decision["action"]
            print(f"Step {step}: ChatGPT action={action} reason={decision['reason']}")

            if action == "stop":
                print("ChatGPT requested stop.")
                stop_robot(robot)
                break

            if args.free_delta:
                target = center if action == "center" else apply_delta(center, validate_free_deltas(decision["deltas"], args.max_delta))
            else:
                target = center if action == "park" else apply_delta(center, actions[action])
            if not args.dry_run:
                move_to_position(robot, target, speed_scale)
                current = read_current_position(robot)
            else:
                current = target
            last_actions.append(action)
            time.sleep(args.pause)

            if args.preview and show_previews(cv2, previews):
                raise KeyboardInterrupt

        if not args.no_return_center:
            print("Returning to safe center pose")
            if not args.dry_run:
                move_to_position(robot, center, speed_scale)

        if not args.hold_at_end:
            print("Stopping robot at end")
            stop_robot(robot)

        print("ChatGPT brain complete.")
        return 0
    except KeyboardInterrupt:
        print("\nStop requested. Stopping robot now.")
        stop_robot(robot)
        return 130
    except Exception as exc:
        print(f"ChatGPT brain failed: {exc}")
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
