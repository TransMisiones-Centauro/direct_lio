# ROS 2 Jazzy image with DLIO (Direct LiDAR-Inertial Odometry).
#
# Build from the root of the repository:
#   podman build -f container/Dockerfile -t ghcr.io/transmisiones-centauro/direct_lio:latest .
#   docker build -f container/Dockerfile -t ghcr.io/transmisiones-centauro/direct_lio:latest .

FROM docker.io/osrf/ros:jazzy-desktop-full

# The ROS 2 version of DLIO is in the feature/ros2 branch of the original repository.
ARG DLIO_REPO=https://github.com/vectr-ucla/direct_lidar_inertial_odometry.git
ARG DLIO_BRANCH=feature/ros2

RUN apt-get update \
    && apt-get install -y --no-install-recommends libomp-dev libpcl-dev libeigen3-dev git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /ros2_ws/src
RUN git clone --depth 1 -b "${DLIO_BRANCH}" "${DLIO_REPO}" direct_lidar_inertial_odometry

WORKDIR /ros2_ws
RUN . /opt/ros/${ROS_DISTRO}/setup.sh \
    && colcon build --symlink-install --packages-select direct_lidar_inertial_odometry \
    && echo "source /ros2_ws/install/setup.bash" >> /root/.bashrc

# Functional test, used by the GitHub workflow (see container/test/).
COPY container/test /test

CMD ["bash"]
