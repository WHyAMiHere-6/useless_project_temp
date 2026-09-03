import cv2
import requests
import numpy as np
import mediapipe as mp
import math
import time

ESP32_IP = "172.17.38.47"
STREAM_URL = f"http://{ESP32_IP}/stream"

# Eye landmarks
LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]

# Thresholds
EAR_THRESHOLD = 0.21
CLOSED_TIME = 2.0

def calculate_ear(landmarks, eye_indices, width, height):
    points = []

    for index in eye_indices:
        x = int(landmarks[index].x * width)
        y = int(landmarks[index].y * height)
        points.append((x, y))

    vertical1 = math.dist(points[1], points[5])
    vertical2 = math.dist(points[2], points[4])
    horizontal = math.dist(points[0], points[3])

    ear = (vertical1 + vertical2) / (2.0 * horizontal)

    return ear


# MediaPipe
mp_face_mesh = mp.solutions.face_mesh

face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

print("Connecting to ESP32-CAM...")

response = requests.get(
    STREAM_URL,
    stream=True,
    timeout=10
)

print("✅ Connected to ESP32-CAM")

bytes_data = b""

eyes_closed_start = None

for chunk in response.iter_content(chunk_size=1024):

    bytes_data += chunk

    start = bytes_data.find(b'\xff\xd8')
    end = bytes_data.find(b'\xff\xd9')

    if start != -1 and end != -1 and end > start:

        jpg = bytes_data[start:end + 2]
        bytes_data = bytes_data[end + 2:]

        frame = cv2.imdecode(
            np.frombuffer(jpg, dtype=np.uint8),
            cv2.IMREAD_COLOR
        )

        if frame is None:
            continue

        height, width = frame.shape[:2]

        # Convert BGR → RGB
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        results = face_mesh.process(rgb)

        status = "NO FACE"

        if results.multi_face_landmarks:

            landmarks = results.multi_face_landmarks[0].landmark

            left_ear = calculate_ear(
                landmarks, LEFT_EYE, width, height
            )

            right_ear = calculate_ear(
                landmarks, RIGHT_EYE, width, height
            )

            # Average of both eyes
            ear = (left_ear + right_ear) / 2.0

            # Check eye state
            if ear < EAR_THRESHOLD:

                if eyes_closed_start is None:
                    eyes_closed_start = time.time()

                closed_duration = time.time() - eyes_closed_start

                if closed_duration >= CLOSED_TIME:
                    status = "DROWSINESS DETECTED!"
                else:
                    status = "EYES CLOSED"

            else:

                eyes_closed_start = None
                status = "EYES OPEN"

            # Display EAR
            cv2.putText(
                frame,
                f"EAR: {ear:.2f}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2
            )

        # Display status
        cv2.putText(
            frame,
            status,
            (20, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 255, 0),
            2
        )

        cv2.imshow("ESP32-CAM Drowsiness Detection", frame)

        # Press Q to quit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break


response.close()
face_mesh.close()
cv2.destroyAllWindows()