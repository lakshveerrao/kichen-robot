from __future__ import annotations

from setuptools import setup


setup(
    name="pbl-so101-cli",
    version="0.1.0",
    description="Solo-style SO-101 LeRobot CLI for setup, calibration, teleop, recording, training, replay, and agent control.",
    py_modules=[
        "pbl_cli",
        "robot_api",
        "connect_test",
        "local_teleop",
        "local_robot_admin",
        "local_record",
        "local_train",
        "local_inference",
        "camera_runtime",
        "automatic_agent_controller",
        "visual_agent_runner",
        "generic_pose_action",
        "save_position",
        "manual_control",
    ],
    install_requires=[
        "lerobot[feetech]",
        "openai",
    ],
    entry_points={
        "console_scripts": [
            "pbl=pbl_cli:main",
        ],
    },
    python_requires=">=3.11",
)
