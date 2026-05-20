from __future__ import annotations

import argparse
import json
import time
from collections.abc import Iterable
from dataclasses import dataclass
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
PAN_JOINT = "shoulder_pan.pos"
LIFT_JOINT = "shoulder_lift.pos"
HIGH_CLEARANCE_POSES = {"ABOVE_BOWL", "LIFT"}
LOW_PRESSURE_POSES = {"STIR_DEPTH", "STIR_FORWARD", "STIR_BACK", "STIR_LEFT", "STIR_RIGHT"}
INGREDIENT_POSES = {
    "CUP_APPROACH",
    "CUP_GRASP",
    "CUP_LIFT",
    "CUP_POUR",
    "CUP_PLACE",
    "CUP_RELEASE",
    "STIRRER_APPROACH",
    "STIRRER_GRASP",
    "STIRRER_LIFT",
    "STIRRER_READY",
}
PAN_BOUNDARY_POSES = {
    "ABOVE_BOWL",
    "STIR_DEPTH",
    "LIFT",
    "STIR_FORWARD",
    "STIR_BACK",
    "STIR_LEFT",
    "STIR_RIGHT",
}


@dataclass(frozen=True)
class UpmaStep:
    name: str
    instruction: str
    sequence: tuple[str, ...]
    cycles: int = 1
    pause_seconds: float = 0.4


UPMA_STEPS = (
    UpmaStep(
        name="warm_pan",
        instruction="Warm the pan. Add oil or ghee, mustard seeds, urad dal, chana dal, curry leaves, green chilli, ginger, and onion.",
        sequence=("ABOVE_BOWL", "STIR_DEPTH", "LIFT"),
        cycles=1,
    ),
    UpmaStep(
        name="roast_rava",
        instruction="Add roasted rava slowly around the bowl area.",
        sequence=("STIR_FORWARD", "STIR_BACK"),
        cycles=4,
        pause_seconds=0.25,
    ),
    UpmaStep(
        name="add_water",
        instruction="Add hot water and salt slowly. Keep the robot away from steam while pouring.",
        sequence=("LIFT", "STIR_LEFT", "STIR_RIGHT"),
        cycles=2,
        pause_seconds=0.35,
    ),
    UpmaStep(
        name="cook_and_mix",
        instruction="Let the rava thicken, then keep mixing until there are no dry pockets.",
        sequence=("STIR_FORWARD", "STIR_BACK", "STIR_LEFT", "STIR_RIGHT"),
        cycles=5,
        pause_seconds=0.25,
    ),
    UpmaStep(
        name="finish",
        instruction="Add lemon, coriander, and optional cashews. Lift and park the arm.",
        sequence=("LIFT", "PARK"),
        cycles=1,
        pause_seconds=0.5,
    ),
)

INGREDIENT_STEPS = (
    UpmaStep(
        name="pick_up_cup",
        instruction="Pick up the ingredient cup from its calibrated pickup location.",
        sequence=("CUP_APPROACH", "CUP_GRASP", "CUP_LIFT"),
        cycles=1,
        pause_seconds=0.4,
    ),
    UpmaStep(
        name="pour_cup",
        instruction="Move the cup to the pan and pour the ingredient.",
        sequence=("CUP_POUR", "CUP_LIFT", "CUP_PLACE", "CUP_RELEASE"),
        cycles=1,
        pause_seconds=0.5,
    ),
    UpmaStep(
        name="pick_up_stirrer",
        instruction="Pick up the stirrer from the side holder and move to the ready pose.",
        sequence=("STIRRER_APPROACH", "STIRRER_GRASP", "STIRRER_LIFT", "STIRRER_READY"),
        cycles=1,
        pause_seconds=0.4,
    ),
)


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Guided LeRobot SO-101 upma-making sequence.")
    parser.add_argument("--dry-run", action="store_true", help="Print the upma sequence without connecting to the robot.")
    parser.add_argument("--yes", action="store_true", help="Do not wait for Enter before each stage.")
    parser.add_argument("--speed-scale", type=float, default=None, help="Override config speed_scale.")
    parser.add_argument("--pause", type=float, default=None, help="Override the per-pose pause in seconds.")
    parser.add_argument("--cycles-multiplier", type=float, default=1.0, help="Scale stirring cycle counts from 0.25 to 3.0.")
    parser.add_argument("--lift-clearance-deg", type=float, default=None, help="Raise travel poses by this many shoulder-lift degrees.")
    parser.add_argument("--low-pressure-lift-deg", type=float, default=None, help="Raise stirring/contact poses by this many shoulder-lift degrees.")
    parser.add_argument("--with-ingredients", action="store_true", help="Pick up cup, pour, pick up side stirrer, then mix.")
    parser.add_argument("--skip-camera-boundary-check", action="store_true", help="Do not require the two-camera pan boundary check before real movement.")
    parser.add_argument("--hold-at-end", action="store_true", help="Keep torque on at the end instead of stopping.")
    return parser.parse_args()


