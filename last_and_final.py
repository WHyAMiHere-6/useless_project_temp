import cv2
import mediapipe as mp
import numpy as np
import math
import requests
import time
import threading
from collections import deque


# ============================================================
# IP ADDRESSES
# ============================================================

ESP32_IP = "192.168.137.103"        # ESP32-CAM
CONTROLLER_IP = "192.168.137.180"   # ESP32 buzzer/motor controller

STREAM_URL = f"http://{ESP32_IP}:81/stream"
ALERT_URL = f"http://{CONTROLLER_IP}/alert"
STOP_URL = f"http://{CONTROLLER_IP}/stop"


# ============================================================
# DETECTION SETTINGS
# ============================================================

EAR_CLOSED = 0.20
EAR_OPEN = 0.235

SLEEP_TIME = 4.0      # continuous closed-eyes needed to confirm SLEEPING
WAKE_TIME = 1.5       # continuous open-eyes needed to confirm AWAKE

HISTORY_SIZE = 30
OPEN_RATIO = 0.70
CLOSED_RATIO = 0.70


# ============================================================
# ALARM SETTINGS
# ============================================================

# Person falls asleep -> buzzer OFF
# Person wakes up -> buzzer ON
# Buzzer stays ON until person is confirmed asleep again.

ALARM_RESEND_INTERVAL = 1.5
STOP_RESEND_INTERVAL = 1.0


# ============================================================
# MEDIAPIPE
# ============================================================

mp_face_mesh = mp.solutions.face_mesh

face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.60,
    min_tracking_confidence=0.60,
)


# ============================================================
# EYE LANDMARKS
# ============================================================

LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]


# ============================================================
# EAR CALCULATION
# ============================================================

def eye_aspect_ratio(landmarks, eye_points, width, height):

    points = [
        (
            int(landmarks[i].x * width),
            int(landmarks[i].y * height)
        )
        for i in eye_points
    ]

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

# alarm_needed:
#
# True  = buzzer SHOULD be ON
# False = buzzer SHOULD be OFF
#
# alarm_started:
#
# Whether Python believes the controller currently has
# the alarm active.


alarm_needed = False
alarm_started = False

last_alarm_signal = 0.0
last_stop_signal = 0.0

_request_in_flight = False
_lock = threading.Lock()

_last_warning_time = 0.0
WARNING_THROTTLE = 5.0


# ============================================================
# WARNING HELPER
# ============================================================

def _warn(message):

    global _last_warning_time

    now = time.time()

    if (
        now - _last_warning_time
        >= WARNING_THROTTLE
    ):

        print(message)

        _last_warning_time = now


# ============================================================
# CLEAR REQUEST LOCK
# ============================================================

def _clear_in_flight():

    global _request_in_flight

    with _lock:

        _request_in_flight = False


# ============================================================
# CLAIM REQUEST
# ============================================================

def _try_claim_request():

    global _request_in_flight

    with _lock:

        if _request_in_flight:

            return False

        _request_in_flight = True

        return True


# ============================================================
# ACTUALLY START ALARM
# ============================================================

def _do_start_alarm():

    global alarm_started

    try:

        requests.get(
            ALERT_URL,
            timeout=1
        )

        # ----------------------------------------------------
        # IMPORTANT RACE-CONDITION FIX
        #
        # It is possible that Python detected SLEEPING while
        # this /alert request was still travelling to ESP32.
        #
        # In that case alarm_needed will already be False.
        # So immediately send /stop after /alert finishes.
        # ----------------------------------------------------

        if alarm_needed:

            if not alarm_started:

                print(
                    "🔔 WOKE UP - ALARM ON"
                )

            alarm_started = True

        else:

            # Person is already sleeping.
            # Force the controller OFF.

            try:

                requests.get(
                    STOP_URL,
                    timeout=1
                )

                alarm_started = False

                print(
                    "😴 SLEEP DETECTED - ALARM FORCED OFF"
                )

            except requests.RequestException:

                _warn(
                    "⚠️ Could not stop alarm after sleep detection"
                )

    except requests.RequestException:

        _warn(
            "⚠️ Could not reach controller to start alarm - will keep retrying"
        )

    finally:

        _clear_in_flight()


