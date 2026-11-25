# Running DLIO in a container (Podman or Docker)

These instructions build and run a ROS 2 Jazzy container image with DLIO.
The `master` branch of this repository is for ROS 1. The ROS 2 version is in the `feature/ros2` branch of the
[original repository](https://github.com/vectr-ucla/direct_lidar_inertial_odometry/tree/feature/ros2), and that is
the one built here.

The instructions work with both [Podman](https://podman.io/) and [Docker](https://docs.docker.com/), because the two tools
take the same command-line syntax for everything used here. Pick one and set a shell variable so the commands
below can be copied as they are:

```bash
ENGINE=podman   # or: ENGINE=docker
```

Differences between the two:

| | Podman | Docker |
|---|---|---|
| Daemon | None. Containers are child processes of the user | Run by the `dockerd` daemon, usually as root |
| Run as normal user | Yes (rootless by default) | Only if the user is in the `docker` group, or with `sudo` |
| X11 access (`xhost`) | `xhost +local:$USER` | `xhost +local:root` (the container runs as root) |
| Image names | Use fully qualified names (`docker.io/...`, `ghcr.io/...`) | `docker.io/` can be left out |

Podman can also replace Docker transparently: `alias docker=podman`, or install the `podman-docker` package.

## Create the software image

Start a container from the official ROS 2 Jazzy image:

```bash
$ENGINE pull docker.io/osrf/ros:jazzy-desktop-full
$ENGINE run -it --name direct_lio docker.io/osrf/ros:jazzy-desktop-full
```

Inside the container, install the dependencies, then clone and build the ROS 2 branch of DLIO:

```bash
apt update && apt -y upgrade
apt install libomp-dev libpcl-dev libeigen3-dev

mkdir -p /ros2_ws/src
cd /ros2_ws/src/
git clone -b feature/ros2 https://github.com/vectr-ucla/direct_lidar_inertial_odometry.git
cd ..
colcon build --symlink-install --packages-select direct_lidar_inertial_odometry
exit
```

Save the container as a new image and, optionally, publish it to the GitHub Container Registry.
To push, you must log in first with a GitHub personal access token that has the `write:packages` scope:

```bash
$ENGINE commit direct_lio ghcr.io/transmisiones-centauro/direct_lio:latest
$ENGINE rm direct_lio

$ENGINE login ghcr.io
$ENGINE push ghcr.io/transmisiones-centauro/direct_lio:latest
```

Replace `ghcr.io/transmisiones-centauro/direct_lio` with your own registry and namespace if needed.

## Run the container

Allow the container to open windows on the host X server (needed for RViz):

```bash
xhost +local:$USER   # Podman (rootless)
xhost +local:root    # Docker
```

Then start the container:

```bash
$ENGINE run -it --rm --name direct_lio \
    --env="DISPLAY=$DISPLAY" \
    --env="QT_X11_NO_MITSHM=1" \
    --volume="/tmp/.X11-unix:/tmp/.X11-unix:rw" \
    --device /dev/dri \
    ghcr.io/transmisiones-centauro/direct_lio:latest
```

Useful additional options:

- `--net=host --ipc=host`: share the host network and IPC, so that ROS 2 nodes inside the container can discover
  nodes on the host or on the robot (for example the LiDAR and IMU drivers).
- `--volume="$HOME/rosbags:/rosbags:rw"`: make a host directory with rosbags available inside the container.
- `--volume="$HOME/maps:/maps:rw"`: keep the maps saved by DLIO after the container is removed.
- `--security-opt label=disable`: on SELinux hosts (Fedora, RHEL), allows the container to access the X11 socket.

## Use DLIO

DLIO needs a `sensor_msgs/PointCloud2` topic and a 6-axis `sensor_msgs/Imu` topic. The LiDAR and the IMU must be
time-synchronized.

### Parameters

The launch file loads two configuration files from `/ros2_ws/src/direct_lidar_inertial_odometry/cfg/`.
Because the package is built with `--symlink-install`, changes to these files take effect the next time DLIO is
launched, without rebuilding.

**Frames and clock (`cfg/params.yaml`)**

```yaml
    use_sim_time: true
    frames/odom: odom
    frames/baselink: base_link
    frames/lidar: lidar
    frames/imu: imu
```

- DLIO publishes the odometry and the TF `odom` → `base_link`. It also publishes `base_link` → `imu` and
  `base_link` → `lidar`, built from the extrinsics in `dlio.yaml`.
- Change the frame names to match your robot. If the robot already publishes the TF between its base and the
  sensors (for example with `robot_state_publisher`), give DLIO different `lidar` and `imu` frame names, so that
  the same frame doesn't get two parents in the TF tree.
- The map node reads its frame from a different parameter, `odom/odom_frame` (default `odom`). If you change
  `frames/odom`, add `odom/odom_frame` with the same value.
- `use_sim_time: true` is correct for rosbags, played with `ros2 bag play --clock`. Set it to `false` when
  running with live sensors.

**Deskewing (`cfg/dlio.yaml`)**

```yaml
    pointcloud/deskew: true
```

- Deskewing corrects the motion distortion inside each scan. It needs a per-point timestamp field in the point
  cloud: `t` (Ouster), `time` (Velodyne) or `timestamp` (Hesai, Livox).
- If none of these fields is present, DLIO turns deskewing off by itself.
- Set it to `false` if the point timestamps of your sensor are unreliable, or to compare results with and without it.

**IMU and LiDAR position (`cfg/dlio.yaml`)**

```yaml
    extrinsics/baselink2imu/t: [ 0.006253, -0.011775, 0.007645 ]
    extrinsics/baselink2imu/R: [ 1.,  0.,  0.,
                                 0.,  1.,  0.,
                                 0.,  0.,  1. ]
    extrinsics/baselink2lidar/t: [ 0.,  0.,  0. ]
    extrinsics/baselink2lidar/R: [ 1.,  0.,  0.,
                                   0.,  1.,  0.,
                                   0.,  0.,  1. ]
```

- `t` is the position of the IMU (or LiDAR) in the `base_link` frame, in meters. `R` is its rotation, written as
  a 3×3 matrix row by row.
- The default values are for the Ouster sensors used by the DLIO authors. Replace them with the values for your robot.
- To use the LiDAR itself as `base_link`, leave `baselink2lidar` as the identity and set `baselink2imu` to the
  position of the IMU relative to the LiDAR. For a LiDAR with an integrated IMU, the manufacturer's datasheet gives
  this offset.
- The published image uses `pointcloud/deskew: false` and `extrinsics/baselink2imu/t: [ 0.011, 0.02329, -0.04412 ]`,
  the position of the integrated IMU of a Livox MID-360 relative to its LiDAR, with `base_link` at the LiDAR.
- The IMU intrinsics (`imu/intrinsics/...`) can be left at their ideal default values, as long as
  `imu/calibration: true`. Keep the sensor still for the first seconds, while DLIO calibrates the IMU biases
  (`odom/imu/calibration/time` in `params.yaml`, 3 s by default).

### Run

Inside the container, source the workspace and launch DLIO with your topic names:

```bash
source /ros2_ws/install/setup.bash
ros2 launch direct_lidar_inertial_odometry dlio.launch.py rviz:=true \
    pointcloud_topic:=/robot/lidar imu_topic:=/robot/imu
```

To process a rosbag, open a second shell in the same container from another terminal on the host, and play it:

```bash
$ENGINE exec -it direct_lio bash
# inside the container:
source /ros2_ws/install/setup.bash
ros2 bag play --clock /rosbags/<rosbag>
```

To save the generated map in `.pcd` format, call the following service:

```bash
ros2 service call /save_pcd direct_lidar_inertial_odometry/srv/SavePCD "{'leaf_size': 0.2, 'save_path': '/maps'}"
```

Test data (Ouster OS1-32 and OSDome rosbags) is linked from the
[original README](https://github.com/vectr-ucla/direct_lidar_inertial_odometry/tree/feature/ros2#test-data).
