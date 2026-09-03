import cv2
import numpy as np
import requests
import threading
import time
import math

# ============================================================
# CONFIGURATION
# ============================================================

CAMERA_URL = "http://192.168.137.54:81/stream"

ESP32_ALERT = "http://192.168.137.90/alert"
ESP32_STOP = "http://192.168.137.90/stop"

# Eye thresholds
EAR_CLOSED = 0.20
EAR_OPEN = 0.235

# Confirmation times
SLEEP_CONFIRM = 4.0
WAKE_CONFIRM = 1.5

# Temporal smoothing
HISTORY_SIZE = 30
OPEN_RATIO = 0.70
CLOSED_RATIO = 0.70

# Window
WINDOW_NAME = "Drowsiness Detection"

# ============================================================
# MEDIAPIPE
# ============================================================

import mediapipe as mp

mp_face_mesh = mp.solutions.face_mesh

face_mesh = mp_face_mesh.FaceMesh(
    static_image_mode=False,
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# ============================================================
# EYE LANDMARKS
# ============================================================

LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]

# ============================================================
# SHARED CAMERA FRAME
# ============================================================

latest_frame = None
frame_lock = threading.Lock()
camera_running = True


# ============================================================
# CAMERA READER THREAD
# ============================================================

def camera_reader():

    global latest_frame
    global camera_running

    while camera_running:

        try:

            print("Connecting to ESP32-CAM...")

            response = requests.get(
                CAMERA_URL,
                stream=True,
                timeout=(5, 10)
            )

            print("Camera connected!")

            buffer = bytearray()

            for chunk in response.iter_content(chunk_size=8192):

                if not camera_running:
                    break

                if not chunk:
                    continue

                buffer.extend(chunk)

                while True:

                    start = buffer.find(b"\xff\xd8")

                    if start == -1:
                        break

                    end = buffer.find(
                        b"\xff\xd9",
                        start + 2
                    )

                    if end == -1:
                        break

                    jpg = bytes(
                        buffer[start:end + 2]
                    )

                    del buffer[:end + 2]

                    img = cv2.imdecode(
                        np.frombuffer(
                            jpg,
                            dtype=np.uint8
                        ),
                        cv2.IMREAD_COLOR
                    )

                    if img is not None:

                        with frame_lock:
                            latest_frame = img

            response.close()

        except Exception as e:

            print("Camera connection error:", e)
            time.sleep(2)


# ============================================================
# START CAMERA THREAD
# ============================================================

camera_thread = threading.Thread(
    target=camera_reader,
    daemon=True
)

camera_thread.start()


# ============================================================
# EAR CALCULATION
# ============================================================

def distance(p1, p2):

    return math.sqrt(
        (p1[0] - p2[0]) ** 2 +
        (p1[1] - p2[1]) ** 2
    )


def calculate_ear(landmarks, eye_indices, width, height):

    points = []

    for index in eye_indices:

        lm = landmarks[index]

        x = int(lm.x * width)
        y = int(lm.y * height)

        points.append((x, y))

    p1, p2, p3, p4, p5, p6 = points

    vertical_1 = distance(p2, p6)
    vertical_2 = distance(p3, p5)

    horizontal = distance(p1, p4)

    if horizontal == 0:
        return 0.0

    ear = (
        vertical_1 + vertical_2
    ) / (2.0 * horizontal)

    return ear


# ============================================================
# ESP32 CONTROL
# ============================================================

def start_alarm():

    print("WAKE DETECTED -> STARTING SOFT ALARM")

    try:

        requests.get(
            ESP32_ALERT,
            timeout=2
        )

    except Exception as e:

        print("ESP32 ALERT ERROR:", e)


def stop_alarm():

    print("SLEEP CONFIRMED -> STOPPING ALARM")

    try:

        requests.get(
            ESP32_STOP,
            timeout=2
        )

    except Exception as e:

        print("ESP32 STOP ERROR:", e)


# ============================================================
# STATE MACHINE
# ============================================================

AWAKE = "AWAKE"
SLEEPING = "SLEEPING"
ALARM = "ALARM"

state = AWAKE

sleep_timer = None
wake_timer = None
alarm_sleep_timer = None

eye_history = []


# ============================================================
# WINDOW
# ============================================================

