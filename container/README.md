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
time-synchronized. The extrinsic calibration between the robot base, the IMU and the LiDAR, and the IMU intrinsics,
are set in `/ros2_ws/src/direct_lidar_inertial_odometry/cfg/dlio.yaml`.

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
ros2 bag play /rosbags/<rosbag>
```

To save the generated map in `.pcd` format, call the following service:

```bash
ros2 service call /save_pcd direct_lidar_inertial_odometry/srv/SavePCD "{'leaf_size': 0.2, 'save_path': '/maps'}"
```

Test data (Ouster OS1-32 and OSDome rosbags) is linked from the
[original README](https://github.com/vectr-ucla/direct_lidar_inertial_odometry/tree/feature/ros2#test-data).
