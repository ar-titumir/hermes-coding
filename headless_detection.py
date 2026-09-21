import cv2
import time
import threading
import queue
import requests
from ultralytics import YOLO
from datetime import datetime

# ============================================================
# CAMERA
# ============================================================

IP = "192.168.0.121"
USERNAME = "titumir"
PASSWORD = "titumir1603"

RTSP_URL = f"rtsp://{USERNAME}:{PASSWORD}@{IP}:554/stream1"

RESIZE_FX = 0.5
RESIZE_FY = 0.5

TARGET_FPS = 10
FRAME_INTERVAL = 1.0 / TARGET_FPS


# ============================================================
# YOLO / DETECTION SETTINGS
# ============================================================

YOLO_MODEL_PATH = "yolov8n.pt"
PERSON_CLASS = 0
YOLO_CONF = 0.40

# Rule 1: don't feed every motion frame to YOLO — only every Nth one.
YOLO_SKIP_INTERVAL = 2

# Rule 2: after a successful detection, don't call YOLO again for 1s,
# even if motion is still being seen.
PERSON_DETECT_COOLDOWN = 1.0  # seconds

# Frame is resized before motion detection, so contour areas shrink too.
MOTION_AREA = 375


# ============================================================
# TELEGRAM
# ============================================================

TELEGRAM_BOT_TOKEN = "8482466729:AAHYS2XW_9e8LX1xYZDZ3rhzB2DN-e9_cFQ"
TELEGRAM_CHAT_ID = "1338034914"
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

# Rule 3: don't send another alert for 15s after one goes out.
ALERT_INTERVAL = 5  # seconds


stop_event = threading.Event()


# ============================================================
# SERVICE 1 — FRAME CAPTURE
# Runs flat-out reading the RTSP stream and always keeps only the
# LATEST frame. This is what stops old/stale frames from piling up
# and the video looking laggy when other services are busy.
# ============================================================

class FrameGrabber(threading.Thread):

    def __init__(self, url):
        super().__init__(daemon=True)
        self.cap = cv2.VideoCapture(url)
        self.ok = self.cap.isOpened()
        self.lock = threading.Lock()
        self.frame = None

    def run(self):
        while not stop_event.is_set():
            ret, frame = self.cap.read()
            if not ret:
                continue
            with self.lock:
                self.frame = frame

    def get_frame(self):
        with self.lock:
            return None if self.frame is None else self.frame.copy()

    def release(self):
        self.cap.release()


# ============================================================
# SERVICE 2 — TELEGRAM ALERTS
# Its own thread + queue, with its own 15s rate limiting, so a slow
# network call never blocks capture, motion detection, or YOLO.
# ============================================================

class TelegramWorker(threading.Thread):

    def __init__(self):
        super().__init__(daemon=True)
        self.queue = queue.Queue()
        self.last_alert_time = 0.0

    def run(self):
        while not stop_event.is_set():
            try:
                message = self.queue.get(timeout=0.5)
            except queue.Empty:
                continue

            now = time.time()

            if now - self.last_alert_time < ALERT_INTERVAL:
                # Alert sent too recently — drop this one.
                continue

            try:
                response = requests.post(
                    TELEGRAM_URL,
                    data={"chat_id": TELEGRAM_CHAT_ID, "text": message},
                    timeout=10
                )
                response.raise_for_status()
                self.last_alert_time = now
                print("Telegram alert sent.")
            except Exception as e:
                print(f"Telegram error: {e}")

    def alert(self, message):
        self.queue.put(message)


# ============================================================
# SERVICE 3 — YOLO HUMAN DETECTION
# Its own thread + a size-1 queue: if it's still busy on a frame,
# newer frames get dropped rather than queued up, so YOLO never
# causes the main loop to fall behind.
# ============================================================