# ============================================================
# ACTUALLY STOP ALARM
# ============================================================

def _do_stop_alarm():

    global alarm_started

    try:

        requests.get(
            STOP_URL,
            timeout=1
        )

        if alarm_started:

            print(
                "😴 ASLEEP AGAIN - ALARM OFF"
            )

        alarm_started = False

    except requests.RequestException:

        _warn(
            "⚠️ Could not reach controller to stop alarm - will keep retrying"
        )

    finally:

        _clear_in_flight()


# ============================================================
# START ALARM
# ============================================================

def start_alarm():

    global last_alarm_signal

    last_alarm_signal = time.time()

    if _try_claim_request():

        threading.Thread(
            target=_do_start_alarm,
            daemon=True
        ).start()


# ============================================================
# STOP ALARM
# ============================================================

def stop_alarm():

    global last_stop_signal

    last_stop_signal = time.time()

    if _try_claim_request():

        threading.Thread(
            target=_do_stop_alarm,
            daemon=True
        ).start()


# ============================================================
# MAINTAIN ALARM
# ============================================================

def maintain_alarm(now):

    # ========================================================
    # PERSON SHOULD BE AWAKE
    # ========================================================

    if alarm_needed:

        if (
            not alarm_started
            and now - last_alarm_signal >= 0.2
        ):

            start_alarm()

        elif (
            alarm_started
            and now - last_alarm_signal
            >= ALARM_RESEND_INTERVAL
        ):

            start_alarm()


    # ========================================================
    # PERSON SHOULD BE SLEEPING
    # ========================================================

    else:

        # IMPORTANT:
        #
        # We deliberately DO NOT check alarm_started here.
        #
        # Even if Python thinks the alarm is already OFF,
        # the ESP32 may still have received an old /alert
        # request that was travelling through the network.
        #
        # Therefore /stop is periodically sent while sleeping.
        # ====================================================

        if (
            now - last_stop_signal
            >= STOP_RESEND_INTERVAL
        ):

            stop_alarm()


# ============================================================
# CONNECT TO ESP32-CAM
# ============================================================

print()

print(
    "========================================"
)

print(
    "     WAKE / SLEEP MONITORING SYSTEM"
)

print(
    "========================================"
)

print()

print(
    "ESP32-CAM IP :",
    ESP32_IP
)

print(
    "STREAM       :",
    STREAM_URL
)

print(
    "CONTROLLER   :",
    CONTROLLER_IP
)

print()

print(
    "Connecting to ESP32-CAM..."
)


try:

    response = requests.get(
        STREAM_URL,
        stream=True,
        timeout=(5, 15)
    )

    response.raise_for_status()

    print(
        "✅ ESP32-CAM CONNECTED"
    )

    print()


except requests.exceptions.ConnectionError as e:

    print(
        "\n❌ ESP32-CAM CONNECTION FAILED\n"
    )

    print(
        "Check that:"
    )

    print(
        "1. ESP32-CAM is powered"
    )

    print(
        "2. Laptop is connected to the same Wi-Fi"
    )

    print(
        "3. Camera IP is correct"
    )

    print(
        "\nOpen this in your browser:",
        STREAM_URL,
        "\n"
    )

    print(e)

    face_mesh.close()

    exit()


except requests.exceptions.Timeout:

    print(
        "\n❌ ESP32-CAM CONNECTION TIMEOUT\n"
    )

    print(
        "Try opening:",
        STREAM_URL
    )

    face_mesh.close()

    exit()


