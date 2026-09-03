import cv2
import mediapipe as mp
import numpy as np
import math
import requests
import time
from collections import deque


# ============================================================
# IP ADDRESSES
# ============================================================

# ESP32-CAM
ESP32_IP = "192.168.137.54"

# Normal ESP32 controller
CONTROLLER_IP = "192.168.137.90"

# ESP32-CAM stream is on PORT 81
STREAM_URL = f"http://{ESP32_IP}:81/stream"

# Normal ESP32 control endpoints
ALERT_URL = f"http://{CONTROLLER_IP}/alert"
STOP_URL = f"http://{CONTROLLER_IP}/stop"


# ============================================================
# DETECTION SETTINGS
# ============================================================

# Eye Aspect Ratio thresholds
EAR_CLOSED = 0.20
EAR_OPEN = 0.235

# Continuous confirmation times
SLEEP_TIME = 4.0
WAKE_TIME = 1.5

# Number of recent eye classifications
HISTORY_SIZE = 30

# Percentage required for stable state
OPEN_RATIO = 0.70
CLOSED_RATIO = 0.70


# ============================================================
# MEDIAPIPE
# ============================================================

mp_face_mesh = mp.solutions.face_mesh

face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.60,
    min_tracking_confidence=0.60
)


# ============================================================
# EYE LANDMARKS
# ============================================================

LEFT_EYE = [
    33,
    160,
    158,
    133,
    153,
    144
]

RIGHT_EYE = [
    362,
    385,
    387,
    263,
    373,
    380
]


# ============================================================
# EAR CALCULATION
# ============================================================

def eye_aspect_ratio(landmarks, eye_points, width, height):

    points = []

    for index in eye_points:

        x = int(landmarks[index].x * width)
        y = int(landmarks[index].y * height)

        points.append((x, y))

    vertical1 = math.dist(
        points[1],
        points[5]
    )

    vertical2 = math.dist(
        points[2],
        points[4]
    )

    horizontal = math.dist(
        points[0],
        points[3]
    )

    if horizontal <= 0:

        return 0.0, points

    ear = (
        vertical1 +
        vertical2
    ) / (
        2.0 *
        horizontal
    )

    return ear, points


# ============================================================
# ALARM CONTROL
# ============================================================

alarm_started = False


def start_alarm():

    global alarm_started

    if alarm_started:
        return

    try:

        requests.get(
            ALERT_URL,
            timeout=1
        )

        alarm_started = True

        print("🔔 WAKE CONFIRMED - ALARM ON")

    except requests.RequestException as e:

        print("⚠️ Could not start alarm")
        print(e)


def stop_alarm():

    global alarm_started

    if not alarm_started:
        return

    try:

        requests.get(
            STOP_URL,
            timeout=1
        )

        alarm_started = False

        print("😴 SLEEP CONFIRMED - ALARM OFF")

    except requests.RequestException as e:

        print("⚠️ Could not stop alarm")
        print(e)


# ============================================================
# CONNECT TO ESP32-CAM
# ============================================================

print()
print("========================================")
print("       DROWSINESS DETECTION SYSTEM")
print("========================================")
print()

print("ESP32-CAM IP :", ESP32_IP)
print("STREAM       :", STREAM_URL)
print("CONTROLLER   :", CONTROLLER_IP)
print()

print("Connecting to ESP32-CAM...")


try:

    response = requests.get(
        STREAM_URL,
        stream=True,
        timeout=(5, 15)
    )

    response.raise_for_status()

    print("✅ ESP32-CAM CONNECTED")
    print()


except requests.exceptions.ConnectionError as e:

    print()
    print("❌ ESP32-CAM CONNECTION FAILED")
    print()
    print("Check that:")
    print("1. ESP32-CAM is powered")
    print("2. Laptop is connected to the same Wi-Fi")
    print("3. Camera IP is correct")
    print()
    print("Open this in your browser:")
    print(STREAM_URL)
    print()
    print(e)

    face_mesh.close()
    exit()


except requests.exceptions.Timeout:

    print()
    print("❌ ESP32-CAM CONNECTION TIMEOUT")
    print()
    print("Try opening:")
    print(STREAM_URL)

    face_mesh.close()
    exit()


except requests.exceptions.RequestException as e:

    print()
    print("❌ ESP32-CAM ERROR")
    print()
    print(e)

    face_mesh.close()
    exit()


# ============================================================
# FRAME BUFFER
# ============================================================

bytes_data = b""


# ============================================================
# TEMPORAL EYE HISTORY
# ============================================================

eye_history = deque(
    maxlen=HISTORY_SIZE
)


# ============================================================
# SYSTEM STATE
# ============================================================

# Initial condition
state = "AWAKE"

# Timers
closed_start = None
open_start = None


# ============================================================
# WINDOW
# ============================================================

WINDOW_NAME = "ESP32-CAM Eye Detection"

cv2.namedWindow(
    WINDOW_NAME,
    cv2.WINDOW_NORMAL
)

window_initialized = False


# ============================================================
# MAIN LOOP
# ============================================================

