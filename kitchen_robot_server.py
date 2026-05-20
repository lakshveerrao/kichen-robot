from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
LOG_LIMIT = 400
DATASET_URL = "https://huggingface.co/datasets/lakshveeer/robot"
PROJECT_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
CONFIG_PATH = ROOT / "config.json"
CAMERA_RESTART_SECONDS = 1.0


def load_config() -> dict[str, Any]:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


class CameraCache:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.frames: dict[int, bytes] = {}
        self.errors: dict[int, str] = {}
        self.started: set[int] = set()

    def start_from_config(self) -> None:
        config = load_config()
        for index in config.get("camera_indices", [1, 2]):
            self.start(int(index))

    def start(self, index: int) -> None:
        with self.lock:
            if index in self.started:
                return
            self.started.add(index)
        thread = threading.Thread(target=self._reader_loop, args=(index,), daemon=True)
        thread.start()

    def get(self, index: int) -> bytes:
        self.start(index)
        deadline = time.time() + 3.0
        while time.time() < deadline:
            with self.lock:
                frame = self.frames.get(index)
                error = self.errors.get(index)
            if frame is not None:
                return frame
            if error:
                time.sleep(0.15)
            else:
                time.sleep(0.05)
        with self.lock:
            error = self.errors.get(index, "no frame available yet")
        raise RuntimeError(f"Camera {index}: {error}")

    def _reader_loop(self, index: int) -> None:
        try:
            import cv2
        except ImportError as exc:
            with self.lock:
                self.errors[index] = f"OpenCV is not installed: {exc}"
            return

        config = load_config()
        width = int(config.get("camera_width", 640))
        height = int(config.get("camera_height", 480))
        fps = int(config.get("camera_fps", 30))

        while True:
            cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap.release()
                cap = cv2.VideoCapture(index)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            cap.set(cv2.CAP_PROP_FPS, fps)
            if hasattr(cv2, "CAP_PROP_AUTOFOCUS"):
                cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)

            if not cap.isOpened():
                with self.lock:
                    self.errors[index] = "failed to open"
                cap.release()
                time.sleep(CAMERA_RESTART_SECONDS)
                continue

            with self.lock:
                self.errors.pop(index, None)

            try:
                while True:
                    ok, frame = cap.read()
                    if not ok or frame is None:
                        with self.lock:
                            self.errors[index] = "failed to read frame"
                        break

                    ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
                    if ok:
                        with self.lock:
                            self.frames[index] = encoded.tobytes()
                            self.errors.pop(index, None)
                    time.sleep(0.08)
            finally:
                cap.release()
                time.sleep(CAMERA_RESTART_SECONDS)


class RobotRun:
    def __init__(self) -> None:
        self.process: subprocess.Popen[str] | None = None
        self.lines: list[str] = []
        self.started_at: float | None = None
        self.command: list[str] = []
        self.lock = threading.Lock()

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            running = self.process is not None and self.process.poll() is None
            return {
                "running": running,
                "returncode": None if self.process is None else self.process.poll(),
                "started_at": self.started_at,
                "command": self.command,
                "log": self.lines[-LOG_LIMIT:],
            }

    def start(self, command: list[str]) -> None:
        with self.lock:
            if self.process is not None and self.process.poll() is None:
                raise RuntimeError("A robot run is already active.")
            self.lines = []
            self.started_at = time.time()
            self.command = command
            self.process = subprocess.Popen(
                command,
                cwd=ROOT,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            if self.process.stdin is not None:
                self.process.stdin.write("\n")
                self.process.stdin.flush()
            threading.Thread(target=self._read_output, daemon=True).start()

    def stop(self) -> None:
        with self.lock:
            process = self.process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        with self.lock:
            self.lines.append("Stop requested from localhost dashboard.")

    def _read_output(self) -> None:
        process = self.process
        if process is None or process.stdout is None:
            return
        for line in process.stdout:
            with self.lock:
                self.lines.append(line.rstrip())
                if len(self.lines) > LOG_LIMIT:
                    self.lines = self.lines[-LOG_LIMIT:]
        process.wait()
        with self.lock:
            self.lines.append(f"Process exited with code {process.returncode}.")


RUN = RobotRun()
CAMERAS = CameraCache()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Localhost dashboard for the SO-101 kitchen robot.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--allow-movement",
        action="store_true",
        help="Allow the dashboard to start real robot movement. Without this, only dry runs are allowed.",
    )
    return parser.parse_args()


def read_request_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    return json.loads(raw.decode("utf-8"))


