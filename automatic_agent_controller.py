from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
PROJECT_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
CONFIG_PATH = ROOT / "config.json"

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
    parser.add_argument("--execute", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--plan-only", action="store_true", help="Print the selected command without moving the robot.")
    parser.add_argument("--camera-indices", nargs="*", type=int, default=None)
    parser.add_argument("--speed-scale", type=float, default=0.02)
    parser.add_argument("--pause", type=float, default=0.4)
    parser.add_argument("--steps", type=int, default=12)
    parser.add_argument("--use-saved-poses", action="store_true", help="Use saved PEN_* poses instead of camera-guided micro-moves.")
    parser.add_argument("--dry-run-command", action="store_true", help="Validate selected pose commands without movement.")
    return parser.parse_args()


def positions_status(sequence: list[str]) -> dict[str, bool]:
    config = load_json(CONFIG_PATH)
    positions_path = ROOT / config.get("positions_file", "positions.json")
    positions = load_json(positions_path)
    return {name: bool(positions.get(name)) for name in sequence}


def command_for(args: argparse.Namespace) -> list[str]:
    python_exe = str(PROJECT_PYTHON if PROJECT_PYTHON.exists() else Path(sys.executable))
    speed = str(args.speed_scale)
    pause = str(args.pause)
    if not args.use_saved_poses:
        command = [
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
        if args.model:
            command.extend(["--model", args.model])
        if args.camera_indices:
            command.extend(["--camera-indices", *[str(index) for index in args.camera_indices]])
        return command
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
        print("CMD: set OPENAI_API_KEY=your_api_key_here")
        return 1

    try:
        command = command_for(args)
        result = {
            "request": request,
            "mode": "saved_poses" if args.use_saved_poses else "free_camera_guided_micro_moves",
            "saved_pose_status": positions_status(PEN_TO_CUP_SEQUENCE) if args.use_saved_poses else None,
            "command": command,
        }
        print(json.dumps(result, indent=2))
        if args.plan_only:
            print("Planning only. Remove --plan-only to run movement.")
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
