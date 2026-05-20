from __future__ import annotations

from setuptools import setup


setup(
    name="so101-upma",
    version="0.1.0",
    description="SO-101 LeRobot upma cooking workflow with calibrated poses, dashboard, and ChatGPT brain.",
    py_modules=[
        "so101_upma_cli",
        "robot_api",
        "connect_test",
        "save_position",
        "upma_mode",
        "stir_motion",
        "ingredient_actions",
        "smart_upma_runner",
        "tight_cup_stick_stir",
        "grip_down",
        "chatgpt_robot_brain",
        "chatgpt_brain",
        "kitchen_robot_server",
        "camera_check",
        "manual_control",
        "replay_sequence",
        "pan_sweep",
        "opencv_auto_stir",
        "live_rl_stir",
    ],
    install_requires=[
        "lerobot[feetech]",
        "openai",
    ],
    entry_points={
        "console_scripts": [
            "upma=so101_upma_cli:main",
        ],
    },
    python_requires=">=3.11",
)
