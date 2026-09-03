import cv2
import mediapipe as mp
import numpy as np
import math
import requests
import time

# ============================================================
# ESP32-CAM IP
# ============================================================

ESP32_IP = "172.17.38.47"
STREAM_URL = f"http://{ESP32_IP}/stream"


# ============================================================
# MediaPipe
# ============================================================

mp_face_mesh = mp.solutions.face_mesh

face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)


# ============================================================
# Eye landmark points
# ============================================================

LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]


# ============================================================
# EAR calculation
# ============================================================

def eye_aspect_ratio(landmarks, eye_points, width, height):

    points = []

    for index in eye_points:

        x = int(landmarks[index].x * width)
        y = int(landmarks[index].y * height)

        points.append((x, y))

    vertical1 = math.dist(points[1], points[5])
    vertical2 = math.dist(points[2], points[4])

    horizontal = math.dist(points[0], points[3])

    # Avoid division by zero
    if horizontal == 0:
        return 0.0, points

    ear = (vertical1 + vertical2) / (2.0 * horizontal)

    return ear, points


# ============================================================
# Connect to ESP32-CAM
# ============================================================

print("======================================")
print(" ESP32-CAM EYE DETECTION")
print("======================================")
print()

print("ESP32-CAM IP:", ESP32_IP)
print("Stream URL:", STREAM_URL)
print()
print("Connecting to ESP32-CAM...")

response = None

try:

    response = requests.get(
        STREAM_URL,
        stream=True,
        timeout=(5, 15)
    )

    response.raise_for_status()

    print("✅ Connected to ESP32-CAM")
    print("Status code:", response.status_code)
    print()

except requests.exceptions.ConnectionError as e:

    print()
    print("❌ CONNECTION ERROR")
    print()
    print("Python could not maintain the connection to the ESP32-CAM.")
    print()
    print("Check:")
    print("1. ESP32-CAM is powered")
    print("2. Laptop and ESP32-CAM are on the same Wi-Fi")
    print("3. ESP32-CAM IP address is correct")
    print("4. /stream works in your browser")
    print()
    print("Try opening:")
    print(STREAM_URL)
    print()
    print("Error:")
    print(e)

    face_mesh.close()
    exit()

except requests.exceptions.Timeout:

    print()
    print("❌ CONNECTION TIMEOUT")
    print()
    print("The ESP32-CAM did not respond in time.")
    print()
    print("Try opening this in your browser:")
    print(STREAM_URL)

    face_mesh.close()
    exit()

except requests.exceptions.RequestException as e:

    print()
    print("❌ ESP32-CAM REQUEST ERROR")
    print()
    print(e)

    face_mesh.close()
    exit()


# ============================================================
# Read MJPEG stream
# ============================================================

bytes_data = b""


try:

    for chunk in response.iter_content(chunk_size=1024):

        if not chunk:
            continue

        bytes_data += chunk

        start = bytes_data.find(b'\xff\xd8')
        end = bytes_data.find(b'\xff\xd9')

        if start != -1 and end != -1 and end > start:

            jpg = bytes_data[start:end + 2]

            bytes_data = bytes_data[end + 2:]

            frame = cv2.imdecode(
                np.frombuffer(
                    jpg,
                    dtype=np.uint8
                ),
                cv2.IMREAD_COLOR
            )

            if frame is None:
                continue

            height, width = frame.shape[:2]


            # =================================================
            # Convert BGR → RGB
            # =================================================

            rgb = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2RGB
            )


            # =================================================
            # Detect face
            # =================================================

            results = face_mesh.process(rgb)


            if results.multi_face_landmarks:

                landmarks = results.multi_face_landmarks[0].landmark


                # =============================================
                # Calculate left EAR
                # =============================================

                left_ear, left_points = eye_aspect_ratio(
                    landmarks,
                    LEFT_EYE,
                    width,
                    height
                )


                # =============================================
                # Calculate right EAR
                # =============================================

                right_ear, right_points = eye_aspect_ratio(
                    landmarks,
                    RIGHT_EYE,
                    width,
                    height
                )


                # =============================================
                # Average EAR
                # =============================================

                ear = (
                    left_ear +
                    right_ear
                ) / 2.0


                # =============================================
                # Threshold
                # =============================================

                if ear < 0.21:

                    status = "EYE CLOSED"

                else:

                    status = "EYE OPEN"


                # =============================================
                # Draw eyes
                # =============================================

                for point in left_points + right_points:

                    cv2.circle(
                        frame,
                        point,
                        2,
                        (0, 255, 0),
                        -1
                    )


                # =============================================
                # Status text
                # =============================================

                cv2.putText(
                    frame,
                    status,
                    (30, 50),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    2
                )


                # =============================================
                # EAR text
                # =============================================

                cv2.putText(
                    frame,
                    f"EAR: {ear:.2f}",
                    (30, 90),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),
                    2
                )


            else:

                cv2.putText(
                    frame,
                    "NO FACE DETECTED",
                    (30, 50),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 0, 255),
                    2
                )


            # =================================================
            # DISPLAY
            # =================================================

            cv2.imshow(
                "ESP32-CAM Eye Detection",
                frame
            )


            # =================================================
            # Press Q to quit
            # =================================================

            if cv2.waitKey(1) & 0xFF == ord("q"):

                break


except requests.exceptions.ConnectionError as e:

    print()
    print("❌ ESP32-CAM DISCONNECTED")
    print()
    print("The camera closed the stream connection.")
    print("Check the ESP32-CAM power, Wi-Fi, and /stream endpoint.")
    print()
    print("Error:")
    print(e)


except KeyboardInterrupt:

    print()
    print("Program stopped.")


finally:

    if response is not None:

        response.close()

    face_mesh.close()

    cv2.destroyAllWindows()

    print()
    print("Program ended.")