from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent


def python_exe() -> str:
    local = ROOT / ".venv" / "Scripts" / "python.exe"
    return str(local if local.exists() else Path(sys.executable))


def run(command: list[str]) -> int:
    print("Running:")
    print(" ".join(command))
    return subprocess.call(command, cwd=ROOT)


def run_optional(command: list[str], missing: str) -> int:
    if shutil.which(command[0]) is None and not Path(command[0]).exists():
        print(missing)
        return 1
    return run(command)


def load_config() -> dict:
    path = ROOT / "config.json"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def setup_config(args: argparse.Namespace) -> int:
    config_path = ROOT / "config.json"
    example_path = ROOT / "config.example.json"
    if not config_path.exists():
        shutil.copyfile(example_path, config_path)
        print("Created config.json from config.example.json.")
    config = load_config()
    if args.port:
        config["robot_port"] = args.port
    if args.cameras:
        config["camera_indices"] = args.cameras
    if args.port or args.cameras:
        with config_path.open("w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
            f.write("\n")
        print("Updated config.json.")
    print(f"Config file: {config_path}")
    print(f"robot_port: {config.get('robot_port')}")
    print(f"camera_indices: {config.get('camera_indices')}")
    return 0


def status(_: argparse.Namespace) -> int:
    print("SO-101 Upma status")
    config = load_config()
    print(f"Project: {ROOT}")
    print(f"Python: {python_exe()}")
    print(f"robot_port: {config.get('robot_port', 'missing')}")
    print(f"camera_indices: {config.get('camera_indices', 'missing')}")
    print(f"OPENAI_API_KEY set: {bool(os.environ.get('OPENAI_API_KEY'))}")
    return run([python_exe(), "connect_test.py"])


def calibrate(args: argparse.Namespace) -> int:
    config = load_config()
    port = args.port or config.get("robot_port") or "COM7"
    robot_id = args.robot_id or config.get("robot_id") or "kitchen_stirrer_follower"
    return run(
        [
            str(ROOT / ".venv" / "Scripts" / "lerobot-calibrate.exe"),
            "--robot.type=so101_follower",
            f"--robot.port={port}",
            f"--robot.id={robot_id}",
        ]
    )


def teleop(args: argparse.Namespace) -> int:
    solo = shutil.which("solo")
    if solo is None:
        print("The 'solo' command was not found. Install solo-cli first, then retry.")
        return 1
    command = [solo, "robo", "--teleop"]
    if args.yes:
        command.append("-y")
    return run(command)


def save_pose(args: argparse.Namespace) -> int:
    command = [python_exe(), "save_position.py", args.name]
    if args.force:
        command.append("--force")
    return run(command)


def dry_run(args: argparse.Namespace) -> int:
    command = [python_exe(), "upma_mode.py", "--dry-run", "--yes"]
    if args.ingredients:
        command.append("--with-ingredients")
    return run(command)


def run_upma(args: argparse.Namespace) -> int:
    command = [
        python_exe(),
        "upma_mode.py",
        "--yes",
        "--speed-scale",
        str(args.speed_scale),
        "--cycles-multiplier",
        str(args.cycles_multiplier),
        "--pause",
        str(args.pause),
        "--low-pressure-lift-deg",
        str(args.low_pressure_lift),
    ]
    if args.ingredients:
        command.append("--with-ingredients")
    if args.skip_camera_check:
        command.append("--skip-camera-boundary-check")
    return run(command)


def smart(args: argparse.Namespace) -> int:
    return run(
        [
            python_exe(),
            "smart_upma_runner.py",
            "--yes",
            "--speed-scale",
            str(args.speed_scale),
            "--pause",
            str(args.pause),
            "--stir-cycles",
            str(args.cycles),
            "--tight",
            str(args.tight),
            "--open",
            str(args.open),
        ]
    )


def ingredients(args: argparse.Namespace) -> int:
    return run(
        [
            python_exe(),
            "ingredient_actions.py",
            "--action",
            args.action,
            "--speed-scale",
            str(args.speed_scale),
            "--pause",
            str(args.pause),
            "--yes",
        ]
    )


def stir(args: argparse.Namespace) -> int:
    return run(
        [
            python_exe(),
            "stir_motion.py",
            "--motion",
            args.motion,
            "--cycles",
            str(args.cycles),
            "--speed-scale",
            str(args.speed_scale),
            "--yes",
        ]
    )


def grip_down(args: argparse.Namespace) -> int:
    return run(
        [
            python_exe(),
            "grip_down.py",
            "--speed-scale",
            str(args.speed_scale),
            "--grip-value",
            str(args.tight),
            "--pause",
            str(args.pause),
            "--yes",
        ]
    )


def brain(args: argparse.Namespace) -> int:
    command = [python_exe(), "chatgpt_robot_brain.py", args.request]
    if args.execute:
        command.append("--execute")
    command.extend(["--speed-scale", str(args.speed_scale), "--pause", str(args.pause), "--cycles", str(args.cycles)])
    return run(command)


def dashboard(args: argparse.Namespace) -> int:
    command = [python_exe(), "kitchen_robot_server.py"]
    if args.allow_movement:
        command.append("--allow-movement")
    command.extend(["--host", args.host, "--port", str(args.port)])
    return run(command)


def stop(_: argparse.Namespace) -> int:
    if os.name == "nt":
        return subprocess.call(["taskkill", "/F", "/IM", "python.exe"])
    return subprocess.call(["pkill", "-f", "python"])


def guide(_: argparse.Namespace) -> int:
    guide_path = ROOT / "UPMA_CALIBRATION_GUIDE.md"
    print(guide_path)
    if os.name == "nt":
        return subprocess.call(["notepad", str(guide_path)])
    return 0


def hf_login(args: argparse.Namespace) -> int:
    hf = shutil.which("huggingface-cli")
    if hf is None:
        return run([python_exe(), "-m", "huggingface_hub.commands.huggingface_cli", "login"])
    command = [hf, "login"]
    if args.token:
        command.extend(["--token", args.token])
    return run(command)


def hf_whoami(_: argparse.Namespace) -> int:
    hf = shutil.which("huggingface-cli")
    if hf is None:
        return run([python_exe(), "-m", "huggingface_hub.commands.huggingface_cli", "whoami"])
    return run([hf, "whoami"])


def download(args: argparse.Namespace) -> int:
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("huggingface_hub is not installed. Run: pip install huggingface_hub")
        return 1

    target = args.local_dir or str(ROOT / "downloads" / args.repo_id.replace("/", "__"))
    print(f"Downloading {args.repo_id} to {target}")
    snapshot_download(
        repo_id=args.repo_id,
        repo_type=args.repo_type,
        revision=args.revision,
        local_dir=target,
        local_dir_use_symlinks=False,
    )
    print("Download complete.")
    return 0


def push_hf(args: argparse.Namespace) -> int:
    try:
        from huggingface_hub import HfApi
    except ImportError:
        print("huggingface_hub is not installed. Run: pip install huggingface_hub")
        return 1

    folder = Path(args.folder).resolve()
    if not folder.exists():
        print(f"Folder does not exist: {folder}")
        return 1
    api = HfApi()
    print(f"Creating or reusing {args.repo_type} repo: {args.repo_id}")
    api.create_repo(repo_id=args.repo_id, repo_type=args.repo_type, exist_ok=True, private=args.private)
    print(f"Uploading {folder} to Hugging Face...")
    api.upload_folder(
        repo_id=args.repo_id,
        repo_type=args.repo_type,
        folder_path=str(folder),
        path_in_repo=args.path_in_repo,
        commit_message=args.message,
    )
    print("Upload complete.")
    return 0


def solo_command(extra: Iterable[str]) -> int:
    solo = shutil.which("solo")
    if solo is None:
        print("The 'solo' command was not found. Install solo-cli first, then retry.")
        print("Example: uv pip install -e path\\to\\solo-cli")
        return 1
    return run([solo, *extra])


def robo(args: argparse.Namespace) -> int:
    if args.calibrate:
        if args.calibrate == "follower":
            return calibrate(args)
        return solo_command(["robo", "--calibrate", args.calibrate])
    if args.teleop:
        return teleop(args)
    if args.record:
        command = ["robo", "--record"]
        if args.yes:
            command.append("--yes")
        return solo_command(command)
    if args.train:
        command = ["robo", "--train"]
        if args.yes:
            command.append("--yes")
        return solo_command(command)
    if args.inference:
        command = ["robo", "--inference"]
        if args.yes:
            command.append("--yes")
        return solo_command(command)
    if args.replay:
        command = ["robo", "--replay"]
        if args.yes:
            command.append("--yes")
        return solo_command(command)
    print("Choose one robo action: --calibrate, --teleop, --record, --train, --inference, or --replay.")
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="upma", description="SO-101 upma robot CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("setup", help="Create/update config.json.")
    p.add_argument("--port", default=None, help="Robot port, for example COM7.")
    p.add_argument("--cameras", nargs="*", type=int, default=None)
    p.set_defaults(func=setup_config)

    p = sub.add_parser("status", help="Show config and test robot connection.")
    p.set_defaults(func=status)

    p = sub.add_parser("calibrate", help="Run LeRobot follower calibration.")
    p.add_argument("--port", default=None)
    p.add_argument("--robot-id", default=None)
    p.set_defaults(func=calibrate)

    p = sub.add_parser("teleop", help="Run Solo teleoperation if solo-cli is installed.")
    p.add_argument("-y", "--yes", action="store_true")
    p.set_defaults(func=teleop)

    p = sub.add_parser("robo", help="Solo-style robotics operations.")
    p.add_argument("--calibrate", choices=["all", "leader", "follower"], default=None)
    p.add_argument("--teleop", action="store_true")
    p.add_argument("--record", action="store_true")
    p.add_argument("--train", action="store_true")
    p.add_argument("--inference", action="store_true")
    p.add_argument("--replay", action="store_true")
    p.add_argument("-y", "--yes", action="store_true")
    p.add_argument("--port", default=None, help="Follower port for --calibrate follower.")
    p.add_argument("--robot-id", default=None, help="Follower id for --calibrate follower.")
    p.set_defaults(func=robo)

    p = sub.add_parser("save-pose", help="Save the current robot pose.")
    p.add_argument("name")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=save_pose)

    p = sub.add_parser("dry-run", help="Validate sequence without movement.")
    p.add_argument("--ingredients", action="store_true")
    p.set_defaults(func=dry_run)

    p = sub.add_parser("run", help="Run upma sequence.")
    p.add_argument("--ingredients", action="store_true")
    p.add_argument("--speed-scale", type=float, default=0.02)
    p.add_argument("--cycles-multiplier", type=float, default=1.0)
    p.add_argument("--pause", type=float, default=0.15)
    p.add_argument("--low-pressure-lift", type=float, default=6.0)
    p.add_argument("--skip-camera-check", action="store_true")
    p.set_defaults(func=run_upma)

    p = sub.add_parser("smart", help="Cup pickup, stick pickup, tight grip, stir, and park.")
    p.add_argument("--speed-scale", type=float, default=0.02)
    p.add_argument("--pause", type=float, default=0.25)
    p.add_argument("--cycles", type=int, default=5)
    p.add_argument("--tight", type=float, default=-5.0)
    p.add_argument("--open", type=float, default=30.0)
    p.set_defaults(func=smart)

    p = sub.add_parser("ingredients", help="Run ingredient cup/stick action only.")
    p.add_argument("--action", choices=["all", "cup", "stirrer"], default="all")
    p.add_argument("--speed-scale", type=float, default=0.02)
    p.add_argument("--pause", type=float, default=0.6)
    p.set_defaults(func=ingredients)

    p = sub.add_parser("stir", help="Run a small stirring test.")
    p.add_argument("--motion", choices=["front-back", "left-right", "up-down", "clockwise", "anticlockwise"], default="front-back")
    p.add_argument("--cycles", type=int, default=1)
    p.add_argument("--speed-scale", type=float, default=0.02)
    p.set_defaults(func=stir)

    p = sub.add_parser("grip-down", help="Tighten gripper and move to DOWN.")
    p.add_argument("--speed-scale", type=float, default=0.02)
    p.add_argument("--tight", type=float, default=-5.0)
    p.add_argument("--pause", type=float, default=0.5)
    p.set_defaults(func=grip_down)

    p = sub.add_parser("brain", help="Ask ChatGPT to choose a safe project action.")
    p.add_argument("request")
    p.add_argument("--execute", action="store_true")
    p.add_argument("--speed-scale", type=float, default=0.02)
    p.add_argument("--pause", type=float, default=0.25)
    p.add_argument("--cycles", type=int, default=5)
    p.set_defaults(func=brain)

    p = sub.add_parser("dashboard", help="Start localhost dashboard.")
    p.add_argument("--allow-movement", action="store_true")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(func=dashboard)

    p = sub.add_parser("stop", help="Stop Python robot processes.")
    p.set_defaults(func=stop)

    p = sub.add_parser("guide", help="Open calibration guide.")
    p.set_defaults(func=guide)

    p = sub.add_parser("login", help="Log in to Hugging Face.")
    p.add_argument("--token", default=None)
    p.set_defaults(func=hf_login)

    p = sub.add_parser("whoami", help="Show Hugging Face account.")
    p.set_defaults(func=hf_whoami)

    p = sub.add_parser("download", help="Download a Hugging Face repo snapshot.")
    p.add_argument("repo_id", help="Example: lakshveeer/robot")
    p.add_argument("--repo-type", choices=["model", "dataset", "space"], default="dataset")
    p.add_argument("--revision", default=None)
    p.add_argument("--local-dir", default=None)
    p.set_defaults(func=download)

    p = sub.add_parser("push-hf", help="Upload a folder to Hugging Face.")
    p.add_argument("repo_id", help="Example: username/my-robot-dataset")
    p.add_argument("--folder", default=".", help="Folder to upload.")
    p.add_argument("--repo-type", choices=["model", "dataset", "space"], default="dataset")
    p.add_argument("--path-in-repo", default="")
    p.add_argument("--message", default="Upload SO-101 upma robot files")
    p.add_argument("--private", action="store_true")
    p.set_defaults(func=push_hf)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
