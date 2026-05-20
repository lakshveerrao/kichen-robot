from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a simple replay policy from recorded SO-101 poses.")
    parser.add_argument("--input", default="recordings/latest/observations.jsonl")
    parser.add_argument("--out", default="models/latest_policy.json")
    parser.add_argument("--stride", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    out_path = Path(args.out)
    if args.stride < 1:
        print("--stride must be >= 1.")
        return 1
    if not input_path.exists():
        print(f"Missing recording: {input_path}")
        return 1

    positions = []
    with input_path.open("r", encoding="utf-8") as f:
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
