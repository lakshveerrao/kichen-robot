from __future__ import annotations

import importlib
import math
import time
from collections.abc import Mapping
from typing import Any


DEFAULT_SPEED_SCALE = 0.2
MAX_ALLOWED_SPEED_SCALE = 10.0
MOVE_STEP_SECONDS = 0.05
MAX_STEP_UNITS = 5.0
BODY_JOINT_LIMIT_DEGREES = 360.0
GRIPPER_MIN = -5.0
GRIPPER_MAX = 105.0


class RobotApiError(RuntimeError):
    pass


def _load_so101_classes():
    """Load SO-101 classes from official LeRobot paths.

    Current LeRobot exposes SO101Follower and SO101FollowerConfig from
    lerobot.robots.so_follower. Some older installs used
    lerobot.robots.so101_follower, so this wrapper tries both without forcing
    the rest of this project to care about the installed package layout.
    """
    candidates = (
        "lerobot.robots.so_follower",
        "lerobot.robots.so101_follower",
    )
    last_error: Exception | None = None
    for module_name in candidates:
        try:
            module = importlib.import_module(module_name)
            return module.SO101Follower, module.SO101FollowerConfig, module_name
        except (ImportError, AttributeError) as exc:
            last_error = exc
    raise RobotApiError(
        "Could not import SO101Follower from LeRobot. Install LeRobot in this "
        "Python environment, then run this script again."
    ) from last_error


def _as_float_position(position: Mapping[str, Any]) -> dict[str, float]:
    converted: dict[str, float] = {}
    for key, value in position.items():
        if not key.endswith(".pos"):
            raise RobotApiError(f"Invalid joint key {key!r}; expected names ending in '.pos'.")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise RobotApiError(f"Invalid value for {key}: {value!r}") from exc
        if not math.isfinite(number):
            raise RobotApiError(f"Invalid non-finite value for {key}: {value!r}")
        converted[key] = number
    return converted


def validate_position(position: Any) -> dict[str, float]:
    if not isinstance(position, Mapping) or not position:
        raise RobotApiError("Position must be a non-empty mapping of joint names to values.")

    converted = _as_float_position(position)
    for key, value in converted.items():
        joint = key.removesuffix(".pos")
        if joint == "gripper":
            if not GRIPPER_MIN <= value <= GRIPPER_MAX:
                raise RobotApiError(f"{key}={value} is outside the expected gripper range.")
        elif not -BODY_JOINT_LIMIT_DEGREES <= value <= BODY_JOINT_LIMIT_DEGREES:
            raise RobotApiError(f"{key}={value} is outside the expected joint range.")
    return converted


def _safe_speed_scale(speed_scale: Any) -> float:
    try:
        scale = float(speed_scale)
    except (TypeError, ValueError) as exc:
        raise RobotApiError(f"Invalid speed_scale: {speed_scale!r}") from exc
    if not 0.0 < scale <= MAX_ALLOWED_SPEED_SCALE:
        raise RobotApiError(
            f"speed_scale must be > 0 and <= {MAX_ALLOWED_SPEED_SCALE}; got {scale}."
        )
    return scale


def connect_robot(config: Mapping[str, Any]):
    if config.get("robot_type", "so101_follower") != "so101_follower":
        raise RobotApiError("This milestone only supports robot_type='so101_follower'.")

    port = config.get("robot_port")
    if not port:
        raise RobotApiError("Missing robot_port in config.json.")

    robot_id = config.get("robot_id") or "kitchen_stirrer_follower"
    SO101Follower, SO101FollowerConfig, module_name = _load_so101_classes()
    print(f"Using LeRobot API from {module_name}")

    # max_relative_target is an official SO follower safety guard. The replay
    # function also interpolates small steps, so this is a second line of
    # defense against accidental large jumps.
    robot_config = SO101FollowerConfig(
        port=port,
        id=robot_id,
        max_relative_target=5.0,
        cameras=_build_camera_configs(config),
    )
    robot = SO101Follower(robot_config)
    _add_write_retries(robot)
    robot.connect()
    if hasattr(robot, "is_connected") and not robot.is_connected:
        raise RobotApiError("LeRobot did not report the robot as connected.")
    return robot


