from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from openai import OpenAI


ROOT = Path(__file__).resolve().parent
PROJECT_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
CONFIG_PATH = ROOT / "config.json"

ALLOWED_ACTIONS = {
    "plan_only",
    "visual_servo_task",
    "pick_pen_place_cup_saved_poses",
    "smart_cup_stick_stir",
    "full_upma_with_ingredients",
    "ingredients_only",
    "stir_front_back",
    "stir_left_right",
    "grip_down",
    "stop",
}

PEN_TO_CUP_SEQUENCE = [
    "HOME",
    "PEN_APPROACH",
    "PEN_GRASP",
    "PEN_LIFT",
    "CUP_TARGET",
    "PEN_RELEASE",
    "PEN_RETREAT",
    "HOME",
]


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Camera-aware bounded ChatGPT agent controller for SO-101.")
    parser.add_argument("request", nargs="*", help="Plain English request, for example: pick up the pen and place it in the cup.")
    parser.add_argument("--model", default=os.environ.get("CHATGPT_ROBOT_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--execute", action="store_true", help="Run the selected safe command.")
    parser.add_argument("--camera-indices", nargs="*", type=int, default=None)
    parser.add_argument("--speed-scale", type=float, default=0.02)
    parser.add_argument("--pause", type=float, default=0.4)
    parser.add_argument("--steps", type=int, default=12)
    parser.add_argument("--use-saved-poses", action="store_true", help="Use saved PEN_* poses instead of camera-guided micro-moves.")
    parser.add_argument("--dry-run-command", action="store_true", help="Validate selected pose commands without movement.")
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
        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
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


def positions_status(sequence: list[str]) -> dict[str, bool]:
    config = load_json(CONFIG_PATH)
    positions_path = ROOT / config.get("positions_file", "positions.json")
    positions = load_json(positions_path)
    return {name: bool(positions.get(name)) for name in sequence}


def ask_agent(client: OpenAI, args: argparse.Namespace, request: str, camera_images: list[dict[str, str]]) -> dict[str, Any]:
    instructions = (
        "You are a bounded automatic controller for a LeRobot SO-101 arm. "
        "Use camera images to understand the scene, but choose only one action from the allowed list. "
        "Never invent raw joint angles. Never claim the robot can do arbitrary manipulation without calibrated poses. "
        "For 'pick up the pen and place in the cup', choose visual_servo_task unless the caller explicitly requires saved poses. "
        "If the task is unclear, unsafe, outside the listed actions, or needs missing calibration, choose plan_only or stop. "
        "Return only JSON with keys: action, reason, needed_poses, safety_note."
    )
    content: list[dict[str, Any]] = [
        {
            "type": "input_text",
            "text": json.dumps(
                {
                    "user_request": request,
                    "allowed_actions": sorted(ALLOWED_ACTIONS),
                    "prefer_without_saved_poses": not args.use_saved_poses,
                    "pen_to_cup_required_poses": positions_status(PEN_TO_CUP_SEQUENCE),
                    "available_camera_count": len(camera_images),
                    "rule": "Use only safe project commands. Real movement is executed by local scripts, not by raw model output.",
                },
                indent=2,
            ),
        }
    ]
    for image in camera_images[:3]:
        content.append({"type": "input_text", "text": f"Camera {image['index']} view:"})
        content.append({"type": "input_image", "image_url": image["data_url"]})
    response = client.responses.create(
        model=args.model,
        instructions=instructions,
        input=[{"role": "user", "content": content}],
    )
    decision = extract_json(response.output_text)
    action = str(decision.get("action", "")).strip()
    if action not in ALLOWED_ACTIONS:
        action = "plan_only"
    if action == "pick_pen_place_cup_saved_poses" and not args.use_saved_poses:
        action = "visual_servo_task"
    if action == "visual_servo_task" and args.use_saved_poses:
        action = "pick_pen_place_cup_saved_poses"
    return {
        "action": action,
        "reason": str(decision.get("reason", "")),
        "needed_poses": decision.get("needed_poses", []),
        "safety_note": str(decision.get("safety_note", "")),
    }


def command_for(action: str, args: argparse.Namespace) -> list[str] | None:
    python_exe = str(PROJECT_PYTHON if PROJECT_PYTHON.exists() else Path(sys.executable))
    speed = str(args.speed_scale)
    pause = str(args.pause)
    if action in {"plan_only", "stop"}:
        return None
    if action == "visual_servo_task":
        return [
            python_exe,
            "visual_agent_runner.py",
            request_text_from_args(args),
            "--steps",
            str(args.steps),
            "--speed-scale",
            speed,
            "--pause",
            pause,
            "--yes",
        ]
    if action == "pick_pen_place_cup_saved_poses":
        command = [
            python_exe,
            "generic_pose_action.py",
            "--sequence",
            *PEN_TO_CUP_SEQUENCE,
            "--speed-scale",
            speed,
            "--pause",
            pause,
            "--yes",
        ]
        if args.dry_run_command:
            command.append("--dry-run")
        return command
    if action == "smart_cup_stick_stir":
        return [python_exe, "smart_upma_runner.py", "--yes", "--speed-scale", speed, "--pause", pause]
    if action == "full_upma_with_ingredients":
        return [python_exe, "upma_mode.py", "--with-ingredients", "--yes", "--speed-scale", speed, "--pause", pause]
    if action == "ingredients_only":
        return [python_exe, "ingredient_actions.py", "--action", "all", "--speed-scale", speed, "--pause", pause, "--yes"]
    if action == "stir_front_back":
        return [python_exe, "stir_motion.py", "--motion", "front-back", "--cycles", "2", "--speed-scale", speed, "--yes"]
    if action == "stir_left_right":
        return [python_exe, "stir_motion.py", "--motion", "left-right", "--cycles", "2", "--speed-scale", speed, "--yes"]
    if action == "grip_down":
        return [python_exe, "grip_down.py", "--speed-scale", speed, "--grip-value", "-5", "--pause", pause, "--yes"]
    return None


def request_text_from_args(args: argparse.Namespace) -> str:
    value = getattr(args, "_request_text", "")
    return value if value else "perform the requested task"


def main() -> int:
    args = parse_args()
    request = " ".join(args.request).strip() or input("What should I do for you? ").strip()
    args._request_text = request
    if not request:
        print("No request provided.")
        return 1
    if not os.environ.get("OPENAI_API_KEY"):
        print("Missing OPENAI_API_KEY. Set it in your terminal, never in Git.")
        print('PowerShell: $env:OPENAI_API_KEY="your_api_key_here"')
        return 1

    config = load_json(CONFIG_PATH)
    camera_indices = args.camera_indices or [int(index) for index in config.get("camera_indices", [0])]
    width = int(config.get("camera_width", 640))
    height = int(config.get("camera_height", 480))
    camera_images = capture_camera_images(camera_indices, width, height)
    print(f"Automatic agent captured {len(camera_images)} camera frame(s).")

    try:
        decision = ask_agent(OpenAI(), args, request, camera_images)
        command = command_for(decision["action"], args)
        result = {"request": request, "decision": decision, "command": command}
        print(json.dumps(result, indent=2))
        if command is None:
            print("No robot command selected.")
            return 0
        if not args.execute:
            print("Planning only. Add --execute to run movement.")
            return 0
        print("Executing automatic agent command.")
        completed = subprocess.run(command, cwd=ROOT, check=False)
        return int(completed.returncode)
    except KeyboardInterrupt:
        print("\nAutomatic agent stopped.")
        return 130
    except Exception as exc:
        print(f"Automatic agent failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
