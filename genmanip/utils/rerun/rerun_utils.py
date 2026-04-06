import os
import tempfile
from dataclasses import dataclass
from enum import Enum

import numpy as np

try:
    import rerun as rr
except ImportError:
    rr = None

try:
    import mediapy
    from genmanip.utils.standalone.frame_utils import (
        create_video_from_image_list_with_mediapy as _create_video,
    )
except (ImportError, ModuleNotFoundError, OSError):
    try:
        from genmanip.utils.standalone.frame_utils import (
            create_video_from_image_list as _create_video,
        )
    except (ImportError, ModuleNotFoundError, AttributeError):
        _create_video = None

RERUN_HAS_WARNING = False


def to_np(x):
    if isinstance(x, np.ndarray):
        return x
    return np.asarray(x)


class RobotType(Enum):
    FRANKA_PANDA_HAND = "manip/franka/panda_hand"
    FRANKA_ROBOTIQ = "manip/franka/robotiq"
    ALOHA_PIPER = "manip/mobile_aloha/piper"
    R5A_LIFT2 = "manip/lift2/R5a"


@dataclass
class RobotActionConfig:
    robot_type: RobotType
    is_dual_arm: bool
    left_arm_slice: tuple[int, int]
    left_gripper_slice: tuple[int, int]
    right_arm_slice: tuple[int, int] | None = None
    right_gripper_slice: tuple[int, int] | None = None
    base_slice: tuple[int, int] | None = None
    total_dim: int = 0

    def __post_init__(self) -> None:
        if self.total_dim == 0:
            end_vals = [self.left_arm_slice[1], self.left_gripper_slice[1]]
            if self.right_arm_slice:
                end_vals.append(self.right_arm_slice[1])
            if self.right_gripper_slice:
                end_vals.append(self.right_gripper_slice[1])
            if self.base_slice:
                end_vals.append(self.base_slice[1])
            self.total_dim = max(end_vals)


ROBOT_ACTION_CONFIGS: dict[str, RobotActionConfig] = {
    "manip/franka/panda_hand": RobotActionConfig(
        robot_type=RobotType.FRANKA_PANDA_HAND,
        is_dual_arm=False,
        left_arm_slice=(0, 7),
        left_gripper_slice=(7, 9),
        total_dim=9,
    ),
    "manip/franka/robotiq": RobotActionConfig(
        robot_type=RobotType.FRANKA_ROBOTIQ,
        is_dual_arm=False,
        left_arm_slice=(0, 7),
        left_gripper_slice=(7, 13),
        total_dim=13,
    ),
    "manip/mobile_aloha/piper": RobotActionConfig(
        robot_type=RobotType.ALOHA_PIPER,
        is_dual_arm=True,
        left_arm_slice=(0, 6),
        left_gripper_slice=(6, 8),
        right_arm_slice=(8, 14),
        right_gripper_slice=(14, 16),
        base_slice=(16, 19),
        total_dim=19,
    ),
    "manip/lift2/R5a": RobotActionConfig(
        robot_type=RobotType.R5A_LIFT2,
        is_dual_arm=True,
        left_arm_slice=(0, 6),
        left_gripper_slice=(6, 8),
        right_arm_slice=(8, 14),
        right_gripper_slice=(14, 16),
        base_slice=(16, 19),
        total_dim=19,
    ),
}


def get_robot_action_config(robot_id: str) -> RobotActionConfig | None:
    return ROBOT_ACTION_CONFIGS.get(robot_id)


def _labels_for_joint_state(count: int, cfg: RobotActionConfig | None) -> list[str]:
    if cfg is None or not cfg.is_dual_arm:
        return [f"j{i}" for i in range(count)]
    left_len = cfg.left_arm_slice[1] - cfg.left_arm_slice[0]
    right_len = 0
    if cfg.right_arm_slice:
        right_len = cfg.right_arm_slice[1] - cfg.right_arm_slice[0]
    if left_len + right_len != count:
        return [f"j{i}" for i in range(count)]
    labels = [f"left_j{i}" for i in range(left_len)]
    labels += [f"right_j{i}" for i in range(right_len)]
    return labels


