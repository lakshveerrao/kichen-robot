from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class CameraFrame:
    index: int
    timestamp: float
    frame: Any
    frames_read: int


def import_cv2():
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("OpenCV is not installed.") from exc
    return cv2


def discover_cameras(max_index: int = 10, width: int = 640, height: int = 480) -> list[int]:
    cv2 = import_cv2()
    found: list[int] = []
    for index in range(max_index + 1):
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(index)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            ok, frame = cap.read()
            if ok and frame is not None:
                found.append(index)
        cap.release()
    return found


def parse_camera_selection(text: str, available: list[int]) -> list[int]:
    text = text.strip()
    if not text:
        return available[:1]
    values = text.replace(",", " ").split()
    selected = []
    for value in values:
        index = int(value)
        if index not in available:
            raise ValueError(f"Camera {index} is not available. Available: {available}")
        selected.append(index)
    return selected


def choose_cameras(mode: str, configured: list[int], width: int, height: int) -> list[int]:
    if mode == "no":
        return []
    if mode == "yes":
        return configured

    answer = input("Would you like to setup cameras? [y/n] (n): ").strip().lower()
    if answer not in {"y", "yes"}:
        return []
    print("Searching for OpenCV cameras...")
    available = discover_cameras(width=width, height=height)
    if not available:
        print("No OpenCV cameras found.")
        return []
    print(f"Found {len(available)} OpenCV cameras: {available}")
    selected_text = input(f"Select cameras, separated by spaces or commas ({available[0]}): ")
    selected = parse_camera_selection(selected_text, available)
    print("Selected cameras:")
    for index in selected:
        print(f"  Camera #{index}")
    return selected


class BackgroundCameraSet:
    def __init__(self, indices: list[int], width: int, height: int, fps: float, save_dir: Path | None = None) -> None:
        self.indices = indices
        self.width = width
        self.height = height
        self.fps = fps
        self.save_dir = save_dir
        self.lock = threading.Lock()
        self.frames: dict[int, CameraFrame] = {}
        self.errors: dict[int, str] = {}
        self.stop_event = threading.Event()
        self.threads: list[threading.Thread] = []
        self.cv2 = import_cv2() if indices else None

    def start(self) -> None:
        if not self.indices:
            return
        if self.save_dir is not None:
            self.save_dir.mkdir(parents=True, exist_ok=True)
        for index in self.indices:
            thread = threading.Thread(target=self._reader, args=(index,), daemon=True)
            thread.start()
            self.threads.append(thread)

    def _reader(self, index: int) -> None:
        assert self.cv2 is not None
        cv2 = self.cv2
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)
        if not cap.isOpened():
            with self.lock:
                self.errors[index] = "failed to open"
            return
        frames_read = 0
        interval = 1.0 / max(self.fps, 1.0)
        try:
            while not self.stop_event.is_set():
                started = time.perf_counter()
                ok, frame = cap.read()
                if ok and frame is not None:
                    frames_read += 1
                    with self.lock:
                        self.frames[index] = CameraFrame(index, time.time(), frame, frames_read)
                        self.errors.pop(index, None)
                    if self.save_dir is not None and frames_read % max(1, int(self.fps)) == 0:
                        cv2.imwrite(str(self.save_dir / f"camera_{index}_latest.jpg"), frame)
                else:
                    with self.lock:
                        self.errors[index] = "read failed"
                sleep_time = interval - (time.perf_counter() - started)
                if sleep_time > 0:
                    time.sleep(sleep_time)
        finally:
            cap.release()

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "cameras": {
                    str(index): {
                        "frames_read": frame.frames_read,
                        "age_seconds": round(time.time() - frame.timestamp, 3),
                    }
                    for index, frame in self.frames.items()
                },
                "errors": dict(self.errors),
            }

    def stop(self) -> None:
        self.stop_event.set()
        for thread in self.threads:
            thread.join(timeout=1.0)

