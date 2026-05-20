from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a simple replay policy from recorded SO-101 poses.")
    parser.add_argument("--input", default="recordings/latest")
    parser.add_argument("--out", default="models/latest_policy.json")
    parser.add_argument("--stride", type=int, default=1)
    return parser.parse_args()


def iter_recording_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        files = sorted(path.glob("episode_*/observations.jsonl"))
        if files:
            return files
        fallback = path / "observations.jsonl"
        if fallback.exists():
            return [fallback]
    return []


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    out_path = Path(args.out)
    if args.stride < 1:
        print("--stride must be >= 1.")
        return 1
    recording_files = iter_recording_files(input_path)
    if not recording_files:
        print(f"Missing recording file or episode dataset: {input_path}")
        return 1

    positions = []
    for recording_file in recording_files:
        with recording_file.open("r", encoding="utf-8") as f:
            for index, line in enumerate(f):
                if index % args.stride != 0:
                    continue
                item = json.loads(line)
                positions.append(item["position"])
    if not positions:
        print("No positions found in recording.")
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    policy = {
        "type": "replay_pose_sequence",
        "source": str(input_path),
        "recording_files": [str(path) for path in recording_files],
        "count": len(positions),
        "positions": positions,
    }
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(policy, f, indent=2)
        f.write("\n")
    print(f"Saved replay policy with {len(positions)} poses to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