def make_command(payload: dict[str, Any], allow_movement: bool) -> list[str]:
    dry_run = bool(payload.get("dry_run", True))
    if not dry_run and not allow_movement:
        raise RuntimeError("Server was started without --allow-movement, so real robot movement is blocked.")
    if not dry_run:
        require_cached_camera_frames()

    python_exe = PROJECT_PYTHON if PROJECT_PYTHON.exists() else Path(sys.executable)
    command = [str(python_exe), "-u", "upma_mode.py", "--yes"]
    if not dry_run:
        command.append("--skip-camera-boundary-check")
    if dry_run:
        command.append("--dry-run")
    if payload.get("cycles_multiplier") is not None:
        command.extend(["--cycles-multiplier", str(payload["cycles_multiplier"])])
    if payload.get("speed_scale") not in (None, ""):
        command.extend(["--speed-scale", str(payload["speed_scale"])])
    if payload.get("pause") not in (None, ""):
        command.extend(["--pause", str(payload["pause"])])
    if payload.get("low_pressure_lift") not in (None, ""):
        command.extend(["--low-pressure-lift-deg", str(payload["low_pressure_lift"])])
    if payload.get("with_ingredients"):
        command.append("--with-ingredients")
    return command


def make_agent_command(payload: dict[str, Any], allow_movement: bool) -> list[str]:
    request = str(payload.get("request", "")).strip()
    if not request:
        raise RuntimeError("Enter a request for the automatic agent.")
    execute = bool(payload.get("execute", False))
    if execute and not allow_movement:
        raise RuntimeError("Server was started without --allow-movement, so automatic movement is blocked.")
    if execute:
        require_cached_camera_frames()

    python_exe = PROJECT_PYTHON if PROJECT_PYTHON.exists() else Path(sys.executable)
    command = [str(python_exe), "-u", "automatic_agent_controller.py", request]
    if execute:
        command.append("--execute")
    else:
        command.append("--dry-run-command")
    if payload.get("speed_scale") not in (None, ""):
        command.extend(["--speed-scale", str(payload["speed_scale"])])
    if payload.get("pause") not in (None, ""):
        command.extend(["--pause", str(payload["pause"])])
    return command


def require_cached_camera_frames() -> None:
    config = load_config()
    indices = [int(index) for index in config.get("camera_indices", [1, 2])]
    if len(indices) < 2:
        raise RuntimeError("Two camera indices are required before real movement.")
    checked = []
    for index in indices[:2]:
        frame = CAMERAS.get(index)
        if len(frame) < 1000:
            raise RuntimeError(f"Camera {index} returned an invalid small frame.")
        checked.append(index)
    print(f"Dashboard camera boundary check OK using cached frames from cameras {checked}.")