def _labels_for_gripper_state(count: int, cfg: RobotActionConfig | None) -> list[str]:
    if cfg is None or not cfg.is_dual_arm:
        return [f"g{i}" for i in range(count)]
    left_len = cfg.left_gripper_slice[1] - cfg.left_gripper_slice[0]
    right_len = 0
    if cfg.right_gripper_slice:
        right_len = cfg.right_gripper_slice[1] - cfg.right_gripper_slice[0]
    if left_len + right_len != count:
        return [f"g{i}" for i in range(count)]
    labels = [f"left_g{i}" for i in range(left_len)]
    labels += [f"right_g{i}" for i in range(right_len)]
    return labels


def _labels_for_base_state(count: int) -> list[str]:
    if count == 3:
        return ["x", "y", "theta"]
    return [f"b{i}" for i in range(count)]


def _min_len(*vals: int | list | None) -> int:
    lengths = []
    for v in vals:
        if v is None:
            continue
        if isinstance(v, int):
            lengths.append(v)
        else:
            lengths.append(len(v))
    if not lengths:
        return 0
    return min(lengths)


def _try_send_blueprint(camera_names: list[str]) -> None:
    if rr is None or not hasattr(rr, "send_blueprint"):
        return
    try:
        import rerun.blueprint as rrb
    except (ImportError, ModuleNotFoundError):
        return

    required = ("Blueprint", "Horizontal", "Spatial2DView", "TimeSeriesView")
    if any(not hasattr(rrb, name) for name in required):
        return

    try:
        cam_views = [
            rrb.Spatial2DView(origin=f"cameras/{name}") for name in camera_names
        ]
        if cam_views:
            top = rrb.Horizontal(*cam_views) if len(cam_views) > 1 else cam_views[0]
        else:
            top = None

        bottom_views = [
            rrb.TimeSeriesView(origin="plots/joints"),
            rrb.TimeSeriesView(origin="plots/gripper"),
            rrb.TimeSeriesView(origin="plots/base"),
        ]
        bottom = (
            rrb.Horizontal(*bottom_views) if len(bottom_views) > 1 else bottom_views[0]
        )

        containers = [c for c in (top, bottom) if c is not None]
        if not containers:
            return

        if hasattr(rrb, "Vertical"):
            blueprint = rrb.Blueprint(rrb.Vertical(*containers))
        else:
            blueprint = rrb.Blueprint(*containers)
        rr.send_blueprint(blueprint)
    except (RuntimeError, TypeError, ValueError, AttributeError):
        return


def _can_use_video() -> bool:
    """Check if rerun supports video-based logging."""
    return (
        rr is not None
        and _create_video is not None
        and hasattr(rr, "AssetVideo")
        and hasattr(rr, "VideoFrameReference")
    )


