from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


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
    if args.leader_port:
        config["leader_port"] = args.leader_port
    if args.leader_id:
        config["leader_id"] = args.leader_id
    if args.follower_id:
        config["follower_id"] = args.follower_id
    if args.cameras:
        config["camera_indices"] = args.cameras
    if args.port or args.leader_port or args.leader_id or args.follower_id or args.cameras:
        with config_path.open("w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
            f.write("\n")
        print("Updated config.json.")
    print(f"Config file: {config_path}")
    print(f"robot_port: {config.get('robot_port')}")
    print(f"leader_port: {config.get('leader_port')}")
    print(f"leader_id: {config.get('leader_id')}")
    print(f"follower_id: {config.get('follower_id')}")
    print(f"camera_indices: {config.get('camera_indices')}")
    return 0


def status(_: argparse.Namespace) -> int:
    print("PBL SO-101 status")
    config = load_config()
    print(f"Project: {ROOT}")
    print(f"Python: {python_exe()}")
    print(f"robot_port: {config.get('robot_port', 'missing')}")
    print(f"leader_port: {config.get('leader_port', 'missing')}")
    print(f"leader_id: {config.get('leader_id', 'missing')}")
    print(f"follower_id: {config.get('follower_id', 'missing')}")
    print(f"camera_indices: {config.get('camera_indices', 'missing')}")
    print(f"OPENAI_API_KEY set: {bool(os.environ.get('OPENAI_API_KEY'))}")
    return run([python_exe(), "connect_test.py"])


def calibrate(args: argparse.Namespace) -> int:
    config = load_config()
    port = args.port or config.get("robot_port") or config.get("follower_port") or "COM7"
    robot_id = args.robot_id or config.get("follower_id") or config.get("robot_id") or "so101_follower"
    return run(
        [
            str(ROOT / ".venv" / "Scripts" / "lerobot-calibrate.exe"),
            "--robot.type=so101_follower",
            f"--robot.port={port}",
            f"--robot.id={robot_id}",
        ]
    )


def robot_admin(args: argparse.Namespace, action: str, device: str) -> int:
    command = [python_exe(), "local_robot_admin.py", "--action", action, "--device", device]
    if getattr(args, "yes", False):
        command.append("--yes")
    if getattr(args, "leader_port", None):
        command.extend(["--leader-port", args.leader_port])
    if getattr(args, "follower_port", None):
        command.extend(["--follower-port", args.follower_port])
    elif getattr(args, "port", None):
        command.extend(["--follower-port", args.port])
    if getattr(args, "leader_id", None):
        command.extend(["--leader-id", args.leader_id])
    if getattr(args, "follower_id", None):
        command.extend(["--follower-id", args.follower_id])
    elif getattr(args, "robot_id", None):
        command.extend(["--follower-id", args.robot_id])
    return run(command)


def teleop(args: argparse.Namespace) -> int:
    command = [python_exe(), "local_teleop.py"]
    if args.yes:
        command.append("--yes")
    if getattr(args, "leader_port", None):
        command.extend(["--leader-port", args.leader_port])
    if getattr(args, "follower_port", None):
        command.extend(["--follower-port", args.follower_port])
    if getattr(args, "leader_id", None):
        command.extend(["--leader-id", args.leader_id])
    if getattr(args, "follower_id", None):
        command.extend(["--follower-id", args.follower_id])
    if getattr(args, "fps", None):
        command.extend(["--fps", str(args.fps)])
    if getattr(args, "camera_mode", None):
        command.extend(["--camera-mode", args.camera_mode])
    if getattr(args, "camera_fps", None):
        command.extend(["--camera-fps", str(args.camera_fps)])
    if getattr(args, "camera_width", None):
        command.extend(["--camera-width", str(args.camera_width)])
    if getattr(args, "camera_height", None):
        command.extend(["--camera-height", str(args.camera_height)])
    if getattr(args, "camera_save_dir", None):
        command.extend(["--camera-save-dir", args.camera_save_dir])
    if getattr(args, "rerun", False):
        command.append("--rerun")
    if getattr(args, "rerun_spawn", False):
        command.append("--rerun-spawn")
    if getattr(args, "no_rerun_spawn", False):
        command.append("--no-rerun-spawn")
    if getattr(args, "rerun_every", None):
        command.extend(["--rerun-every", str(args.rerun_every)])
    return run(command)


def save_pose(args: argparse.Namespace) -> int:
    command = [python_exe(), "save_position.py", args.name]
    if args.force:
        command.append("--force")
    return run(command)


def agent(args: argparse.Namespace) -> int:
    command = [python_exe(), "automatic_agent_controller.py", *args.request]
    if args.execute:
        command.append("--execute")
    if args.dry_run_command:
        command.append("--dry-run-command")
    if args.use_saved_poses:
        command.append("--use-saved-poses")
    command.extend(["--steps", str(args.steps)])
    command.extend(["--speed-scale", str(args.speed_scale), "--pause", str(args.pause)])
    return run(command)


def stop(_: argparse.Namespace) -> int:
    if os.name == "nt":
        return subprocess.call(["taskkill", "/F", "/IM", "python.exe"])
    return subprocess.call(["pkill", "-f", "python"])


def test(_: argparse.Namespace) -> int:
    return status(_)


def list_assets(_: argparse.Namespace) -> int:
    for folder_name in ("downloads", "recordings", "models"):
        folder = ROOT / folder_name
        print(f"{folder_name}:")
        if not folder.exists():
            print("  missing")
            continue
        items = sorted(folder.iterdir())
        if not items:
            print("  empty")
            continue
        for item in items:
            print(f"  {item.name}")
    return 0


def logout(_: argparse.Namespace) -> int:
    hf = shutil.which("huggingface-cli")
    command = [hf, "logout"] if hf else [python_exe(), "-m", "huggingface_hub.commands.huggingface_cli", "logout"]
    return run(command)


def setup_usb(_: argparse.Namespace) -> int:
    print("Windows USB setup:")
    print("  1. Connect the SO-101 USB adapters.")
    print("  2. Run: mode")
    print("  3. Use the detected COM ports with pbl setup --port COM7 --leader-port COM8")
    print("  4. If a port is missing, unplug/replug USB or try another cable/port.")
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


def robo(args: argparse.Namespace) -> int:
    if args.setup_motors:
        return robot_admin(args, "setup-motors", args.setup_motors)
    if args.calibrate:
        return robot_admin(args, "calibrate", args.calibrate)
    if args.teleop:
        return teleop(args)
    if args.record:
        command = [
            python_exe(), "local_record.py",
            "--dataset-dir", args.dataset_dir,
            "--task", args.task,
            "--out", args.out,
            "--fps", str(args.fps),
            "--control-mode", args.control_mode,
            "--camera-mode", args.camera_mode,
            "--camera-fps", str(args.camera_fps),
            "--camera-width", str(args.camera_width),
            "--camera-height", str(args.camera_height),
            "--rerun-every", str(args.rerun_every),
        ]
        if args.seconds is not None:
            command.extend(["--seconds", str(args.seconds)])
        if args.episodes is not None:
            command.extend(["--episodes", str(args.episodes)])
        if args.camera_save_dir:
            command.extend(["--camera-save-dir", args.camera_save_dir])
        if args.leader_port:
            command.extend(["--leader-port", args.leader_port])
        if args.follower_port:
            command.extend(["--follower-port", args.follower_port])
        if args.leader_id:
            command.extend(["--leader-id", args.leader_id])
        if args.follower_id:
            command.extend(["--follower-id", args.follower_id])
        if args.yes:
            command.append("--yes")
        if args.rerun:
            command.append("--rerun")
        if args.rerun_spawn:
            command.append("--rerun-spawn")
        if args.no_rerun_spawn:
            command.append("--no-rerun-spawn")
        if args.push_hf:
            command.append("--push-hf")
        if args.repo_id:
            command.extend(["--repo-id", args.repo_id])
        if args.repo_type:
            command.extend(["--repo-type", args.repo_type])
        if args.private:
            command.append("--private")
        return run(command)
    if args.train:
        return run([python_exe(), "local_train.py", "--input", args.input, "--out", args.model_out, "--stride", str(args.stride)])
    if args.inference:
        return run([python_exe(), "local_inference.py", "--policy", args.policy, "--speed-scale", str(args.speed_scale), "--pause", str(args.pause), "--yes"])
    if args.replay:
        return run([python_exe(), "replay_sequence.py", "--yes"])
    print("Choose one robo action: --setup-motors, --calibrate, --teleop, --record, --train, --inference, or --replay.")
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pbl", description="PBL SO-101 robotics CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("setup", help="Create/update config.json.")
    p.add_argument("--port", default=None, help="Robot port, for example COM7.")
    p.add_argument("--leader-port", default=None, help="Leader arm port, for example COM8.")
    p.add_argument("--leader-id", default=None)
    p.add_argument("--follower-id", default=None)
    p.add_argument("--cameras", nargs="*", type=int, default=None)
    p.set_defaults(func=setup_config)

    p = sub.add_parser("status", help="Show config and test robot connection.")
    p.set_defaults(func=status)

    p = sub.add_parser("setup-motors", help="Assign SO-101 motor IDs locally.")
    p.add_argument("--device", choices=["leader", "follower", "all"], default="all")
    p.add_argument("--leader-port", default=None)
    p.add_argument("--follower-port", default=None)
    p.add_argument("--leader-id", default=None)
    p.add_argument("--follower-id", default=None)
    p.add_argument("-y", "--yes", action="store_true")
    p.set_defaults(func=lambda args: robot_admin(args, "setup-motors", args.device))

    p = sub.add_parser("calibrate", help="Run local SO-101 calibration.")
    p.add_argument("--device", choices=["leader", "follower", "all"], default="follower")
    p.add_argument("--port", default=None)
    p.add_argument("--robot-id", default=None)
    p.add_argument("--leader-port", default=None)
    p.add_argument("--follower-port", default=None)
    p.add_argument("--leader-id", default=None)
    p.add_argument("--follower-id", default=None)
    p.add_argument("-y", "--yes", action="store_true")
    p.set_defaults(func=lambda args: robot_admin(args, "calibrate", args.device))

    p = sub.add_parser("teleop", help="Run local leader-to-follower teleoperation without Solo.")
    p.add_argument("-y", "--yes", action="store_true")
    p.add_argument("--leader-port", default=None)
    p.add_argument("--follower-port", default=None)
    p.add_argument("--leader-id", default=None)
    p.add_argument("--follower-id", default=None)
    p.add_argument("--fps", type=float, default=60.0)
    p.add_argument("--camera-mode", choices=["ask", "yes", "no"], default="ask")
    p.add_argument("--camera-fps", type=float, default=30.0)
    p.add_argument("--camera-width", type=int, default=640)
    p.add_argument("--camera-height", type=int, default=480)
    p.add_argument("--camera-save-dir", default=None)
    p.add_argument("--rerun", action="store_true", help="Stream camera frames and robot data to Rerun.")
    p.add_argument("--rerun-spawn", action="store_true", help="Compatibility option. --rerun opens the viewer by default.")
    p.add_argument("--no-rerun-spawn", action="store_true", help="Log to Rerun without opening the viewer.")
    p.add_argument("--rerun-every", type=int, default=5)
    p.set_defaults(func=teleop)

    p = sub.add_parser("robo", help="Local robotics operations.")
    p.add_argument("--setup-motors", choices=["all", "leader", "follower"], default=None)
    p.add_argument("--calibrate", choices=["all", "leader", "follower"], default=None)
    p.add_argument("--teleop", action="store_true")
    p.add_argument("--record", action="store_true")
    p.add_argument("--train", action="store_true")
    p.add_argument("--inference", action="store_true")
    p.add_argument("--replay", action="store_true")
    p.add_argument("-y", "--yes", action="store_true")
    p.add_argument("--port", default=None, help="Follower port for --calibrate follower.")
    p.add_argument("--robot-id", default=None, help="Follower id for --calibrate follower.")
    p.add_argument("--leader-port", default=None)
    p.add_argument("--follower-port", default=None)
    p.add_argument("--leader-id", default=None)
    p.add_argument("--follower-id", default=None)
    p.add_argument("--fps", type=float, default=60.0)
    p.add_argument("--camera-mode", choices=["ask", "yes", "no"], default="ask")
    p.add_argument("--camera-fps", type=float, default=30.0)
    p.add_argument("--camera-width", type=int, default=640)
    p.add_argument("--camera-height", type=int, default=480)
    p.add_argument("--camera-save-dir", default=None)
    p.add_argument("--rerun", action="store_true", help="Stream camera frames and robot data to Rerun.")
    p.add_argument("--rerun-spawn", action="store_true", help="Compatibility option. --rerun opens the viewer by default.")
    p.add_argument("--no-rerun-spawn", action="store_true", help="Log to Rerun without opening the viewer.")
    p.add_argument("--rerun-every", type=int, default=5)
    p.add_argument("--episodes", type=int, default=None, help="Number of recording episodes. If omitted, pbl asks.")
    p.add_argument("--seconds", type=float, default=None, help="Seconds per episode. If omitted, pbl asks.")
    p.add_argument("--dataset-dir", default="recordings/latest")
    p.add_argument("--task", default="so101_recording")
    p.add_argument("--control-mode", choices=["auto", "teleop", "observe"], default="auto")
    p.add_argument("--out", default="recordings/latest/observations.jsonl")
    p.add_argument("--input", default="recordings/latest")
    p.add_argument("--model-out", default="models/latest_policy.json")
    p.add_argument("--policy", default="models/latest_policy.json")
    p.add_argument("--stride", type=int, default=1)
    p.add_argument("--speed-scale", type=float, default=0.02)
    p.add_argument("--pause", type=float, default=0.05)
    p.add_argument("--push-hf", action="store_true", help="Upload recording dataset to Hugging Face after --record.")
    p.add_argument("--repo-id", default=None, help="Hugging Face repo id for --push-hf.")
    p.add_argument("--repo-type", choices=["dataset", "model", "space"], default="dataset")
    p.add_argument("--private", action="store_true")
    p.set_defaults(func=robo)

    p = sub.add_parser("save-pose", help="Save the current robot pose.")
    p.add_argument("name")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=save_pose)

    p = sub.add_parser("agent", help="Camera-aware automatic agent controller.")
    p.add_argument("request", nargs="*")
    p.add_argument("--execute", action="store_true")
    p.add_argument("--dry-run-command", action="store_true")
    p.add_argument("--use-saved-poses", action="store_true")
    p.add_argument("--steps", type=int, default=12)
    p.add_argument("--speed-scale", type=float, default=0.02)
    p.add_argument("--pause", type=float, default=0.4)
    p.set_defaults(func=agent)

    p = sub.add_parser("stop", help="Stop Python robot processes.")
    p.set_defaults(func=stop)

    p = sub.add_parser("test", help="Test CLI and robot connection.")
    p.set_defaults(func=test)

    p = sub.add_parser("list", help="List local downloads, recordings, and models.")
    p.set_defaults(func=list_assets)

    p = sub.add_parser("setup-usb", help="Show Windows USB/COM setup steps.")
    p.set_defaults(func=setup_usb)

    p = sub.add_parser("login", help="Log in to Hugging Face.")
    p.add_argument("--token", default=None)
    p.set_defaults(func=hf_login)

    p = sub.add_parser("whoami", help="Show Hugging Face account.")
    p.set_defaults(func=hf_whoami)

    p = sub.add_parser("logout", help="Log out of Hugging Face.")
    p.set_defaults(func=logout)

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
    p.add_argument("--message", default="Upload SO-101 robot files")
    p.add_argument("--private", action="store_true")
    p.set_defaults(func=push_hf)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