def page_html(allow_movement: bool) -> str:
    movement_note = "Real movement enabled for this server." if allow_movement else "Dry-run locked. Restart with --allow-movement for real robot motion."
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SO-101 Upma Robot</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f4ed;
      --ink: #202124;
      --muted: #62666d;
      --line: #d9d2c3;
      --accent: #0f766e;
      --accent-dark: #0b5f59;
      --danger: #b42318;
      --panel: #ffffff;
      --warm: #d97706;
      --blue: #2563eb;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      background: var(--bg);
      color: var(--ink);
    }}
    header {{
      padding: 22px 28px 16px;
      border-bottom: 1px solid var(--line);
      background: #fffaf0;
    }}
    main {{
      display: grid;
      grid-template-columns: minmax(280px, 380px) 1fr;
      gap: 18px;
      padding: 18px;
      max-width: 1180px;
      margin: 0 auto;
    }}
    h1 {{ margin: 0 0 6px; font-size: 28px; }}
    h2 {{ margin: 0 0 12px; font-size: 17px; }}
    p {{ margin: 0; color: var(--muted); line-height: 1.45; }}
    a {{ color: var(--accent-dark); }}
    section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }}
    .status {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin-top: 12px;
      font-weight: 700;
    }}
    .dot {{
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: #7a7f87;
    }}
    .dot.running {{ background: var(--warm); }}
    .dot.done {{ background: var(--accent); }}
    label {{
      display: grid;
      gap: 6px;
      margin: 12px 0;
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
    }}
    input, select {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      font-size: 15px;
      background: white;
      color: var(--ink);
    }}
    .check-row {{
      grid-template-columns: 20px 1fr;
      align-items: center;
      gap: 8px;
      color: var(--ink);
      font-size: 14px;
    }}
    .check-row input {{
      width: 18px;
      height: 18px;
      padding: 0;
    }}
    .buttons {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-top: 14px;
    }}
    .camera-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }}
    .camera {{
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      background: #111827;
    }}
    .camera b {{
      display: block;
      padding: 8px 10px;
      background: #fffaf0;
      color: var(--ink);
      font-size: 13px;
    }}
    .camera img {{
      display: block;
      width: 100%;
      aspect-ratio: 4 / 3;
      object-fit: contain;
      background: #111827;
    }}
    button {{
      border: 0;
      border-radius: 6px;
      padding: 11px 12px;
      font-weight: 700;
      cursor: pointer;
      background: var(--accent);
      color: white;
    }}
    button:hover {{ background: var(--accent-dark); }}
    button.secondary {{ background: #334155; }}
    button.agent {{ background: var(--blue); }}
    button.danger {{ background: var(--danger); }}
    button:disabled {{ opacity: 0.55; cursor: not-allowed; }}
    ol {{
      margin: 0;
      padding-left: 21px;
      line-height: 1.55;
    }}
    pre {{
      min-height: 360px;
      max-height: 560px;
      overflow: auto;
      margin: 0;
      padding: 14px;
      border-radius: 6px;
      background: #101418;
      color: #d6f3e9;
      font-size: 13px;
      line-height: 1.45;
      white-space: pre-wrap;
    }}
    .wide {{ display: grid; gap: 18px; }}
    .agent-bar {{
      display: grid;
      grid-template-columns: 1fr auto auto;
      gap: 10px;
      align-items: end;
    }}
    .agent-bar label {{ margin: 0; }}
    .agent-toggle {{
      min-width: 128px;
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      font-weight: 700;
      color: var(--ink);
    }}
    .agent-toggle input {{ width: 18px; height: 18px; }}
    @media (max-width: 820px) {{
      main {{ grid-template-columns: 1fr; padding: 12px; }}
      header {{ padding: 18px 14px; }}
      .camera-grid {{ grid-template-columns: 1fr; }}
      .agent-bar {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>SO-101 Kitchen Robot: Upma Mode</h1>
    <p>LeRobot arm control with guided ingredient stages. Dataset reference: <a href="{DATASET_URL}" target="_blank" rel="noreferrer">lakshveeer/robot</a>.</p>
    <div class="status"><span id="dot" class="dot"></span><span id="statusText">{movement_note}</span></div>
  </header>
  <main>
    <section>
      <h2>Run Control</h2>
      <label>Mode
        <select id="dryRun">
          <option value="true">Dry run</option>
          <option value="false">Move robot</option>
        </select>
      </label>
      <label>Speed scale
        <input id="speedScale" type="number" min="0.01" max="10" step="0.01" placeholder="Use config.json">
      </label>
      <label>Stir cycles multiplier
        <input id="cycles" type="number" min="0.25" max="3" step="0.25" value="1">
      </label>
      <label>Pause seconds
        <input id="pause" type="number" min="0" max="10" step="0.05" placeholder="Use stage default">
      </label>
      <label>Low pressure lift
        <input id="lowPressure" type="number" min="0" max="25" step="0.5" value="6">
      </label>
      <label class="check-row">
        <input id="withIngredients" type="checkbox">
        <span>Pick cup and side stirrer first</span>
      </label>
      <div class="buttons">
        <button id="startBtn">Start Upma</button>
        <button id="stopBtn" class="danger">Stop</button>
      </div>
    </section>
    <div class="wide">
    <section>
      <h2>Automatic Agent Controller</h2>
      <div class="agent-bar">
        <label>What should I do for you?
          <input id="agentRequest" type="text" placeholder="pick up the pen and place it in the cup">
        </label>
        <label class="agent-toggle">
          <input id="agentExecute" type="checkbox">
          <span>Move robot</span>
        </label>
        <button id="agentBtn" class="agent">Ask Agent</button>
      </div>
      <p style="margin-top:10px">The agent uses camera frames and ChatGPT, then selects a bounded local robot command. Pen-to-cup requires saved poses: PEN_APPROACH, PEN_GRASP, PEN_LIFT, CUP_TARGET, PEN_RELEASE, PEN_RETREAT.</p>
    </section>
    <section>
      <h2>Ingredient Timeline</h2>
        <ol>
          <li>Optional: pick the ingredient cup, pour it, pick the side stirrer, then move to ready.</li>
          <li>Warm pan, then add oil or ghee, mustard seeds, dals, curry leaves, chilli, ginger, and onion.</li>
          <li>Add roasted rava while the arm uses front and back stirring.</li>
          <li>Add hot water and salt slowly while the arm lifts and mixes side to side.</li>
          <li>Cook and mix until the upma thickens and no dry pockets remain.</li>
          <li>Add lemon, coriander, and optional cashews, then park the robot.</li>
        </ol>
      </section>
      <section>
        <h2>Cameras</h2>
        <div class="camera-grid">
          <div class="camera"><b>Camera 1</b><img id="cam0" alt="Camera 1 view"></div>
          <div class="camera"><b>Camera 2</b><img id="cam1" alt="Camera 2 view"></div>
        </div>
      </section>
      <section>
        <h2>Robot Log</h2>
        <pre id="log">Waiting for command...</pre>
      </section>
    </div>
  </main>
  <script>
    const logEl = document.getElementById("log");
    const statusText = document.getElementById("statusText");
    const dot = document.getElementById("dot");
    const startBtn = document.getElementById("startBtn");
    const stopBtn = document.getElementById("stopBtn");
    const agentBtn = document.getElementById("agentBtn");

    function payload() {{
      return {{
        dry_run: document.getElementById("dryRun").value === "true",
        speed_scale: document.getElementById("speedScale").value,
        cycles_multiplier: document.getElementById("cycles").value,
        pause: document.getElementById("pause").value,
        low_pressure_lift: document.getElementById("lowPressure").value,
        with_ingredients: document.getElementById("withIngredients").checked
      }};
    }}

    async function post(path, body) {{
      const res = await fetch(path, {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify(body || {{}})
      }});
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Request failed");
      return data;
    }}

    async function refresh() {{
      const res = await fetch("/api/status");
      const data = await res.json();
      logEl.textContent = data.log.length ? data.log.join("\\n") : "Waiting for command...";
      startBtn.disabled = data.running;
      stopBtn.disabled = !data.running;
      dot.className = "dot " + (data.running ? "running" : data.returncode === 0 ? "done" : "");
      statusText.textContent = data.running ? "Running" : data.returncode === null ? "{movement_note}" : "Last run exited with code " + data.returncode;
      logEl.scrollTop = logEl.scrollHeight;
    }}

    startBtn.addEventListener("click", async () => {{
      try {{
        await post("/api/run-upma", payload());
        await refresh();
      }} catch (err) {{
        alert(err.message);
      }}
    }});

    agentBtn.addEventListener("click", async () => {{
      try {{
        await post("/api/agent", {{
          request: document.getElementById("agentRequest").value,
          execute: document.getElementById("agentExecute").checked,
          speed_scale: document.getElementById("speedScale").value || "0.02",
          pause: document.getElementById("pause").value || "0.4"
        }});
        await refresh();
      }} catch (err) {{
        alert(err.message);
      }}
    }});

    stopBtn.addEventListener("click", async () => {{
      try {{
        await post("/api/stop", {{}});
        await refresh();
      }} catch (err) {{
        alert(err.message);
      }}
    }});

    setInterval(refresh, 1000);
    async function refreshCameras() {{
      const stamp = Date.now();
      document.getElementById("cam0").src = "/api/camera.jpg?index=1&t=" + stamp;
      document.getElementById("cam1").src = "/api/camera.jpg?index=2&t=" + stamp;
    }}

    setInterval(refreshCameras, 1000);
    refreshCameras();
    refresh();
  </script>
</body>
</html>"""


class KitchenRobotHandler(BaseHTTPRequestHandler):
    allow_movement = False

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.send_text(page_html(self.allow_movement), "text/html; charset=utf-8")
        elif parsed.path == "/api/status":
            self.send_json(RUN.snapshot())
        elif parsed.path == "/api/camera.jpg":
            try:
                query = parse_qs(parsed.query)
                index = int(query.get("index", ["0"])[0])
                self.send_bytes(CAMERAS.get(index), "image/jpeg")
            except Exception as exc:
                self.send_json({"error": str(exc)}, status=HTTPStatus.SERVICE_UNAVAILABLE)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/run-upma":
                payload = read_request_json(self)
                RUN.start(make_command(payload, self.allow_movement))
                self.send_json({"ok": True})
            elif parsed.path == "/api/agent":
                payload = read_request_json(self)
                RUN.start(make_agent_command(payload, self.allow_movement))
                self.send_json({"ok": True})
            elif parsed.path == "/api/stop":
                RUN.stop()
                self.send_json({"ok": True})
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}")

    def send_text(self, body: str, content_type: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def send_bytes(self, body: bytes, content_type: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, body: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def main() -> int:
    args = parse_args()
    KitchenRobotHandler.allow_movement = args.allow_movement
    CAMERAS.start_from_config()
    server = ThreadingHTTPServer((args.host, args.port), KitchenRobotHandler)
    print(f"Open http://{args.host}:{args.port}")
    if not args.allow_movement:
        print("Movement is blocked. The dashboard can only start dry runs.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        RUN.stop()
        print("\nServer stopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
