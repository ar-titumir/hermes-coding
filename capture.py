import cv2
import argparse
import time
import os

# Camera configuration
IP = "192.168.0.121"
USERNAME = "titumir"
PASSWORD = "titumir1603"

# Command-line argument
parser = argparse.ArgumentParser()

parser.add_argument(
    "-t",
    type=int,
    default=2,
    help="Capture duration in seconds (default: 2)"
)

args = parser.parse_args()

# Create output folder
os.makedirs("captures", exist_ok=True)

# RTSP URL
url = f"rtsp://{USERNAME}:{PASSWORD}@{IP}:554/stream1"

# -----------------------------
# Connect with 5-second timeout
# -----------------------------
print(f"Connecting to {IP}...")

cap = cv2.VideoCapture(url)

start_connect = time.time()
connected = False

while time.time() - start_connect < 5:
    if cap.isOpened():
        connected = True
        break

    time.sleep(0.1)

if not connected:
    cap.release()
    print("Could not connect. Exiting.")
    exit()

# -----------------------------
# Capture images
# -----------------------------
print(f"Connected. Capturing for {args.t} seconds...")

start_time = time.time()
image_count = 0
next_capture = start_time

while time.time() - start_time < args.t:

    if time.time() < next_capture:
        time.sleep(0.01)
        continue

    ret, frame = cap.read()

    if ret:
        image_count += 1

        filename = f"captures/image_{image_count:03d}.jpg"
        cv2.imwrite(filename, frame)

        print(f"Saved: {filename}")

    next_capture += 1

cap.release()

print(f"Finished. Total images: {image_count}")
