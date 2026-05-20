from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from openai import OpenAI


ROOT = Path(__file__).resolve().parent
PROJECT_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"

ALLOWED_ACTIONS = {
    "dry_full_upma",
    "full_upma",
    "full_upma_with_ingredients",
    "smart_cup_stick_stir",
    "ingredients_only",
    "stir_front_back",
    "stir_left_right",
    "grip_down",
    "stop",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ChatGPT project brain for safe SO-101 upma robot actions."
    )
    parser.add_argument("request", nargs="*", help="Plain English command for the robot.")
    parser.add_argument("--model", default=os.environ.get("CHATGPT_ROBOT_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--execute", action="store_true", help="Actually run the selected robot command.")
    parser.add_argument("--speed-scale", type=float, default=0.02)
    parser.add_argument("--pause", type=float, default=0.25)
    parser.add_argument("--cycles", type=int, default=5)
    parser.add_argument("--tight", type=float, default=-5.0)
    parser.add_argument("--open", type=float, default=30.0)
    return parser.parse_args()


def clamp_float(value: Any, default: float, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(low, min(high, number))


def clamp_int(value: Any, default: int, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(low, min(high, number))


def extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.startswith("json"):
            text = text[4:].strip()
    return json.loads(text)


def ask_chatgpt(client: OpenAI, model: str, request: str, defaults: argparse.Namespace) -> dict[str, Any]:
    instructions = (
        "You are the high-level brain for an SO-101 LeRobot upma cooking project. "
        "You must choose only one safe action from the allowed list. "
        "Never invent raw joint angles, shell commands, filenames, or unlisted actions. "
        "Return only JSON with keys: action, speed_scale, pause, cycles, tight, open, reason. "
        "Use dry_full_upma for validation/no movement. "
        "Use smart_cup_stick_stir when the user wants cup pickup, spoon/stick pickup, tight grasp, and stirring. "
        "Use full_upma_with_ingredients when the user wants the normal upma sequence including ingredients. "
        "Use stop if the request sounds unsafe or unclear."
    )
    state = {
        "user_request": request,
        "allowed_actions": sorted(ALLOWED_ACTIONS),
        "defaults": {
            "speed_scale": defaults.speed_scale,
            "pause": defaults.pause,
            "cycles": defaults.cycles,
            "tight": defaults.tight,
            "open": defaults.open,
        },
        "safety_rules": [
            "Only calibrated pose scripts are allowed.",
            "Use slow speed unless user explicitly asks otherwise.",
            "Tight gripper is lower gripper.pos; -5 is tightest allowed.",
            "No raw joint targets.",
        ],
    }
    response = client.responses.create(
        model=model,
        instructions=instructions,
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": json.dumps(state, indent=2),
                    }
                ],
            }
        ],
    )
    decision = extract_json(response.output_text)
    action = str(decision.get("action", "")).strip()
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"ChatGPT returned disallowed action: {action!r}")
    return {
        "action": action,
        "speed_scale": clamp_float(decision.get("speed_scale"), defaults.speed_scale, 0.01, 0.2),
        "pause": clamp_float(decision.get("pause"), defaults.pause, 0.0, 2.0),
        "cycles": clamp_int(decision.get("cycles"), defaults.cycles, 1, 30),
        "tight": clamp_float(decision.get("tight"), defaults.tight, -5.0, 10.0),
        "open": clamp_float(decision.get("open"), defaults.open, 0.0, 60.0),
        "reason": str(decision.get("reason", "")),
    }


def command_for(decision: dict[str, Any]) -> list[str] | None:
    python_exe = str(PROJECT_PYTHON if PROJECT_PYTHON.exists() else Path(sys.executable))
    speed = str(decision["speed_scale"])
    pause = str(decision["pause"])
    cycles = str(decision["cycles"])
    tight = str(decision["tight"])
    open_value = str(decision["open"])
    action = decision["action"]

    if action == "stop":
        return None
    if action == "dry_full_upma":
        return [python_exe, "upma_mode.py", "--dry-run", "--with-ingredients", "--yes"]
    if action == "full_upma":
        return [
            python_exe,
            "upma_mode.py",
            "--yes",
            "--speed-scale",
            speed,
            "--cycles-multiplier",
            "1",
            "--pause",
            pause,
            "--low-pressure-lift-deg",
            "6",
        ]
    if action == "full_upma_with_ingredients":
        return [
            python_exe,
            "upma_mode.py",
            "--with-ingredients",
            "--yes",
            "--speed-scale",
            speed,
            "--cycles-multiplier",
            "1",
            "--pause",
            pause,
            "--low-pressure-lift-deg",
            "6",
        ]
    if action == "smart_cup_stick_stir":
        return [
            python_exe,
            "smart_upma_runner.py",
            "--yes",
            "--speed-scale",
            speed,
            "--pause",
            pause,
            "--stir-cycles",
            cycles,
            "--tight",
            tight,
            "--open",
            open_value,
        ]
    if action == "ingredients_only":
        return [python_exe, "ingredient_actions.py", "--action", "all", "--speed-scale", speed, "--pause", pause, "--yes"]
    if action == "stir_front_back":
        return [python_exe, "stir_motion.py", "--motion", "front-back", "--cycles", cycles, "--speed-scale", speed, "--yes"]
    if action == "stir_left_right":
        return [python_exe, "stir_motion.py", "--motion", "left-right", "--cycles", cycles, "--speed-scale", speed, "--yes"]
    if action == "grip_down":
        return [python_exe, "grip_down.py", "--speed-scale", speed, "--grip-value", tight, "--pause", pause, "--yes"]
    raise ValueError(f"No command mapping for action: {action}")


def main() -> int:
    args = parse_args()
    request = " ".join(args.request).strip()
    if not request:
        request = input("Robot request: ").strip()
    if not request:
        print("No request provided.")
        return 1
    if not os.environ.get("OPENAI_API_KEY"):
        print("Missing OPENAI_API_KEY environment variable.")
        print('Set it with: $env:OPENAI_API_KEY="your_api_key_here"')
        return 1

    try:
        client = OpenAI()
        decision = ask_chatgpt(client, args.model, request, args)
        command = command_for(decision)
        print("ChatGPT robot brain decision:")
        print(json.dumps(decision, indent=2))
        if command is None:
            print("No robot command will run because ChatGPT chose stop.")
            return 1
        print("Selected command:")
        print(" ".join(command))

        if not args.execute:
            print("Planning only. Add --execute to run real movement.")
            return 0

        print("Executing selected robot command.")
        completed = subprocess.run(command, cwd=ROOT, check=False)
        return int(completed.returncode)
    except KeyboardInterrupt:
        print("\nStopped before completing.")
        return 130
    except Exception as exc:
        print(f"ChatGPT robot brain failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