def active_steps(with_ingredients: bool) -> tuple[UpmaStep, ...]:
    return INGREDIENT_STEPS + UPMA_STEPS if with_ingredients else UPMA_STEPS


def load_positions(config: dict, steps: tuple[UpmaStep, ...]) -> dict[str, dict[str, float]]:
    positions_path = Path(config.get("positions_file", "positions.json"))
    raw_positions = load_json(positions_path)
    needed = sorted({pose for step in steps for pose in step.sequence})
    positions: dict[str, dict[str, float]] = {}
    for name in needed:
        if name not in raw_positions or raw_positions[name] is None:
            raise RobotApiError(f"Position {name!r} is missing or null in {positions_path}.")
        positions[name] = validate_position(raw_positions[name])
    return positions


def pan_bounds(config: dict) -> tuple[float, float]:
    bounds = config.get("upma_pan_bounds_degrees", {})
    return (
        float(bounds.get("shoulder_pan_min", -25.0)),
        float(bounds.get("shoulder_pan_max", 20.0)),
    )


def apply_high_clearance(
    positions: dict[str, dict[str, float]],
    clearance_degrees: float,
) -> dict[str, dict[str, float]]:
    adjusted = {name: dict(position) for name, position in positions.items()}
    if clearance_degrees <= 0:
        return adjusted
    for name in HIGH_CLEARANCE_POSES:
        if name in adjusted and LIFT_JOINT in adjusted[name]:
            # On this SO-101 setup, more negative shoulder_lift raises the arm.
            adjusted[name][LIFT_JOINT] -= clearance_degrees
    return adjusted


def apply_low_pressure(
    positions: dict[str, dict[str, float]],
    lift_degrees: float,
) -> dict[str, dict[str, float]]:
    adjusted = {name: dict(position) for name, position in positions.items()}
    if lift_degrees <= 0:
        return adjusted
    for name in LOW_PRESSURE_POSES:
        if name in adjusted and LIFT_JOINT in adjusted[name]:
            # On this SO-101 setup, more negative shoulder_lift raises the arm,
            # reducing pan contact pressure when no force sensor is available.
            adjusted[name][LIFT_JOINT] -= lift_degrees
    return adjusted


def validate_pan_boundaries(positions: dict[str, dict[str, float]], config: dict) -> None:
    lower, upper = pan_bounds(config)
    if lower >= upper:
        raise RobotApiError("Invalid upma pan boundaries: shoulder_pan_min must be below shoulder_pan_max.")

    for name, position in positions.items():
        if name not in PAN_BOUNDARY_POSES:
            continue
        pan = position.get(PAN_JOINT)
        if pan is None:
            continue
        if pan < lower or pan > upper:
            raise RobotApiError(
                f"Position {name} has {PAN_JOINT}={pan:.2f}, outside pan boundary {lower:.2f}..{upper:.2f}."
            )
    print(f"Pan boundary OK: {PAN_JOINT} stays inside {lower:.2f}..{upper:.2f} degrees.")


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


def central_roi(frame: Any, roi: tuple[int, int, int, int] | None):
    h, w = frame.shape[:2]
    if roi is None:
        x = int(w * 0.18)
        y = int(h * 0.18)
        rw = int(w * 0.64)
        rh = int(h * 0.64)
    else:
        x, y, rw, rh = roi
    x = max(0, min(int(x), w - 1))
    y = max(0, min(int(y), h - 1))
    rw = max(1, min(int(rw), w - x))
    rh = max(1, min(int(rh), h - y))
    return x, y, rw, rh


def camera_boundary_check(config: dict) -> None:
    try:
        import cv2
    except ImportError as exc:
        raise RobotApiError("OpenCV is required for the two-camera pan boundary check.") from exc

    indices = [int(index) for index in config.get("camera_indices", [0, 1])]
    if len(indices) < 2:
        raise RobotApiError("Two camera indices are required for upma boundary checking.")

    width = int(config.get("camera_width", 640))
    height = int(config.get("camera_height", 480))
    fps = int(config.get("camera_fps", 30))
    roi_config = config.get("upma_camera_roi")
    roi = tuple(int(value) for value in roi_config) if isinstance(roi_config, list) and len(roi_config) == 4 else None
    min_edge_score = float(config.get("upma_camera_min_edge_score", 2.0))
    min_brightness = float(config.get("upma_camera_min_brightness", 8.0))
    max_brightness = float(config.get("upma_camera_max_brightness", 245.0))

    cameras = []
    try:
        for index in indices[:2]:
            cap = open_camera(cv2, index, width, height, fps)
            if cap is None:
                raise RobotApiError(f"Camera {index} failed to open for pan boundary check.")
            cameras.append((index, cap))

        for index, cap in cameras:
            time.sleep(0.15)
            ok, frame = cap.read()
            if not ok or frame is None:
                raise RobotApiError(f"Camera {index} opened but did not return a frame.")
            x, y, rw, rh = central_roi(frame, roi)
            crop = frame[y : y + rh, x : x + rw]
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            brightness = float(gray.mean())
            edges = cv2.Canny(gray, 60, 140)
            edge_score = float(edges.mean())
            if brightness < min_brightness or brightness > max_brightness:
                raise RobotApiError(
                    f"Camera {index} pan ROI brightness {brightness:.1f} is outside {min_brightness:.1f}..{max_brightness:.1f}."
                )
            if edge_score < min_edge_score:
                raise RobotApiError(
                    f"Camera {index} pan ROI edge score {edge_score:.2f} is below {min_edge_score:.2f}; pan boundary view may be blocked."
                )
            print(f"Camera {index} boundary OK: roi=({x},{y},{rw},{rh}) brightness={brightness:.1f} edge={edge_score:.2f}")
        print("Two-camera pan boundary check OK.")
    finally:
        for _, cap in cameras:
            cap.release()
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass


