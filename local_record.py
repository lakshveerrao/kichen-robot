from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from camera_runtime import BackgroundCameraSet, choose_cameras, log_rerun_text, start_rerun
from local_teleop import add_write_retries, import_lerobot_classes
from robot_api import connect_robot, disconnect_robot, read_current_position


CONFIG_PATH = Path("config.json")


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record SO-101 episodes with optional teleop, cameras, Rerun, and Hugging Face upload.")
    parser.add_argument("--out", default="recordings/latest/observations.jsonl")
    parser.add_argument("--dataset-dir", default="recordings/latest")
    parser.add_argument("--task", default="so101_kitchen_recording")
    parser.add_argument("--episodes", type=int, default=None)
    parser.add_argument("--seconds", type=float, default=None)
    parser.add_argument("--fps", type=float, default=10.0)
    parser.add_argument("--control-mode", choices=["auto", "teleop", "observe"], default="auto")
    parser.add_argument("--leader-port", default=None)
    parser.add_argument("--follower-port", default=None)
    parser.add_argument("--leader-id", default=None)
    parser.add_argument("--follower-id", default=None)
    parser.add_argument("--camera-mode", choices=["ask", "yes", "no"], default="ask")
    parser.add_argument("--camera-fps", type=float, default=30.0)
    parser.add_argument("--camera-width", type=int, default=640)
    parser.add_argument("--camera-height", type=int, default=480)
    parser.add_argument("--camera-save-dir", default=None)
    parser.add_argument("--rerun", action="store_true", help="Stream camera frames and robot data to Rerun.")
    parser.add_argument("--rerun-spawn", action="store_true", help="Compatibility option. --rerun opens the viewer by default.")
    parser.add_argument("--no-rerun-spawn", action="store_true", help="Log to Rerun without opening the viewer.")
    parser.add_argument("--rerun-every", type=int, default=5, help="Log every N camera/record frames to Rerun.")
    parser.add_argument("--push-hf", action="store_true", help="Upload the recorded dataset folder to Hugging Face after recording.")
    parser.add_argument("--repo-id", default=None, help="Hugging Face repo id, for example username/my-so101-dataset.")
    parser.add_argument("--repo-type", choices=["dataset", "model", "space"], default="dataset")
    parser.add_argument("--private", action="store_true")
    parser.add_argument("--yes", action="store_true")
    return parser.parse_args()


def prompt_number(label: str, default: float, cast: Any) -> Any:
    answer = input(f"{label} ({default}): ").strip()
    return cast(answer) if answer else cast(default)


def resolve_recording_shape(args: argparse.Namespace) -> tuple[int, float]:
    episodes = args.episodes
    seconds = args.seconds
    if not args.yes:
        if episodes is None:
            episodes = prompt_number("How many episodes do you want to record?", 1, int)
        if seconds is None:
            seconds = prompt_number("How many seconds should each episode be?", 20.0, float)
    return int(episodes if episodes is not None else 1), float(seconds if seconds is not None else 20.0)


def connect_teleop(config: dict, args: argparse.Namespace) -> tuple[Any, Any]:
    leader_port = args.leader_port or config.get("leader_port") or "COM8"
    follower_port = args.follower_port or config.get("robot_port") or config.get("follower_port") or "COM7"
    leader_id = args.leader_id or config.get("leader_id") or "1"
    follower_id = args.follower_id or config.get("follower_id") or config.get("robot_id") or "kitchen_stirrer_follower"
    SO101Leader, SO101LeaderConfig, SO101Follower, SO101FollowerConfig = import_lerobot_classes()
    leader = SO101Leader(SO101LeaderConfig(port=leader_port, id=str(leader_id)))
    follower = SO101Follower(
        SO101FollowerConfig(
            port=follower_port,
            id=str(follower_id),
            max_relative_target=5.0,
            cameras={},
        )
    )
    add_write_retries(leader)
    add_write_retries(follower)
    leader.connect()
    follower.connect()
    return leader, follower


def upload_to_hugging_face(args: argparse.Namespace, dataset_dir: Path) -> int:
    if not args.repo_id:
        print("--push-hf requires --repo-id username/dataset-name")
        return 1
    try:
        from huggingface_hub import HfApi
    except ImportError:
        print("huggingface_hub is not installed.")
        return 1
    api = HfApi()
    print(f"Creating or reusing Hugging Face {args.repo_type} repo: {args.repo_id}")
    api.create_repo(repo_id=args.repo_id, repo_type=args.repo_type, exist_ok=True, private=args.private)
    print(f"Uploading dataset folder: {dataset_dir}")
    api.upload_folder(
        repo_id=args.repo_id,
        repo_type=args.repo_type,
        folder_path=str(dataset_dir),
        commit_message=f"Upload PBL SO-101 recording: {args.task}",
    )
    print("Hugging Face upload complete.")
    return 0