try:

    for chunk in response.iter_content(
        chunk_size=4096
    ):

        if not chunk:
            continue

        bytes_data += chunk


        # ====================================================
        # FIND JPEG START
        # ====================================================

        start = bytes_data.find(
            b"\xff\xd8"
        )


        # ====================================================
        # FIND JPEG END
        # ====================================================

        end = bytes_data.find(
            b"\xff\xd9"
        )


        if start == -1 or end == -1:

            # Prevent corrupted/large buffer
            if len(bytes_data) > 2_000_000:

                bytes_data = b""

            continue


        if end <= start:

            continue


        # ====================================================
        # EXTRACT JPEG
        # ====================================================

        jpg = bytes_data[
            start:end + 2
        ]

        bytes_data = bytes_data[
            end + 2:
        ]


        # ====================================================
        # DECODE IMAGE
        # ====================================================

        frame = cv2.imdecode(
            np.frombuffer(
                jpg,
                dtype=np.uint8
            ),
            cv2.IMREAD_COLOR
        )


        if frame is None:

            continue


        # ====================================================
        # ORIGINAL CAMERA SIZE
        # ====================================================

        height, width = frame.shape[:2]


        if width < 100 or height < 100:

            continue


        # ====================================================
        # SET WINDOW SIZE ONCE
        # ====================================================

        if not window_initialized:

            display_width = min(
                width,
                960
            )

            display_height = int(
                display_width *
                height /
                width
            )

            cv2.resizeWindow(
                WINDOW_NAME,
                display_width,
                display_height
            )

            window_initialized = True


        # ====================================================
        # PROCESSING COPY
        # ====================================================
        #
        # The displayed frame is NOT enlarged.
        #
        # MediaPipe gets a larger copy to improve detection
        # on the relatively small ESP32-CAM image.
        # ====================================================

        PROCESS_SCALE = 1.5

        process_frame = cv2.resize(
            frame,
            None,
            fx=PROCESS_SCALE,
            fy=PROCESS_SCALE,
            interpolation=cv2.INTER_CUBIC
        )


        process_height, process_width = (
            process_frame.shape[:2]
        )


        # ====================================================
        # BGR → RGB
        # ====================================================

        rgb = cv2.cvtColor(
            process_frame,
            cv2.COLOR_BGR2RGB
        )


        # ====================================================
        # FACE DETECTION
        # ====================================================

        results = face_mesh.process(
            rgb
        )


        # ====================================================
        # FACE FOUND
        # ====================================================

        if results.multi_face_landmarks:

            landmarks = (
                results
                .multi_face_landmarks[0]
                .landmark
            )


            # =================================================
            # LEFT EAR
            # =================================================

            left_ear, left_points_big = (
                eye_aspect_ratio(
                    landmarks,
                    LEFT_EYE,
                    process_width,
                    process_height
                )
            )


            # =================================================
            # RIGHT EAR
            # =================================================

            right_ear, right_points_big = (
                eye_aspect_ratio(
                    landmarks,
                    RIGHT_EYE,
                    process_width,
                    process_height
                )
            )


            # =================================================
            # AVERAGE EAR
            # =================================================

            ear = (
                left_ear +
                right_ear
            ) / 2.0


            # =================================================
            # EYE DIFFERENCE
            # =================================================

            eye_difference = abs(
                left_ear -
                right_ear
            )


            # =================================================
            # CONVERT POINTS BACK TO DISPLAY FRAME
            # =================================================

            left_points = []

            for x, y in left_points_big:

                left_points.append(
                    (
                        int(x / PROCESS_SCALE),
                        int(y / PROCESS_SCALE)
                    )
                )


            right_points = []

            for x, y in right_points_big:

                right_points.append(
                    (
                        int(x / PROCESS_SCALE),
                        int(y / PROCESS_SCALE)
                    )
                )


            # =================================================
            # CLASSIFY EYES
            # =================================================

            if eye_difference > 0.10:

                classification = "BORDERLINE"

            elif ear < EAR_CLOSED:

                classification = "CLOSED"

            elif ear >= EAR_OPEN:

                classification = "OPEN"

            else:

                classification = "BORDERLINE"


            # =================================================
            # ADD TO HISTORY
            # =================================================

            eye_history.append(
                classification
            )


            # =================================================
            # TEMPORAL VOTING
            # =================================================

            history_length = len(
                eye_history
            )

            open_count = eye_history.count(
                "OPEN"
            )

            closed_count = eye_history.count(
                "CLOSED"
            )


            if history_length > 0:

                open_ratio = (
                    open_count /
                    history_length
                )

                closed_ratio = (
                    closed_count /
                    history_length
                )

            else:

                open_ratio = 0.0
                closed_ratio = 0.0


            # =================================================
            # STABLE EYE STATE
            # =================================================

            if (
                history_length >= 10
                and closed_ratio >= CLOSED_RATIO
            ):

                stable_state = "CLOSED"

            elif (
                history_length >= 10
                and open_ratio >= OPEN_RATIO
            ):

                stable_state = "OPEN"

            else:

                stable_state = "BORDERLINE"


            current_time = time.time()


            # =================================================
            # AWAKE STATE
            # =================================================

            if state == "AWAKE":

                # ---------------------------------------------
                # Start closed-eye timer
                # ---------------------------------------------

                if stable_state == "CLOSED":

                    if closed_start is None:

                        closed_start = current_time


                    closed_duration = (
                        current_time -
                        closed_start
                    )


                    # -----------------------------------------
                    # 4 SECONDS CLOSED
                    # -----------------------------------------

                    if closed_duration >= SLEEP_TIME:

                        state = "SLEEPING"

                        closed_start = None
                        open_start = None

                        eye_history.clear()

                        print(
                            "😴 SLEEPING CONFIRMED"
                        )

                        stop_alarm()


                else:

                    # Eyes opened/borderline
                    # Reset continuous timer

                    closed_start = None


            # =================================================
            # SLEEPING STATE
            # =================================================

            elif state == "SLEEPING":

                # ---------------------------------------------
                # Start open-eye timer
                # ---------------------------------------------

                if stable_state == "OPEN":

                    if open_start is None:

                        open_start = current_time


                    open_duration = (
                        current_time -
                        open_start
                    )


                    # -----------------------------------------
                    # 1.5 SECONDS OPEN
                    # -----------------------------------------

                    if open_duration >= WAKE_TIME:

                        state = "AWAKE"

                        open_start = None
                        closed_start = None

                        eye_history.clear()

                        print(
                            "👁️ WAKE CONFIRMED"
                        )

                        start_alarm()


                else:

                    # Eyes closed/borderline
                    # Cancel wake timer

                    open_start = None


            # =================================================
            # DISPLAY STATE
            # =================================================

            if state == "SLEEPING":

                state_text = "SLEEPING"

            else:

                state_text = "AWAKE"


            # =================================================
            # DRAW EYE POINTS
            # =================================================

            for point in (
                left_points +
                right_points
            ):

                cv2.circle(
                    frame,
                    point,
                    2,
                    (0, 255, 0),
                    -1
                )


            # =================================================
            # CLEAN UI
            # =================================================

            # -----------------------------------------------
            # STATE
            # -----------------------------------------------

            cv2.putText(
                frame,
                f"STATE: {state_text}",
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.70,
                (0, 255, 0),
                2,
                cv2.LINE_AA
            )


            # -----------------------------------------------
            # EAR
            # -----------------------------------------------

            cv2.putText(
                frame,
                f"EAR: {ear:.3f}",
                (20, 65),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                2,
                cv2.LINE_AA
            )


            # -----------------------------------------------
            # EYE STATUS
            # -----------------------------------------------

            cv2.putText(
                frame,
                f"EYES: {classification}",
                (20, 92),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.50,
                (255, 255, 255),
                2,
                cv2.LINE_AA
            )


            # =================================================
            # TIMER TEXT
            # =================================================

            timer_text = ""


            # -----------------------------------------------
            # SLEEP TIMER
            # -----------------------------------------------

            if state == "AWAKE":

                if closed_start is not None:

                    elapsed = (
                        current_time -
                        closed_start
                    )

                    elapsed = min(
                        elapsed,
                        SLEEP_TIME
                    )

                    timer_text = (
                        f"SLEEP CHECK: "
                        f"{elapsed:.1f}/"
                        f"{SLEEP_TIME:.1f}s"
                    )


            # -----------------------------------------------
            # WAKE TIMER
            # -----------------------------------------------

            elif state == "SLEEPING":

                if open_start is not None:

                    elapsed = (
                        current_time -
                        open_start
                    )

                    elapsed = min(
                        elapsed,
                        WAKE_TIME
                    )

                    timer_text = (
                        f"WAKE CHECK: "
                        f"{elapsed:.1f}/"
                        f"{WAKE_TIME:.1f}s"
                    )


            if timer_text:

                cv2.putText(
                    frame,
                    timer_text,
                    (20, 120),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.48,
                    (255, 255, 255),
                    2,
                    cv2.LINE_AA
                )


            # =================================================
            # ALARM STATUS
            # =================================================

            if alarm_started:

                cv2.putText(
                    frame,
                    "ALARM: ON",
                    (20, 150),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.52,
                    (0, 0, 255),
                    2,
                    cv2.LINE_AA
                )


        # ====================================================
        # NO FACE
        # ====================================================

        else:

            # Reset confirmation timers
            closed_start = None
            open_start = None

            cv2.putText(
                frame,
                "NO FACE DETECTED",
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.70,
                (0, 0, 255),
                2,
                cv2.LINE_AA
            )


        # ====================================================
        # SHOW CAMERA
        # ====================================================

        cv2.imshow(
            WINDOW_NAME,
            frame
        )


        # ====================================================
        # Q TO EXIT
        # ====================================================

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):

            break


# ============================================================
# ERROR HANDLING
# ============================================================

except requests.exceptions.ConnectionError:

    print()
    print("❌ ESP32-CAM STREAM DISCONNECTED")


except KeyboardInterrupt:

    print()
    print("Program stopped.")


# ============================================================
# CLEANUP
# ============================================================

finally:

    if alarm_started:

        stop_alarm()

    response.close()

    face_mesh.close()

    cv2.destroyAllWindows()

    print()
    print("Detection program ended.")