def iter_stage_poses(step: UpmaStep, cycles_multiplier: float) -> Iterable[str]:
    cycles = max(1, round(step.cycles * cycles_multiplier))
    for _ in range(cycles):
        yield from step.sequence


def wait_for_stage(args: argparse.Namespace, step: UpmaStep) -> None:
    print()
    print(f"Stage: {step.name}")
    print(step.instruction)
    if not args.yes:
        input("Press Enter when the pan is ready for this stage, or Ctrl+C to stop.")


def main() -> int:
    args = parse_args()
    if not 0.25 <= args.cycles_multiplier <= 3.0:
        print("--cycles-multiplier must be between 0.25 and 3.0.")
        return 1
    if args.pause is not None and not 0 <= args.pause <= 10:
        print("--pause must be between 0 and 10 seconds.")
        return 1
    if not CONFIG_PATH.exists():
        print("Missing config.json. Copy config.example.json to config.json and edit robot_port.")
        return 1

    robot = None
    try:
        config = load_json(CONFIG_PATH)
        steps = active_steps(args.with_ingredients)
        clearance_degrees = (
            args.lift_clearance_deg
            if args.lift_clearance_deg is not None
            else float(config.get("upma_lift_clearance_degrees", 10.0))
        )
        low_pressure_degrees = (
            args.low_pressure_lift_deg
            if args.low_pressure_lift_deg is not None
            else float(config.get("upma_low_pressure_lift_degrees", 6.0))
        )
        positions = {}
        if not args.dry_run:
            positions = load_positions(config, steps)
            positions = apply_high_clearance(positions, clearance_degrees)
            positions = apply_low_pressure(positions, low_pressure_degrees)
            validate_pan_boundaries(positions, config)
        speed_scale = args.speed_scale if args.speed_scale is not None else config.get("speed_scale", DEFAULT_SPEED_SCALE)

        print("SO-101 LeRobot Upma Mode")
        print("Dataset reference: https://huggingface.co/datasets/lakshveeer/robot")
        print("This sequence stirs and parks the arm. A human must add ingredients and control the stove.")
        if args.with_ingredients:
            print("Ingredient handling is enabled: cup pickup, pour/place, side stirrer pickup, then mixing.")
        print("Keep one hand near the robot power switch. Press Ctrl+C to stop.")
        print(
            f"speed_scale={speed_scale}, cycles_multiplier={args.cycles_multiplier}, "
            f"lift_clearance_deg={clearance_degrees}, low_pressure_lift_deg={low_pressure_degrees}"
        )

        if args.dry_run:
            print("Dry run only. No robot connection or movement will happen.")
        else:
            if not args.skip_camera_boundary_check and config.get("upma_camera_boundary_check", True):
                camera_boundary_check(config)
            if not args.yes:
                input("Press Enter to connect to the SO-101 follower, or Ctrl+C to cancel.")
            print(f"Connecting to SO-101 follower on {config.get('robot_port')}...")
            robot = connect_robot(config)
            print("Robot connected.")

        for step in steps:
            wait_for_stage(args, step)
            for pose_name in iter_stage_poses(step, args.cycles_multiplier):
                print(f"Moving to {pose_name}")
                if not args.dry_run:
                    move_to_position(robot, positions[pose_name], speed_scale)
                pause = args.pause if args.pause is not None else step.pause_seconds
                time.sleep(pause)

        if not args.hold_at_end:
            print("Stopping robot at end.")
            stop_robot(robot)
        print("Upma mode complete.")
        return 0
    except KeyboardInterrupt:
        print("\nStop requested. Stopping robot now.")
        stop_robot(robot)
        return 130
    except Exception as exc:
        print(f"Upma mode failed: {exc}")
        return 1
    finally:
        disconnect_robot(robot)
        print("Disconnected.")


if __name__ == "__main__":
    raise SystemExit(main())
