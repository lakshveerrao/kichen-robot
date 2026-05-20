from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from robot_api import connect_robot, disconnect_robot, move_to_position, read_current_position


CONFIG_PATH = Path("config.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="No-AI wrist-camera pen pickup for SO-101.")
    parser.add_argument("--camera-index", type=int, default=1)
    parser.add_argument("--seconds", type=float, default=90.0)
    parser.add_argument("--speed-scale", type=float, default=0.01)
    parser.add_argument("--save-dir", default="agent_attempt/no_ai_vision_pickup")
    parser.add_argument("--grip-close", type=float, default=18.0)
    parser.add_argument("--grip-open", type=float, default=42.0)
    parser.add_argument("--place", action="store_true", help="After lifting, pan toward cup side and release.")
    parser.add_argument("--learned-fast", action="store_true", help="Use the learned fast pen pickup routine for this table setup.")
    parser.add_argument("--continuous", action="store_true", help="Continuously check the wrist camera while moving, then pick and place.")
    parser.add_argument("--yes", action="store_true")
    return parser.parse_args()


def load_config() -> dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        config = json.load(f)
    config["robot_port"] = config.get("robot_port") or "COM7"
    return config


def capture(camera_index: int) -> Any | None:
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap.release()
        cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    ok, frame = cap.read()
    cap.release()
    return frame if ok and frame is not None else None


def detect_pen(frame: Any) -> dict[str, float] | None:
    height, width = frame.shape[:2]
    roi = frame[: int(height * 0.9), :]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    # The pen in this workspace is pale blue/white. The table and glare are
    # also bright, so broad color thresholding is followed by strict geometry.
    white = cv2.inRange(hsv, (0, 0, 170), (179, 85, 255))
    pale_blue = cv2.inRange(hsv, (80, 0, 120), (140, 175, 255))
    mask = cv2.bitwise_or(white, pale_blue)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates: list[tuple[float, float, float, float, float, float]] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 800 or area > 14000:
            continue
        (cx, cy), (rw, rh), angle = cv2.minAreaRect(contour)
        long_side = max(rw, rh)
        short_side = max(1.0, min(rw, rh))
        aspect = long_side / short_side
        if aspect < 2.0:
            continue
        if long_side < 70 or long_side > 280:
            continue
        if short_side < 8 or short_side > 90:
            continue
        if cy > 365:
            continue
        # In the learned wrist view, the cup/glare often creates pale contours
        # on the far left. The pen enters from the center/right side.
        if cx < width * 0.42 or cx > width - 25:
            continue
        score = area * aspect - abs(cx - width / 2) * 2.0
        candidates.append((score, cx, cy, long_side, short_side, area))
    if not candidates:
        return detect_pen_line(frame)
    candidates.sort(reverse=True)
    _, cx, cy, long_side, short_side, area = candidates[0]
    return {
        "cx": float(cx),
        "cy": float(cy),
        "long": float(long_side),
        "short": float(short_side),
        "area": float(area),
        "width": float(width),
        "height": float(height),
    }


def detect_pen_line(frame: Any) -> dict[str, float] | None:
    height, width = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=45, minLineLength=70, maxLineGap=15)
    if lines is None:
        return None
    candidates: list[tuple[float, float, float, float, float]] = []
    for line in lines[:, 0, :]:
        x1, y1, x2, y2 = [int(value) for value in line]
        length = float(((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5)
        if length < 75 or length > 260:
            continue
        angle = abs(float(np.degrees(np.arctan2(y2 - y1, x2 - x1))))
        if angle > 90:
            angle = 180 - angle
        if angle < 70:
            continue
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        if cx < 335 or cx > width - 35:
            continue
        if cy < 20 or cy > 430:
            continue

        samples = []
        for fraction in (0.2, 0.4, 0.6, 0.8):
            x = int(x1 + (x2 - x1) * fraction)
            y = int(y1 + (y2 - y1) * fraction)
            if 0 <= x < width and 0 <= y < height:
                samples.append(frame[y, x])
        if not samples:
            continue
        color = np.mean(np.asarray(samples, dtype=np.float32), axis=0)
        # Reject the black gripper pads; keep the pale blue/white pen.
        if float(np.mean(color)) < 125 or float(np.min(color)) < 80:
            continue

        score = length * 2.0 + angle - abs(cx - width / 2.0) * 0.5
        candidates.append((score, cx, cy, length, angle))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    _, cx, cy, length, angle = candidates[0]
    return {
        "cx": float(cx),
        "cy": float(cy),
        "long": float(length),
        "short": 12.0,
        "area": float(length * 12.0),
        "width": float(width),
        "height": float(height),
        "angle": float(angle),
    }


def save_debug(save_dir: Path, step: int, frame: Any, detection: dict[str, float] | None, label: str) -> None:
    image = frame.copy()
    height, width = image.shape[:2]
    cv2.line(image, (width // 2, 0), (width // 2, height), (0, 255, 0), 1)
    cv2.rectangle(image, (250, 300), (390, 470), (255, 0, 0), 2)
    if detection:
        cv2.circle(image, (int(detection["cx"]), int(detection["cy"])), 12, (0, 0, 255), 2)
        cv2.putText(
            image,
            f"x={detection['cx']:.0f} y={detection['cy']:.0f}",
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 255),
            2,
        )
    cv2.imwrite(str(save_dir / f"{step:03d}_{label}.jpg"), image)


def hand_in_view(frame: Any) -> bool:
    ycrcb = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)
    mask = cv2.inRange(ycrcb, (0, 133, 77), (255, 180, 135))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return any(cv2.contourArea(contour) > 14000 for contour in contours)


def move_delta(robot: Any, deltas: dict[str, float], speed_scale: float) -> None:
    current = read_current_position(robot)
    target = dict(current)
    for key, delta in deltas.items():
        target[key] = current[key] + delta
    move_to_position(robot, target, speed_scale)


def learned_fast_pickup(robot: Any, args: argparse.Namespace, save_dir: Path) -> int:
    print("Running learned-fast wrist-camera pickup.")
    current = read_current_position(robot)
    target = dict(current)
    target["gripper.pos"] = args.grip_open
    move_to_position(robot, target, 0.04)
    time.sleep(0.4)

    # These moves are learned from this table/camera setup:
    # pan positive brings the right-side pen toward the jaw center, and lowering
    # shoulder plus wrist-back brings the pen down into the gripper frame.
    routine = [
        ("pan_to_pen", {"shoulder_pan.pos": 8.0}),
        ("lower_to_pen", {"shoulder_lift.pos": -5.0}),
        ("wrist_place_jaws", {"wrist_flex.pos": 5.0}),
    ]
    for step, (label, deltas) in enumerate(routine, 1):
        move_delta(robot, deltas, args.speed_scale)
        time.sleep(0.35)
        frame = capture(args.camera_index)
        if frame is not None:
            save_debug(save_dir, step, frame, detect_pen(frame), label)

    print("Fast light close.")
    current = read_current_position(robot)
    target = dict(current)
    target["gripper.pos"] = args.grip_close
    move_to_position(robot, target, 0.04)
    time.sleep(0.7)
    frame = capture(args.camera_index)
    if frame is not None:
        save_debug(save_dir, 10, frame, detect_pen(frame), "after_close")

    print("Fast lift.")
    move_delta(robot, {"shoulder_lift.pos": 6.0}, args.speed_scale)
    time.sleep(0.8)
    frame = capture(args.camera_index)
    if frame is not None:
        save_debug(save_dir, 11, frame, detect_pen(frame), "after_lift")

    if args.place:
        print("Fast place/release.")
        move_delta(robot, {"shoulder_pan.pos": -20.0}, args.speed_scale)
        time.sleep(0.8)
        current = read_current_position(robot)
        target = dict(current)
        target["gripper.pos"] = args.grip_open
        move_to_position(robot, target, 0.04)
        time.sleep(0.6)
        frame = capture(args.camera_index)
        if frame is not None:
            save_debug(save_dir, 12, frame, detect_pen(frame), "after_release")
    return 0


def continuous_pick_and_place(robot: Any, args: argparse.Namespace, save_dir: Path) -> int:
    print("Running continuous no-AI wrist-camera pick-and-place.")
    print("It checks the camera after every small move and does not use ChatGPT or training.")
    current = read_current_position(robot)
    target = dict(current)
    target["gripper.pos"] = args.grip_open
    move_to_position(robot, target, 0.04)
    time.sleep(0.2)

    start = time.time()
    step = 0
    last_detection: dict[str, float] | None = None
    scan_direction = 1.0

    while time.time() - start < args.seconds:
        step += 1
        frame = capture(args.camera_index)
        if frame is None:
            print(f"{step}: camera read failed")
            time.sleep(0.15)
            continue
        if hand_in_view(frame):
            save_debug(save_dir, step, frame, None, "hand_pause")
            print(f"{step}: hand in wrist camera - pausing")
            time.sleep(0.5)
            continue
        detection = detect_pen(frame)
        save_debug(save_dir, step, frame, detection, "continuous")
        print(f"{step}: detection={detection}")

        if detection is None:
            if last_detection is not None:
                # Keep moving in the last useful direction briefly.
                x_error = last_detection["cx"] - last_detection["width"] / 2.0
                pan_delta = 2.0 if x_error > 0 else -2.0
                move_delta(robot, {"shoulder_pan.pos": pan_delta}, args.speed_scale)
            else:
                move_delta(robot, {"shoulder_pan.pos": 2.5 * scan_direction}, args.speed_scale)
                if step % 5 == 0:
                    scan_direction *= -1.0
                    move_delta(robot, {"wrist_flex.pos": -2.0}, args.speed_scale)
            time.sleep(0.15)
            continue

        last_detection = detection
        cx = detection["cx"]
        cy = detection["cy"]
        width = detection["width"]
        x_error = cx - width / 2.0

        # Learned from real frames:
        # - positive pan moves the right-side pen leftward in the wrist image.
        # - y around 235+ is close enough to close; waiting lower overshoots.
        if abs(x_error) > 45:
            pan_delta = 2.5 if x_error > 0 else -2.5
            move_delta(robot, {"shoulder_pan.pos": pan_delta}, args.speed_scale)
            time.sleep(0.15)
            continue

        if cy < 225:
            move_delta(robot, {"shoulder_lift.pos": -2.0, "wrist_flex.pos": 1.5}, args.speed_scale)
            time.sleep(0.15)
            continue

        print("Pen is in learned jaw zone. Closing while camera continues.")
        current = read_current_position(robot)
        target = dict(current)
        target["gripper.pos"] = args.grip_close
        move_to_position(robot, target, 0.04)
        time.sleep(0.4)
        frame = capture(args.camera_index)
        if frame is not None:
            save_debug(save_dir, step, frame, detect_pen(frame), "after_close")

        print("Lifting.")
        move_delta(robot, {"shoulder_lift.pos": 7.0}, args.speed_scale)
        time.sleep(0.5)
        frame = capture(args.camera_index)
        if frame is not None:
            save_debug(save_dir, step, frame, detect_pen(frame), "after_lift")

        print("Placing toward cup side and releasing.")
        # Cup is on the left side in the learned wrist/table setup.
        for place_step, pan_delta in enumerate((-8.0, -8.0, -6.0), 1):
            move_delta(robot, {"shoulder_pan.pos": pan_delta}, args.speed_scale)
            time.sleep(0.25)
            frame = capture(args.camera_index)
            if frame is not None:
                save_debug(save_dir, step + place_step, frame, detect_pen(frame), f"place_{place_step}")

        current = read_current_position(robot)
        target = dict(current)
        target["gripper.pos"] = args.grip_open
        move_to_position(robot, target, 0.04)
        time.sleep(0.4)
        frame = capture(args.camera_index)
        if frame is not None:
            save_debug(save_dir, step + 10, frame, detect_pen(frame), "after_release")
        print("Continuous pick-and-place done.")
        return 0

    print("Timed out before the pen reached the learned jaw zone.")
    return 1


def main() -> int:
    args = parse_args()
    save_dir = Path(args.save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    if not args.yes:
        input("Keep hands away from the robot. Press Enter to start no-AI vision pickup.")

    robot = None
    try:
        robot = connect_robot(load_config())
        print("No-AI vision pickup connected.")
        print("This uses only the wrist camera and bounded moves.")
        print("Start:", read_current_position(robot))

        if args.continuous:
            return continuous_pick_and_place(robot, args, save_dir)

        if args.learned_fast:
            return learned_fast_pickup(robot, args, save_dir)

        current = read_current_position(robot)
        target = dict(current)
        target["gripper.pos"] = max(current["gripper.pos"], args.grip_open)
        move_to_position(robot, target, 0.03)
        time.sleep(0.5)

        started = time.time()
        step = 0
        scan_direction = 1
        while time.time() - started < args.seconds:
            step += 1
            frame = capture(args.camera_index)
            if frame is None:
                print(f"{step}: camera read failed")
                time.sleep(0.3)
                continue
            detection = detect_pen(frame)
            label = "detect" if detection else "scan"
            save_debug(save_dir, step, frame, detection, label)
            print(f"{step}: detection={detection}")

            if detection is None:
                move_delta(robot, {"shoulder_pan.pos": 2.0 * scan_direction}, args.speed_scale)
                if step % 4 == 0:
                    scan_direction *= -1
                    move_delta(robot, {"wrist_flex.pos": -2.0}, args.speed_scale)
                time.sleep(0.35)
                continue

            cx = detection["cx"]
            cy = detection["cy"]
            width = detection["width"]
            x_error = cx - width / 2.0

            if abs(x_error) > 50:
                # Learned on this setup: positive pan moves the pen left in the wrist view.
                pan_delta = 3.0 if x_error > 0 else -3.0
                move_delta(robot, {"shoulder_pan.pos": pan_delta}, args.speed_scale)
                time.sleep(0.2)
                continue

            # Learned from real wrist-camera frames: when the pen center is
            # roughly y=240..320 and x-centered, the pen is already between the
            # pads enough for a light close. Waiting until y>340 overshoots.
            if cy >= 235:
                print("Pen centered near jaws. Closing lightly.")
                current = read_current_position(robot)
                target = dict(current)
                target["gripper.pos"] = max(10.0, args.grip_close)
                move_to_position(robot, target, 0.03)
                time.sleep(1.0)
                frame = capture(args.camera_index)
                if frame is not None:
                    save_debug(save_dir, step, frame, detect_pen(frame), "after_close")

                print("Lifting.")
                move_delta(robot, {"shoulder_lift.pos": 6.0}, args.speed_scale)
                time.sleep(1.0)
                frame = capture(args.camera_index)
                if frame is not None:
                    save_debug(save_dir, step, frame, detect_pen(frame), "after_lift")

                if args.place:
                    print("Moving toward cup side and releasing.")
                    move_delta(robot, {"shoulder_pan.pos": -18.0}, args.speed_scale)
                    time.sleep(1.0)
                    current = read_current_position(robot)
                    target = dict(current)
                    target["gripper.pos"] = args.grip_open
                    move_to_position(robot, target, 0.03)
                    time.sleep(0.8)
                    frame = capture(args.camera_index)
                    if frame is not None:
                        save_debug(save_dir, step, frame, detect_pen(frame), "after_release")
                print("Done.")
                return 0

            if cy < 220:
                move_delta(robot, {"shoulder_lift.pos": -2.5, "wrist_flex.pos": 2.0}, args.speed_scale)
                time.sleep(0.2)
                continue

            if cy < 240:
                move_delta(robot, {"shoulder_lift.pos": -1.5}, args.speed_scale)
                time.sleep(0.2)
                continue

        print("Timed out before pen reached the jaw zone.")
        return 1
    except KeyboardInterrupt:
        print("Stopped by user.")
        return 130
    except Exception as exc:
        print(f"No-AI vision pickup failed: {exc}")
        return 1
    finally:
        disconnect_robot(robot)
        print(f"Disconnected. Debug frames: {save_dir}")


if __name__ == "__main__":
    raise SystemExit(main())
