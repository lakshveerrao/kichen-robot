from __future__ import annotations

import argparse
import base64
import json
import os
import time
from pathlib import Path
from typing import Any

from openai import OpenAI

from robot_api import connect_robot, disconnect_robot, move_to_position, read_current_position, stop_robot


CONFIG_PATH = Path("config.json")

ALLOWED_MOVES = {
    "pan_left",
    "pan_right",
    "lift_up",
    "lift_down",
    "wrist_forward",
    "wrist_back",
    "open_gripper",
    "close_gripper",
    "hold",
    "done",
    "stop",
}


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Camera-guided bounded terminal agent for SO-101.")
    parser.add_argument("request", help="Task request, for example: pick up the pen and place it in the cup.")
    parser.add_argument("--model", default=os.environ.get("CHATGPT_ROBOT_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--steps", type=int, default=12)
    parser.add_argument("--speed-scale", type=float, default=0.02)
    parser.add_argument("--pause", type=float, default=0.4)
    parser.add_argument("--camera-indices", nargs="*", type=int, default=None)
    parser.add_argument("--yes", action="store_true")
    return parser.parse_args()


def capture_camera_images(indices: list[int], width: int, height: int) -> list[dict[str, str]]:
    try:
        import cv2
    except ImportError:
        return []
    images = []
    for index in indices:
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        ok, frame = cap.read() if cap.isOpened() else (False, None)
        cap.release()
        if not ok or frame is None:
            continue
        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        if ok:
            images.append(
                {
                    "index": str(index),
                    "data_url": "data:image/jpeg;base64," + base64.b64encode(encoded.tobytes()).decode("ascii"),
                }
            )
    return images


def extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.startswith("json"):
            text = text[4:].strip()
    return json.loads(text)


def ask_next_move(
    client: OpenAI,
    model: str,
    request: str,
    step: int,
    position: dict[str, float],
    camera_images: list[dict[str, str]],
) -> dict[str, str]:
    instructions = (
        "You are controlling an SO-101 robot through small bounded relative moves only. "
        "Use the camera images and current joint position to choose exactly one next move. "
        "Allowed moves: pan_left, pan_right, lift_up, lift_down, wrist_forward, wrist_back, "
        "open_gripper, close_gripper, hold, done, stop. "
        "Never output raw joint angles. If uncertain or unsafe, choose stop. "
        "Return only JSON with keys: move, reason."
    )
    content: list[dict[str, Any]] = [
        {
            "type": "input_text",
            "text": json.dumps(
                {
                    "task": request,
                    "step": step,
                    "current_position": position,
                    "allowed_moves": sorted(ALLOWED_MOVES),
                    "strategy": [
                        "Move slowly.",
                        "Use pan/wrist/lift to align the gripper with the object.",
                        "Close gripper only when the object appears inside the gripper.",
                        "Move toward the target container after grasp.",
                        "Open gripper only when above/in the target.",
                    ],
                },
                indent=2,
            ),
        }
    ]
    for image in camera_images[:3]:
        content.append({"type": "input_text", "text": f"Camera {image['index']}:"})
        content.append({"type": "input_image", "image_url": image["data_url"]})
    response = client.responses.create(
        model=model,
        instructions=instructions,
        input=[{"role": "user", "content": content}],
    )
    decision = extract_json(response.output_text)
    move = str(decision.get("move", "")).strip()
    if move not in ALLOWED_MOVES:
        move = "stop"
    return {"move": move, "reason": str(decision.get("reason", ""))}


def target_for_move(current: dict[str, float], move: str) -> dict[str, float] | None:
    target = dict(current)
    if move == "pan_left":
        target["shoulder_pan.pos"] -= 2.0
    elif move == "pan_right":
        target["shoulder_pan.pos"] += 2.0
    elif move == "lift_up":
        target["shoulder_lift.pos"] += 1.5
    elif move == "lift_down":
        target["shoulder_lift.pos"] -= 1.5
    elif move == "wrist_forward":
        target["wrist_flex.pos"] -= 2.0
    elif move == "wrist_back":
        target["wrist_flex.pos"] += 2.0
    elif move == "open_gripper":
        target["gripper.pos"] = min(95.0, target["gripper.pos"] + 18.0)
    elif move == "close_gripper":
        target["gripper.pos"] = max(-5.0, target["gripper.pos"] - 18.0)
    elif move in {"hold", "done", "stop"}:
        return None
    else:
        return None
    return target


def main() -> int:
    args = parse_args()
    if args.steps <= 0 or args.steps > 50:
        print("--steps must be > 0 and <= 50.")
        return 1
    if not os.environ.get("OPENAI_API_KEY"):
        print("Missing OPENAI_API_KEY. Set it in your terminal, never in Git.")
        return 1
    if not CONFIG_PATH.exists():
        print("Missing config.json.")
        return 1

    robot = None
    try:
        config = load_json(CONFIG_PATH)
        camera_indices = args.camera_indices or [int(index) for index in config.get("camera_indices", [0])]
        width = int(config.get("camera_width", 640))
        height = int(config.get("camera_height", 480))
        print("Terminal automatic agent controller")
        print(f"Task: {args.request}")
        print(f"Max steps: {args.steps}")
        print("This uses small bounded camera-guided moves from the current pose.")
        if not args.yes:
            input("Put one hand near the power switch. Press Enter to connect and start, or Ctrl+C to cancel.")
        robot = connect_robot(config)
        client = OpenAI()
        for step in range(1, args.steps + 1):
            position = read_current_position(robot)
            images = capture_camera_images(camera_indices, width, height)
            print(f"Step {step}/{args.steps}: captured {len(images)} camera frame(s).")
            decision = ask_next_move(client, args.model, args.request, step, position, images)
            move = decision["move"]
            print(f"Agent move: {move} - {decision['reason']}")
            if move == "done":
                print("Agent reports task complete.")
                return 0
            if move == "stop":
                print("Agent requested stop.")
                stop_robot(robot)
                return 1
            target = target_for_move(position, move)
            if target is None:
                time.sleep(args.pause)
                continue
            move_to_position(robot, target, args.speed_scale)
            time.sleep(args.pause)
        print("Reached max automatic steps.")
        return 0
    except KeyboardInterrupt:
        print("\nStop requested. Stopping robot now.")
        stop_robot(robot)
        return 130
    except Exception as exc:
        print(f"Visual agent failed: {exc}")
        return 1
    finally:
        disconnect_robot(robot)
        print("Disconnected.")


if __name__ == "__main__":
    raise SystemExit(main())