def log_episode_to_rerun(
    rgb_dict,
    action_list,
    joint_list,
    gripper_list,
    base_list,
    rrd_path,
    *,
    robot_id=None,
    app_id="episode_viewer",
    fps=30,
):
    global RERUN_HAS_WARNING
    if rr is None:
        if not RERUN_HAS_WARNING:
            print("=" * 100)
            for _ in range(3):
                print(
                    "Rerun is not installed, server data will not be logged to rerun, pip install rerun-sdk==0.28.2; pip install numpy==1.26.4 to enable"
                )
            print("=" * 100)
            RERUN_HAS_WARNING = True
        return
    rr.init(app_id, spawn=False)

    if rgb_dict:
        _try_send_blueprint(list(rgb_dict.keys()))

    rgb_len = None
    if rgb_dict and all(len(rgb_list) > 0 for rgb_list in rgb_dict.values()):
        rgb_len = min(len(rgb_list) for rgb_list in rgb_dict.values())
    min_list_len = _min_len(joint_list, gripper_list, base_list, rgb_len)
    if min_list_len <= 0:
        print(
            "Warning: skip saving rerun episode because inputs are empty "
            f"(rgb_len={rgb_len}, "
            f"joint_len={0 if joint_list is None else len(joint_list)}, "
            f"gripper_len={0 if gripper_list is None else len(gripper_list)}, "
            f"base_len={0 if base_list is None else len(base_list)})"
        )
        return

    cfg = get_robot_action_config(robot_id) if robot_id else None
    joint_labels = None
    gripper_labels = None
    base_labels = None

    # -- Video-based image logging --
    use_video = _can_use_video() and rgb_dict and rgb_len is not None
    temp_video_paths: dict[str, str] = {}
    if use_video:
        for camera_name, rgb_list in rgb_dict.items():
            frames = rgb_list[:rgb_len]
            if not frames:
                continue
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mp4")
            os.close(tmp_fd)
            try:
                if _create_video is None:
                    raise ValueError("Cannot create video but _can_use_video() is True")
                _create_video(frames, tmp_path, fps=fps)
                video_asset = rr.AssetVideo(path=tmp_path)
                rr.log(f"cameras/{camera_name}", video_asset, static=True)
                temp_video_paths[camera_name] = tmp_path
            except (
                FileNotFoundError,
                OSError,
                RuntimeError,
                ValueError,
                TypeError,
            ) as e:
                print(
                    f"Warning: video logging failed for {camera_name}: {e}, falling back to per-frame images"
                )
                use_video = False
                try:
                    os.unlink(tmp_path)
                except FileNotFoundError:
                    # Temporary video may be removed before cleanup.
                    pass
                except OSError as exc:
                    print(
                        f"Warning: failed to cleanup temporary video file {tmp_path}: {exc}"
                    )
                # Clean up any already-created temp videos
                for p in temp_video_paths.values():
                    try:
                        os.unlink(p)
                    except FileNotFoundError:
                        # Another path may have already removed this temporary file.
                        pass
                    except OSError as exc:
                        print(
                            f"Warning: failed to cleanup previous temporary video file {p}: {exc}"
                        )
                temp_video_paths.clear()
                break

    for t in range(min_list_len):
        rr.set_time("stable_time", duration=t / float(fps))

        if rgb_dict and rgb_len is not None:
            if use_video:
                for camera_name in temp_video_paths:
                    rr.log(
                        f"cameras/{camera_name}",
                        rr.VideoFrameReference(
                            timestamp=rr.components.VideoTimestamp(
                                nanoseconds=int(t / float(fps) * 1e9)
                            )
                        ),
                    )
            else:
                for camera_name, rgb_list in rgb_dict.items():
                    rr.log(f"cameras/{camera_name}", rr.Image(rgb_list[t]))

        if joint_list is not None:
            joints = to_np(joint_list[t]).astype(np.float32).reshape(-1)
            if joint_labels is None:
                joint_labels = _labels_for_joint_state(joints.size, cfg)
            for i, v in enumerate(joints):
                name = joint_labels[i] if i < len(joint_labels) else f"j{i}"
                rr.log(f"plots/joints/{name}", rr.Scalars(float(v)))

        if gripper_list is not None:
            gripper = to_np(gripper_list[t]).astype(np.float32).reshape(-1)
            if gripper_labels is None:
                gripper_labels = _labels_for_gripper_state(gripper.size, cfg)
            for i, v in enumerate(gripper):
                name = gripper_labels[i] if i < len(gripper_labels) else f"g{i}"
                rr.log(f"plots/gripper/{name}", rr.Scalars(float(v)))

        if base_list is not None:
            base = to_np(base_list[t]).astype(np.float32).reshape(-1)
            if base_labels is None:
                base_labels = _labels_for_base_state(base.size)
            for i, v in enumerate(base):
                name = base_labels[i] if i < len(base_labels) else f"b{i}"
                rr.log(f"plots/base/{name}", rr.Scalars(float(v)))

    rr.save(rrd_path)
    print(f"Saved: {rrd_path}")

    for p in temp_video_paths.values():
        try:
            os.unlink(p)
        except FileNotFoundError:
            # File may already be gone after log finalization.
            pass
        except OSError as exc:
            print(
                f"Warning: failed to cleanup temporary video file after logging: {p}: {exc}"
            )
            pass