except requests.exceptions.RequestException as e:

    print(
        "\n❌ ESP32-CAM ERROR\n"
    )

    print(e)

    face_mesh.close()

    exit()


# ============================================================
# STATE
# ============================================================

bytes_data = b""

eye_history = deque(
    maxlen=HISTORY_SIZE
)

state = "AWAKE"

closed_start = None
open_start = None


# ============================================================
# WINDOW
# ============================================================

WINDOW_NAME = "Wake / Sleep Monitor"

cv2.namedWindow(
    WINDOW_NAME,
    cv2.WINDOW_NORMAL
)

window_initialized = False


# ============================================================
# UI COLORS
# ============================================================

COLOR_AWAKE = (60, 220, 60)
COLOR_SLEEPING = (0, 200, 255)
COLOR_ALARM = (0, 0, 255)
COLOR_TEXT = (225, 225, 225)
COLOR_PANEL = (25, 25, 25)


# ============================================================
# DASHBOARD
# ============================================================

def draw_dashboard(
    frame,
    state_text,
    ear,
    classification,
    timer_label,
    timer_ratio,
    alarm_on
):

    panel_w = 250
    panel_h = 140
    pad = 10

    overlay = frame.copy()

    cv2.rectangle(
        overlay,
        (pad, pad),
        (
            pad + panel_w,
            pad + panel_h
        ),
        COLOR_PANEL,
        -1
    )

    cv2.addWeighted(
        overlay,
        0.55,
        frame,
        0.45,
        0,
        dst=frame
    )

    accent = (
        COLOR_ALARM
        if alarm_on
        else (
            COLOR_SLEEPING
            if state_text == "SLEEPING"
            else COLOR_AWAKE
        )
    )

    # --------------------------------------------------------
    # Accent bar
    # --------------------------------------------------------

    cv2.rectangle(
        frame,
        (pad, pad),
        (
            pad + 4,
            pad + panel_h
        ),
        accent,
        -1
    )

    x = pad + 18

    # --------------------------------------------------------
    # State
    # --------------------------------------------------------

    cv2.putText(
        frame,
        state_text,
        (
            x,
            pad + 30
        ),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.72,
        accent,
        2,
        cv2.LINE_AA
    )

    # --------------------------------------------------------
    # EAR
    # --------------------------------------------------------

    cv2.putText(
        frame,
        f"EAR {ear:.3f}  |  {classification}",
        (
            x,
            pad + 55
        ),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        COLOR_TEXT,
        1,
        cv2.LINE_AA
    )

    # --------------------------------------------------------
    # Timer
    # --------------------------------------------------------

    if timer_label:

        cv2.putText(
            frame,
            timer_label,
            (
                x,
                pad + 80
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.44,
            COLOR_TEXT,
            1,
            cv2.LINE_AA
        )

        bar_x = x
        bar_y = pad + 90

        bar_w = panel_w - 50
        bar_h = 8

        cv2.rectangle(
            frame,
            (
                bar_x,
                bar_y
            ),
            (
                bar_x + bar_w,
                bar_y + bar_h
            ),
            (80, 80, 80),
            1
        )

        fill_w = int(
            bar_w *
            max(
                0.0,
                min(
                    timer_ratio,
                    1.0
                )
            )
        )

        if fill_w > 0:

            cv2.rectangle(
                frame,
                (
                    bar_x,
                    bar_y
                ),
                (
                    bar_x + fill_w,
                    bar_y + bar_h
                ),
                accent,
                -1
            )

    # --------------------------------------------------------
    # Alarm indicator
    # --------------------------------------------------------

    if alarm_on:

        dot_center = (
            pad + panel_w - 18,
            pad + 22
        )

        cv2.circle(
            frame,
            dot_center,
            6,
            COLOR_ALARM,
            -1
        )

        cv2.putText(
            frame,
            "ALARM",
            (
                dot_center[0] - 70,
                dot_center[1] + 5
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            COLOR_ALARM,
            1,
            cv2.LINE_AA
        )


# ============================================================
# NO FACE UI
# ============================================================

def draw_no_face(frame):

    cv2.rectangle(
        frame,
        (10, 10),
        (260, 45),
        COLOR_PANEL,
        -1
    )

    cv2.putText(
        frame,
        "NO FACE DETECTED",
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 0, 255),
        2,
        cv2.LINE_AA
    )


# ============================================================
# MAIN LOOP
# ============================================================

try:

    for chunk in response.iter_content(
        chunk_size=4096
    ):

        if not chunk:

            continue


        # ====================================================
        # BUILD JPEG BUFFER
        # ====================================================

        bytes_data += chunk


        start = bytes_data.find(
            b"\xff\xd8"
        )

        end = bytes_data.find(
            b"\xff\xd9"
        )


        if (
            start == -1
            or end == -1
        ):

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
        # DECODE
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
        # ORIGINAL FRAME SIZE
        # ====================================================

        height, width = frame.shape[:2]


        if (
            width < 100
            or height < 100
        ):

            continue


        # ====================================================
        # WINDOW SIZE
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


        current_time = time.time()


        # ====================================================
        # MAINTAIN BUZZER
        # ====================================================

        maintain_alarm(
            current_time
        )


        # ====================================================
        # PROCESSING COPY
        # ====================================================
        #
        # This enlargement is ONLY for MediaPipe.
        #
        # The actual camera image shown on screen remains
        # at its original aspect ratio and size.
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
        # MEDIAPIPE
        # ====================================================

        results = face_mesh.process(
            rgb
        )


        # ====================================================
        # FACE DETECTED
        # ====================================================

        if results.multi_face_landmarks:

            landmarks = (
                results
                .multi_face_landmarks[0]
                .landmark
            )


            # =================================================
            # LEFT EYE EAR
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
            # RIGHT EYE EAR
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
            # CONVERT POINTS BACK TO CAMERA FRAME
            # =================================================

            left_points = [
                (
                    int(x / PROCESS_SCALE),
                    int(y / PROCESS_SCALE)
                )
                for x, y in left_points_big
            ]


            right_points = [
                (
                    int(x / PROCESS_SCALE),
                    int(y / PROCESS_SCALE)
                )
                for x, y in right_points_big
            ]


            # =================================================
            # CLASSIFICATION
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
            # HISTORY
            # =================================================

            eye_history.append(
                classification
            )


            history_length = len(
                eye_history
            )

            open_count = eye_history.count(
                "OPEN"
            )

            closed_count = eye_history.count(
                "CLOSED"
            )


            open_ratio = (
                open_count /
                history_length
                if history_length
                else 0.0
            )

            closed_ratio = (
                closed_count /
                history_length
                if history_length
                else 0.0
            )


            # =================================================
            # STABLE STATE
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


            # =================================================
            # AWAKE STATE
            # =================================================

            if state == "AWAKE":

                # ---------------------------------------------
                # CLOSED EYES
                # ---------------------------------------------

                if stable_state == "CLOSED":

                    if closed_start is None:

                        closed_start = current_time


                    closed_duration = (
                        current_time -
                        closed_start
                    )


                    # -----------------------------------------
                    # SLEEP CONFIRMED
                    # -----------------------------------------

                    if (
                        closed_duration
                        >= SLEEP_TIME
                    ):

                        state = "SLEEPING"

                        closed_start = None
                        open_start = None

                        eye_history.clear()


                        print(
                            "😴 SLEEPING CONFIRMED"
                        )


                        # =================================================
                        # IMPORTANT BUZZER FIX
                        # =================================================
                        #
                        # Tell the alarm system that the buzzer MUST
                        # be OFF.
                        #
                        # maintain_alarm() will continue sending /stop
                        # until the controller is definitely commanded off.
                        # =================================================

                        alarm_needed = False

                        stop_alarm()


                else:

                    closed_start = None


            # =================================================
            # SLEEPING STATE
            # =================================================

            elif state == "SLEEPING":

                # ---------------------------------------------
                # OPEN EYES
                # ---------------------------------------------

                if stable_state == "OPEN":

                    if open_start is None:

                        open_start = current_time


                    open_duration = (
                        current_time -
                        open_start
                    )


                    # -----------------------------------------
                    # WAKE CONFIRMED
                    # -----------------------------------------

                    if (
                        open_duration
                        >= WAKE_TIME
                    ):

                        state = "AWAKE"

                        open_start = None
                        closed_start = None

                        eye_history.clear()


                        print(
                            "👁️ WAKE CONFIRMED"
                        )


                        # Buzzer should now turn ON
                        # and remain ON.

                        alarm_needed = True

                        start_alarm()


                else:

                    open_start = None


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
            # TIMER
            # =================================================

            timer_label = ""
            timer_ratio = 0.0


            # =================================================
            # FALLING ASLEEP TIMER
            # =================================================

            if (
                state == "AWAKE"
                and closed_start is not None
            ):

                elapsed = min(
                    current_time -
                    closed_start,
                    SLEEP_TIME
                )

                timer_label = (
                    f"Falling asleep check: "
                    f"{elapsed:.1f}/"
                    f"{SLEEP_TIME:.1f}s"
                )

                timer_ratio = (
                    elapsed /
                    SLEEP_TIME
                )


            # =================================================
            # WAKING TIMER
            # =================================================

            elif (
                state == "SLEEPING"
                and open_start is not None
            ):

                elapsed = min(
                    current_time -
                    open_start,
                    WAKE_TIME
                )

                timer_label = (
                    f"Waking up check: "
                    f"{elapsed:.1f}/"
                    f"{WAKE_TIME:.1f}s"
                )

                timer_ratio = (
                    elapsed /
                    WAKE_TIME
                )


            # =================================================
            # DASHBOARD
            # =================================================

            draw_dashboard(
                frame,
                state,
                ear,
                classification,
                timer_label,
                timer_ratio,
                alarm_started
            )


        # ====================================================
        # NO FACE
        # ====================================================

        else:

            # Cancel only the current confirmation timers.
            #
            # DO NOT change alarm_needed.
            #
            # If the person was awake and the camera temporarily
            # loses their face, the alarm must continue.
            #

            closed_start = None
            open_start = None

            draw_no_face(
                frame
            )


        # ====================================================
        # DISPLAY
        # ====================================================

        cv2.imshow(
            WINDOW_NAME,
            frame
        )


        # ====================================================
        # EXIT WITH Q
        # ====================================================

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):

            break


# ============================================================
# CAMERA DISCONNECTED
# ============================================================

except requests.exceptions.ConnectionError:

    print(
        "\n❌ ESP32-CAM STREAM DISCONNECTED"
    )


# ============================================================
# CTRL+C
# ============================================================

except KeyboardInterrupt:

    print(
        "\nProgram stopped."
    )


# ============================================================
# CLEANUP
# ============================================================

finally:

    # ========================================================
    # FORCE ALARM OFF BEFORE EXIT
    # ========================================================

    alarm_needed = False

    print(
        "\nStopping buzzer..."
    )

    try:

        requests.get(
            STOP_URL,
            timeout=1
        )

        print(
            "🔇 Buzzer OFF"
        )

    except requests.RequestException:

        print(
            "⚠️ Could not confirm buzzer was turned off on exit."
        )


    # ========================================================
    # CLOSE CAMERA
    # ========================================================

    response.close()


    # ========================================================
    # CLOSE MEDIAPIPE
    # ========================================================

    face_mesh.close()


    # ========================================================
    # CLOSE OPENCV
    # ========================================================

    cv2.destroyAllWindows()


    print(
        "\nDetection program ended."
    )