def main() -> int:
    args = parse_args()
    episodes, seconds = resolve_recording_shape(args)
    if seconds <= 0 or seconds > 3600:
        print("--seconds must be > 0 and <= 3600.")
        return 1
    if episodes <= 0 or episodes > 1000:
        print("--episodes must be > 0 and <= 1000.")
        return 1
    if args.fps <= 0 or args.fps > 60:
        print("--fps must be > 0 and <= 60.")
        return 1
    if not CONFIG_PATH.exists():
        print("Missing config.json.")
        return 1

    robot = None
    leader = None
    cameras = None
    rr = None
    try:
        config = load_json(CONFIG_PATH)
        dataset_dir = Path(args.dataset_dir)
        dataset_dir.mkdir(parents=True, exist_ok=True)
        print("PBL episode recorder")
        print(f"dataset_dir={dataset_dir}")
        print(f"task={args.task}")
        print(f"episodes={episodes}, seconds_per_episode={seconds}, fps={args.fps}")
        configured_cameras = [int(index) for index in config.get("camera_indices", [0])]
        camera_indices = choose_cameras(args.camera_mode, configured_cameras, args.camera_width, args.camera_height)
        if not args.yes:
            input("Press Enter to connect and start episode recording, or Ctrl+C to cancel.")
        if args.rerun:
            rr = start_rerun("pbl_so101_record", spawn=not args.no_rerun_spawn)

        use_teleop = args.control_mode == "teleop" or (
            args.control_mode == "auto" and bool(args.leader_port or config.get("leader_port"))
        )
        if use_teleop:
            print("Recording in teleop mode: move the leader arm during each episode.")
            leader, robot = connect_teleop(config, args)
        else:
            print("Recording in observe mode: follower poses are recorded without leader control.")
            robot = connect_robot(config)

        interval = 1.0 / args.fps
        manifest = {
            "task": args.task,
            "fps": args.fps,
            "seconds_per_episode": seconds,
            "episodes_requested": episodes,
            "control_mode": "teleop" if use_teleop else "observe",
            "camera_indices": camera_indices,
            "episodes": [],
        }
        total_frames = 0
        for episode_index in range(episodes):
            episode_dir = dataset_dir / f"episode_{episode_index:06d}"
            episode_dir.mkdir(parents=True, exist_ok=True)
            episode_out = episode_dir / "observations.jsonl"
            camera_dir = Path(args.camera_save_dir) if args.camera_save_dir else episode_dir / "cameras"
            if cameras is not None:
                cameras.stop()
            cameras = BackgroundCameraSet(
                camera_indices,
                args.camera_width,
                args.camera_height,
                args.camera_fps,
                camera_dir if camera_indices else None,
                rerun=rr,
                rerun_every=args.rerun_every,
                rerun_path_prefix=f"episode_{episode_index:06d}/cameras",
            )
            cameras.start()
            print(f"Episode {episode_index + 1}/{episodes}: recording for {seconds} seconds.")
            log_rerun_text(rr, "recording/episode", {"episode": episode_index, "state": "start"})
            start = time.time()
            count = 0
            with episode_out.open("w", encoding="utf-8") as f:
                while time.time() - start < seconds:
                    loop_started = time.perf_counter()
                    timestamp = time.time()
                    action = None
                    if leader is not None:
                        action = leader.get_action()
                        robot.send_action(action)
                        position = {key: float(value) for key, value in action.items() if key.endswith(".pos")}
                    else:
                        position = read_current_position(robot)
                    camera_state = cameras.snapshot() if cameras is not None else {}
                    item = {
                        "episode": episode_index,
                        "frame": count,
                        "t": timestamp,
                        "position": position,
                        "action": action,
                        "camera_state": camera_state,
                        "task": args.task,
                    }
                    f.write(json.dumps(item, default=str) + "\n")
                    if rr is not None and count % max(1, args.rerun_every) == 0:
                        log_rerun_text(rr, "robot/position", {"episode": episode_index, "frame": count, "position": position})
                        log_rerun_text(rr, "robot/camera_state", camera_state)
                    count += 1
                    sleep_time = interval - (time.perf_counter() - loop_started)
                    if sleep_time > 0:
                        time.sleep(sleep_time)
            total_frames += count
            manifest["episodes"].append({"index": episode_index, "frames": count, "file": str(episode_out)})
            log_rerun_text(rr, "recording/episode", {"episode": episode_index, "state": "complete", "frames": count})
            print(f"Saved episode {episode_index + 1}: {episode_out} ({count} frames)")
            if episode_index < episodes - 1 and not args.yes:
                input("Reset the scene, then press Enter for the next episode.")
        with (dataset_dir / "manifest.json").open("w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
            f.write("\n")
        latest_out = Path(args.out)
        latest_out.parent.mkdir(parents=True, exist_ok=True)
        first_episode = dataset_dir / "episode_000000" / "observations.jsonl"
        if first_episode.exists():
            latest_out.write_text(first_episode.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Recorded {episodes} episodes and {total_frames} frames.")
        if args.push_hf:
            return upload_to_hugging_face(args, dataset_dir)
        return 0
    except KeyboardInterrupt:
        print("\nRecording stopped.")
        return 130
    except Exception as exc:
        print(f"Recording failed: {exc}")
        return 1
    finally:
        disconnect_robot(leader)
        disconnect_robot(robot)
        if cameras is not None:
            cameras.stop()
        print("Disconnected.")


if __name__ == "__main__":
    raise SystemExit(main())
