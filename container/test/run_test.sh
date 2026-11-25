#!/bin/bash
# Functional test of the DLIO image: launch DLIO, feed it synthetic sensor data and check its odometry.
# Run it inside the container:
#   podman run --rm ghcr.io/transmisiones-centauro/direct_lio:latest bash /test/run_test.sh

source /opt/ros/${ROS_DISTRO}/setup.bash
source /ros2_ws/install/setup.bash

echo "== Package"
ros2 pkg prefix direct_lidar_inertial_odometry || exit 1

echo "== Launching DLIO"
ros2 launch direct_lidar_inertial_odometry dlio.launch.py rviz:=false \
    pointcloud_topic:=points_raw imu_topic:=imu_raw > /tmp/dlio.log 2>&1 &
LAUNCH_PID=$!
sleep 5

echo "== Publishing synthetic sensor data"
python3 /test/synthetic_sensors.py
RESULT=$?

# Stop DLIO. Background jobs of a non-interactive shell ignore SIGINT, so send SIGTERM,
# and kill whatever is still running after 10 seconds.
kill -TERM $LAUNCH_PID 2>/dev/null
for _ in $(seq 10); do kill -0 $LAUNCH_PID 2>/dev/null || break; sleep 1; done
pkill -KILL -f dlio_ 2>/dev/null
kill -KILL $LAUNCH_PID 2>/dev/null

if [ $RESULT -ne 0 ]; then
    echo "== DLIO output"
    tail -n 50 /tmp/dlio.log
fi
exit $RESULT