cv2.namedWindow(
    WINDOW_NAME,
    cv2.WINDOW_NORMAL
)

# Make the window large, BUT NOT OpenCV fullscreen.
cv2.resizeWindow(
    WINDOW_NAME,
    960,
    720
)


# ============================================================
# MAIN LOOP
# ============================================================

try:

    while True:

        # ----------------------------------------------------
        # GET LATEST CAMERA FRAME
        # ----------------------------------------------------

        with frame_lock:

            if latest_frame is None:
                frame = None
            else:
                frame = latest_frame.copy()

        if frame is None:

            blank = np.zeros(
                (480, 640, 3),
                dtype=np.uint8
            )

            cv2.putText(
                blank,
                "Connecting to ESP32-CAM...",
                (80, 240),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2
            )

            cv2.imshow(
                WINDOW_NAME,
                blank
            )

            if cv2.waitKey(1) & 0xFF in [ord("q"), 27]:
                break

            continue

        # ----------------------------------------------------
        # FRAME SIZE
        # ----------------------------------------------------

        height, width = frame.shape[:2]

        # ----------------------------------------------------
        # MEDIAPIPE
        # ----------------------------------------------------

        rgb = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        results = face_mesh.process(rgb)

        voted_state = "UNKNOWN"
        left_ear = 0.0
        right_ear = 0.0
        average_ear = 0.0

        landmarks = None

        # ----------------------------------------------------
        # FACE DETECTED
        # ----------------------------------------------------

        if results.multi_face_landmarks:

            face_landmarks = results.multi_face_landmarks[0]

            landmarks = face_landmarks.landmark

            # -----------------------------------------------
            # EAR
            # -----------------------------------------------

            left_ear = calculate_ear(
                landmarks,
                LEFT_EYE,
                width,
                height
            )

            right_ear = calculate_ear(
                landmarks,
                RIGHT_EYE,
                width,
                height
            )

            # -----------------------------------------------
            # GREEN EYE LINES ONLY
            # -----------------------------------------------

            for eye_indices in [
                LEFT_EYE,
                RIGHT_EYE
            ]:

                eye_points = []

                for index in eye_indices:

                    lm = landmarks[index]

                    x = int(lm.x * width)
                    y = int(lm.y * height)

                    eye_points.append(
                        (x, y)
                    )

                points = np.array(
                    eye_points,
                    dtype=np.int32
                )

                # Green eye outline
                cv2.polylines(
                    frame,
                    [points],
                    True,
                    (0, 255, 0),
                    2
                )

                # Small green points
                for x, y in eye_points:

                    cv2.circle(
                        frame,
                        (x, y),
                        2,
                        (0, 255, 0),
                        -1
                    )

            # -----------------------------------------------
            # REJECT BAD LEFT/RIGHT DIFFERENCE
            # -----------------------------------------------

            if abs(left_ear - right_ear) <= 0.10:

                average_ear = (
                    left_ear +
                    right_ear
                ) / 2.0

                # -------------------------------------------
                # CLASSIFY CURRENT FRAME
                # -------------------------------------------

                if average_ear < EAR_CLOSED:

                    current_eye_state = "CLOSED"

                elif average_ear > EAR_OPEN:

                    current_eye_state = "OPEN"

                else:

                    current_eye_state = "BORDERLINE"

                # -------------------------------------------
                # HISTORY
                # -------------------------------------------

                eye_history.append(
                    current_eye_state
                )

                if len(eye_history) > HISTORY_SIZE:

                    eye_history.pop(0)

                # -------------------------------------------
                # MAJORITY VOTE
                # -------------------------------------------

                if len(eye_history) >= 10:

                    open_count = eye_history.count(
                        "OPEN"
                    )

                    closed_count = eye_history.count(
                        "CLOSED"
                    )

                    total = len(eye_history)

                    if open_count / total >= OPEN_RATIO:

                        voted_state = "OPEN"

                    elif closed_count / total >= CLOSED_RATIO:

                        voted_state = "CLOSED"

                    else:

                        voted_state = "BORDERLINE"

            else:

                voted_state = "UNKNOWN"

        else:

            # No face
            voted_state = "UNKNOWN"


        # ====================================================
        # STATE MACHINE
        # ====================================================

        now = time.time()

        # ----------------------------------------------------
        # AWAKE
        # ----------------------------------------------------

        if state == AWAKE:

            wake_timer = None
            alarm_sleep_timer = None

            if voted_state == "CLOSED":

                if sleep_timer is None:

                    sleep_timer = now

                elapsed = now - sleep_timer

                if elapsed >= SLEEP_CONFIRM:

                    state = SLEEPING

                    sleep_timer = None

                    print(
                        "SLEEP CONFIRMED"
                    )

            else:

                sleep_timer = None


        # ----------------------------------------------------
        # SLEEPING
        # ----------------------------------------------------

        elif state == SLEEPING:

            sleep_timer = None
            alarm_sleep_timer = None

            if voted_state == "OPEN":

                if wake_timer is None:

                    wake_timer = now

                elapsed = now - wake_timer

                if elapsed >= WAKE_CONFIRM:

                    state = ALARM

                    wake_timer = None

                    start_alarm()

                    print(
                        "PERSON WOKE UP -> ALARM ACTIVE"
                    )

            else:

                wake_timer = None


        # ----------------------------------------------------
        # ALARM
        # ----------------------------------------------------

        elif state == ALARM:

            sleep_timer = None
            wake_timer = None

            # Alarm continues indefinitely
            # until sleep is confirmed again.

            if voted_state == "CLOSED":

                if alarm_sleep_timer is None:

                    alarm_sleep_timer = now

                elapsed = (
                    now -
                    alarm_sleep_timer
                )

                if elapsed >= SLEEP_CONFIRM:

                    stop_alarm()

                    state = SLEEPING

                    alarm_sleep_timer = None

                    print(
                        "PERSON SLEEPING AGAIN -> ALARM STOPPED"
                    )

            else:

                # OPEN / BORDERLINE / UNKNOWN
                # does NOT stop the alarm.
                alarm_sleep_timer = None


        # ====================================================
        # DISPLAY TEXT DIRECTLY ON VIDEO
        # ====================================================

        # Dark translucent area INSIDE the video
        # so text remains readable.
        overlay = frame.copy()

        cv2.rectangle(
            overlay,
            (0, 0),
            (width, 105),
            (0, 0, 0),
            -1
        )

        cv2.addWeighted(
            overlay,
            0.45,
            frame,
            0.55,
            0,
            frame
        )

        # ----------------------------------------------------
        # TITLE
        # ----------------------------------------------------

        cv2.putText(
            frame,
            "DROWSINESS DETECTION",
            (15, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (255, 255, 255),
            2,
            cv2.LINE_AA
        )

        # ----------------------------------------------------
        # STATE
        # ----------------------------------------------------

        state_text = "STATE: " + state

        cv2.putText(
            frame,
            state_text,
            (15, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2,
            cv2.LINE_AA
        )

        # ----------------------------------------------------
        # EAR
        # ----------------------------------------------------

        ear_text = "EAR: {:.3f}".format(
            average_ear
        )

        cv2.putText(
            frame,
            ear_text,
            (15, 88),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.60,
            (255, 255, 255),
            2,
            cv2.LINE_AA
        )

        # ----------------------------------------------------
        # STATUS MESSAGE
        # ----------------------------------------------------

        if state == AWAKE:

            status = "MONITORING"

        elif state == SLEEPING:

            status = "SLEEP CONFIRMED"

        elif state == ALARM:

            status = "WAKE UP!"

        else:

            status = ""

        cv2.putText(
            frame,
            status,
            (width - 180, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2,
            cv2.LINE_AA
        )

        # ----------------------------------------------------
        # SHOW VIDEO
        # ----------------------------------------------------

        # IMPORTANT:
        # We display ONLY the camera frame.
        # No separate black background.
        # No fullscreen stretching.
        # The window itself contains the video.

        cv2.imshow(
            WINDOW_NAME,
            frame
        )

        # ----------------------------------------------------
        # KEYBOARD
        # ----------------------------------------------------

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q") or key == 27:

            break


# ============================================================
# CLEANUP
# ============================================================

finally:

    camera_running = False

    try:
        stop_alarm()
    except:
        pass

    face_mesh.close()

    cv2.destroyAllWindows()

    print("Detection stopped.")