class YoloWorker(threading.Thread):

    def __init__(self, model_path, telegram_worker):
        super().__init__(daemon=True)
        self.model = YOLO(model_path)
        self.telegram_worker = telegram_worker
        self.in_queue = queue.Queue(maxsize=1)
        self.last_person_time = 0.0

    def in_cooldown(self):
        return (time.time() - self.last_person_time) < PERSON_DETECT_COOLDOWN

    def submit(self, frame):
        if self.in_queue.full():
            return  # busy — drop this frame instead of queueing it up
        try:
            self.in_queue.put_nowait(frame)
        except queue.Full:
            pass

    def run(self):
        while not stop_event.is_set():
            try:
                frame = self.in_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if self.in_cooldown():
                continue

            results = self.model(frame, conf=YOLO_CONF, verbose=False)

            person_detected = False

            for result in results:
                if result.boxes is None:
                    continue
                for box in result.boxes:
                    class_id = int(box.cls[0])
                    confidence = float(box.conf[0])
                    if class_id == PERSON_CLASS and confidence >= YOLO_CONF:
                        person_detected = True
                        break  # no display to draw boxes on
                if person_detected:
                    break

            if person_detected:
                self.last_person_time = time.time()
                print(datetime.now().strftime("%H:%M:%S") + ": PERSON DETECTED!")
                self.telegram_worker.alert(datetime.now().strftime("%H:%M:%S") + ": 🚨 Human detected by IP camera!")


# ============================================================
# MAIN — capture + motion detection + display
# (Motion detection stays cheap enough to run in the main loop;
# it's the heavy YOLO inference and network calls that are split
# off into their own threads.)
# ============================================================

def main():

    print(f"Connecting to {IP}...")

    grabber = FrameGrabber(RTSP_URL)

    if not grabber.ok:
        print("Could not connect. Exiting.")
        return

    grabber.start()
    print("Connected.")

    telegram_worker = TelegramWorker()
    telegram_worker.start()

    yolo_worker = YoloWorker(YOLO_MODEL_PATH, telegram_worker)
    yolo_worker.start()

    motion_detector = cv2.createBackgroundSubtractorMOG2(
        history=500,
        varThreshold=50,
        detectShadows=True
    )

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))

    motion_frame_counter = 0
    last_process_time = 0.0

    try:

        while True:

            frame = grabber.get_frame()

            if frame is None:
                time.sleep(0.01)
                continue

            now = time.time()

            # Frame-rate limiting: only process ~TARGET_FPS frames/sec.
            # The grabber thread keeps reading in the background, so
            # we always process the freshest frame available.
            if now - last_process_time < FRAME_INTERVAL:
                continue

            last_process_time = now

            frame = cv2.resize(frame, (0, 0), fx=RESIZE_FX, fy=RESIZE_FY)

            # ------------------------------------------------
            # MOTION DETECTION
            # ------------------------------------------------

            motion_mask = motion_detector.apply(frame)

            _, motion_mask = cv2.threshold(
                motion_mask, 200, 255, cv2.THRESH_BINARY
            )

            motion_mask = cv2.morphologyEx(
                motion_mask, cv2.MORPH_OPEN, kernel
            )

            motion_mask = cv2.dilate(motion_mask, kernel, iterations=2)

            contours, _ = cv2.findContours(
                motion_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            motion_detected = False

            for contour in contours:
                area = cv2.contourArea(contour)
                if area > MOTION_AREA:
                    motion_detected = True
                    break  # no display to draw on — just need the flag

            # ------------------------------------------------
            # HAND OFF TO YOLO SERVICE (non-blocking)
            # ------------------------------------------------

            if motion_detected and not yolo_worker.in_cooldown():
                motion_frame_counter += 1
                if motion_frame_counter % YOLO_SKIP_INTERVAL == 0:
                    yolo_worker.submit(frame.copy())

            # No display in headless mode — motion/detection state is
            # only reflected in the console prints and Telegram alerts.

    except KeyboardInterrupt:
        print("Stopping (Ctrl+C)...")

    finally:
        stop_event.set()
        grabber.release()
        print("Camera stopped.")


if __name__ == "__main__":
    main()
