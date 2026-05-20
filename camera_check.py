from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


CONFIG_PATH = Path("config.json")


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check OpenCV cameras 0 and 1.")
    parser.add_argument("--indices", nargs="+", type=int, default=None, help="Camera indices to check.")
    parser.add_argument("--save", action="store_true", help="Save one snapshot per camera.")
    parser.add_argument("--preview", action="store_true", help="Show live preview windows. Press q to quit.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not CONFIG_PATH.exists():
        print("Missing config.json.")
        return 1

    try:
        import cv2
    except ImportError:
        print("OpenCV is not installed. Install LeRobot requirements first.")
        return 1

    config = load_json(CONFIG_PATH)
    indices = args.indices if args.indices is not None else config.get("camera_indices", [0, 1])
    width = int(config.get("camera_width", 640))
    height = int(config.get("camera_height", 480))
    fps = int(config.get("camera_fps", 30))

    cameras = []
    try:
        for index in indices:
            cap = cv2.VideoCapture(int(index), cv2.CAP_DSHOW)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            cap.set(cv2.CAP_PROP_FPS, fps)

            if not cap.isOpened():
                print(f"Camera {index}: FAILED to open")
                cap.release()
                continue

            time.sleep(0.25)
            ok, frame = cap.read()
            if not ok or frame is None:
                print(f"Camera {index}: opened but FAILED to read frame")
                cap.release()
                continue

            actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = cap.get(cv2.CAP_PROP_FPS)
            print(f"Camera {index}: OK frame={frame.shape} capture={actual_width}x{actual_height} fps={actual_fps}")

            if args.save:
                out = Path(f"camera_{index}_snapshot.jpg")
                cv2.imwrite(str(out), frame)
                print(f"Camera {index}: saved {out}")

            cameras.append((index, cap))

        if args.preview and cameras:
            print("Preview open. Press q to quit.")
            while True:
                for index, cap in cameras:
                    ok, frame = cap.read()
                    if ok and frame is not None:
                        cv2.imshow(f"camera_{index}", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
        return 0 if cameras else 1
    finally:
        for _, cap in cameras:
            cap.release()
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
