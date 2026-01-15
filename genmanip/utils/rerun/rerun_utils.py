import numpy as np

try:
    import rerun as rr
except ImportError:
    rr = None

RERUN_HAS_WARNING = False


def to_np(x):
    if isinstance(x, np.ndarray):
        return x
    return np.asarray(x)


def log_episode_to_rerun(
    rgb_dict,
    action_list,
    state_list,
    rrd_path,
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

    T = min(
        min(len(rgb_list) for rgb_list in rgb_dict.values()),
        len(action_list),
        len(state_list),
    )
    assert T > 0, "Empty lists?"

    for t in range(T):
        rr.set_time("stable_time", duration=t / float(fps))
        for camera_name, rgb_list in rgb_dict.items():
            rr.log(f"cam/{camera_name}", rr.Image(rgb_list[t]))

        a = to_np(action_list[t]).astype(np.float32).reshape(-1)
        s = to_np(state_list[t]).astype(np.float32).reshape(-1)

        for i, v in enumerate(a):
            rr.log(f"actions/action/action_{str(i).zfill(2)}", rr.Scalars(float(v)))
        for i, v in enumerate(s):
            rr.log(f"states/state/state_{str(i).zfill(2)}", rr.Scalars(float(v)))
    rr.save(rrd_path)
    print(f"Saved: {rrd_path}")