def _build_camera_configs(config: Mapping[str, Any]) -> dict[str, Any]:
    """Build optional LeRobot OpenCV camera configs.

    Cameras are disabled by default for motion scripts because a camera failure
    should not prevent emergency arm control. Set enable_robot_cameras=true in
    config.json if you want LeRobot observations to include camera frames.
    """
    if not config.get("enable_robot_cameras", False):
        return {}

    try:
        from lerobot.cameras.opencv import OpenCVCameraConfig
    except ImportError as exc:
        raise RobotApiError("LeRobot OpenCV camera support is not installed.") from exc

    width = int(config.get("camera_width", 640))
    height = int(config.get("camera_height", 480))
    fps = int(config.get("camera_fps", 30))
    camera_indices = config.get("camera_indices", [0, 1])
    cameras: dict[str, Any] = {}
    for index in camera_indices:
        index_int = int(index)
        cameras[f"camera_{index_int}"] = OpenCVCameraConfig(
            index_or_path=index_int,
            fps=fps,
            width=width,
            height=height,
        )
    return cameras


def _add_write_retries(robot: Any) -> None:
    """Make Feetech serial writes tolerate an occasional missed status packet.

    LeRobot's SO follower configure path writes settings such as Torque_Enable
    and Lock with the default retry count. On Windows/USB serial adapters, the
    Feetech bus can occasionally miss one status packet even though the motor is
    present. This keeps the official API behavior but asks LeRobot to retry
    single-motor writes a few times.
    """
    bus = getattr(robot, "bus", None)
    original_write = getattr(bus, "write", None)
    if not callable(original_write):
        return

    def write_with_retry(*args: Any, **kwargs: Any):
        kwargs["num_retry"] = max(int(kwargs.get("num_retry", 1)), 5)
        return original_write(*args, **kwargs)

    bus.write = write_with_retry


def disconnect_robot(robot: Any) -> None:
    if robot is None:
        return
    try:
        if not hasattr(robot, "is_connected") or robot.is_connected:
            robot.disconnect()
    except Exception as exc:
        print(f"Warning: disconnect failed: {exc}")


def read_current_position(robot: Any) -> dict[str, float]:
    obs = robot.get_observation()
    position = {key: value for key, value in obs.items() if key.endswith(".pos")}
    return validate_position(position)


def _send_position(robot: Any, position: Mapping[str, float]) -> dict[str, float]:
    sent = robot.send_action(dict(position))
    return _as_float_position(sent) if isinstance(sent, Mapping) else dict(position)


def move_to_position(robot: Any, target_position: Mapping[str, Any], speed_scale: Any) -> None:
    scale = _safe_speed_scale(speed_scale)
    target = validate_position(target_position)
    current = read_current_position(robot)

    missing = sorted(set(current) ^ set(target))
    if missing:
        raise RobotApiError(f"Target position joint set does not match robot joints: {missing}")

    max_delta = max(abs(target[key] - current[key]) for key in target)
    if max_delta == 0:
        print("Already at target position.")
        return

    # At default speed_scale=0.2 this commands about 0.8 degree/value units per
    # step at 20 Hz. Larger values are capped by _safe_speed_scale and LeRobot's
    # max_relative_target guard.
    max_step_units = min(MAX_STEP_UNITS, max(0.25, 4.0 * scale))
    steps = max(1, math.ceil(max_delta / max_step_units))

    for step in range(1, steps + 1):
        fraction = step / steps
        waypoint = {
            key: current[key] + (target[key] - current[key]) * fraction
            for key in target
        }
        _send_position(robot, waypoint)
        time.sleep(MOVE_STEP_SECONDS)


def stop_robot(robot: Any) -> None:
    if robot is None:
        return
    try:
        current = read_current_position(robot)
        _send_position(robot, current)
        print("Emergency stop: commanded current position to halt motion.")
    except Exception as exc:
        print(f"Emergency stop: could not command current position: {exc}")

    bus = getattr(robot, "bus", None)
    disable_torque = getattr(bus, "disable_torque", None)
    if callable(disable_torque):
        try:
            disable_torque()
            print("Emergency stop: torque disabled.")
        except Exception as exc:
            print(f"Emergency stop: could not disable torque: {exc}")
