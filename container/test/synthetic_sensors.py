#!/usr/bin/env python3
"""Publish a synthetic, static LiDAR + IMU stream and check that DLIO produces odometry.

The sensor sits still in the middle of a box-shaped room. The node publishes:
  - /clock          simulated time (DLIO's params.yaml sets use_sim_time: true)
  - /imu_raw        sensor_msgs/Imu at 200 Hz, measuring only gravity
  - /points_raw     sensor_msgs/PointCloud2 at 10 Hz, the walls, floor and ceiling of the room

It counts the messages on /dlio/odom_node/odom and exits with code 0 if enough of them arrive
and the estimated position stays close to the origin, or 1 otherwise.
"""

import sys

import numpy as np
import rclpy
from builtin_interfaces.msg import Time
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import Imu, PointCloud2, PointField
from sensor_msgs_py import point_cloud2
from std_msgs.msg import Header

IMU_RATE = 200.0
LIDAR_EVERY = 20             # one point cloud every 20 IMU messages = 10 Hz
DURATION = 25.0              # seconds of simulated data (DLIO calibrates the IMU for the first 3 s)
MIN_ODOM_MSGS = 50
MAX_DRIFT = 0.5              # meters


def room_cloud(step=0.1, size=(10.0, 8.0, 3.0)):
    """Points on the six faces of a box centred on the sensor."""
    sx, sy, sz = (s / 2 for s in size)
    xs = np.arange(-sx, sx + 1e-6, step)
    ys = np.arange(-sy, sy + 1e-6, step)
    zs = np.arange(-1.0, sz * 2 - 1.0 + 1e-6, step)  # floor 1 m below the sensor
    faces = []
    for x in (-sx, sx):
        y, z = np.meshgrid(ys, zs)
        faces.append(np.stack([np.full(y.size, x), y.ravel(), z.ravel()], axis=1))
    for y in (-sy, sy):
        x, z = np.meshgrid(xs, zs)
        faces.append(np.stack([x.ravel(), np.full(x.size, y), z.ravel()], axis=1))
    for z in (zs[0], zs[-1]):
        x, y = np.meshgrid(xs, ys)
        faces.append(np.stack([x.ravel(), y.ravel(), np.full(x.size, z)], axis=1))
    # A few boxes inside the room, so that the scene is not symmetric.
    for cx, cy, w in ((2.0, 1.5, 1.0), (-3.0, -2.0, 0.6), (1.0, -2.5, 0.8)):
        a = np.arange(-w / 2, w / 2 + 1e-6, step)
        b = np.arange(-1.0, 0.5, step)
        u, v = np.meshgrid(a, b)
        for off in (-w / 2, w / 2):
            faces.append(np.stack([np.full(u.size, cx + off), cy + u.ravel(), v.ravel()], axis=1))
            faces.append(np.stack([cx + u.ravel(), np.full(u.size, cy + off), v.ravel()], axis=1))
    pts = np.concatenate(faces).astype(np.float32)
    intensity = np.full((pts.shape[0], 1), 100.0, dtype=np.float32)
    return np.hstack([pts, intensity])


class SyntheticSensors(Node):
    def __init__(self):
        super().__init__('dlio_synthetic_test')
        self.clock_pub = self.create_publisher(Clock, '/clock', 10)
        self.imu_pub = self.create_publisher(Imu, 'imu_raw', 100)
        self.pc_pub = self.create_publisher(PointCloud2, 'points_raw', 10)
        self.create_subscription(Odometry, '/dlio/odom_node/odom', self.odom_cb, 10)

        self.cloud = room_cloud()
        self.fields = [
            PointField(name='x', offset=0, datatype=PointField.FLOAT32, count=1),
            PointField(name='y', offset=4, datatype=PointField.FLOAT32, count=1),
            PointField(name='z', offset=8, datatype=PointField.FLOAT32, count=1),
            PointField(name='intensity', offset=12, datatype=PointField.FLOAT32, count=1),
        ]
        self.tick = 0
        self.odom_count = 0
        self.last_position = None
        self.done = False
        self.create_timer(1.0 / IMU_RATE, self.step)

    def stamp(self):
        ns = int(1e9) + int(self.tick * 1e9 / IMU_RATE)  # start at t = 1 s
        return Time(sec=ns // 1_000_000_000, nanosec=ns % 1_000_000_000)

    def step(self):
        stamp = self.stamp()
        self.clock_pub.publish(Clock(clock=stamp))

        imu = Imu()
        imu.header = Header(stamp=stamp, frame_id='imu')
        imu.orientation.w = 1.0
        imu.linear_acceleration.z = 9.80665
        self.imu_pub.publish(imu)

        if self.tick % LIDAR_EVERY == 0:
            header = Header(stamp=stamp, frame_id='lidar')
            self.pc_pub.publish(point_cloud2.create_cloud(header, self.fields, self.cloud))

        self.tick += 1
        if self.tick >= DURATION * IMU_RATE:
            self.done = True

    def odom_cb(self, msg):
        self.odom_count += 1
        p = msg.pose.pose.position
        self.last_position = np.array([p.x, p.y, p.z])


def main():
    rclpy.init()
    node = SyntheticSensors()
    while rclpy.ok() and not node.done:
        rclpy.spin_once(node, timeout_sec=0.1)
    # Give DLIO a moment to process the last messages.
    for _ in range(20):
        rclpy.spin_once(node, timeout_sec=0.1)

    count, pos = node.odom_count, node.last_position
    node.destroy_node()
    rclpy.shutdown()

    print(f'Odometry messages received: {count} (minimum {MIN_ODOM_MSGS})')
    if pos is not None:
        drift = float(np.linalg.norm(pos))
        print(f'Final position: {pos.round(3).tolist()}, drift {drift:.3f} m (maximum {MAX_DRIFT} m)')
    if count < MIN_ODOM_MSGS or pos is None or np.linalg.norm(pos) > MAX_DRIFT:
        print('TEST FAILED')
        return 1
    print('TEST PASSED')
    return 0


if __name__ == '__main__':
    sys.exit(main())
