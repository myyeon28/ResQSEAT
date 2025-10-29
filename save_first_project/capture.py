# capture.py

import cv2
import requests
import os
import time
import platform
import json

CAM_INDEX = 0
WIDTH, HEIGHT = 640, 480
TEMP_IMAGE_NAME = "_temp_capture.jpg"

def open_camera(index=0):
    system = platform.system().lower()
    if "windows" in system:
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    elif "linux" in system:
        cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
        try:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass
    else:
        cap = cv2.VideoCapture(index)
    return cap

def capture_and_upload(accident_id, server_base_url):
    print(f"[Capture] Initializing camera for photo...")

    cap = open_camera(CAM_INDEX)

    if not cap.isOpened():
        print("[Capture] ERROR: Cannot open camera.")
        return False

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)

    time.sleep(1.0)

    ok, frame = cap.read()
    cap.release()

    if not ok:
        print("[Capture] ERROR: Failed to read frame from camera.")
        return False

    print(f"[Capture] Frame captured successfully.")


    try:
        cv2.imwrite(TEMP_IMAGE_NAME, frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    except Exception as e:
        print(f"[Capture] ERROR: Failed to save temp image: {e}")
        return False

    upload_url = f"{server_base_url}/api/upload_image/{accident_id}"

    try:
        with open(TEMP_IMAGE_NAME, 'rb') as f:
            # Send file with the name 'file' and correct MIME type
            files = {'file': (TEMP_IMAGE_NAME, f, 'image/jpeg')}

            print(f"[Capture] Uploading image to {upload_url}...")
            response = requests.post(upload_url, files=files, timeout=15) # 15s timeout for upload

            if response.status_code == 200:
                print(f"[Capture] SUCCESS: Image uploaded. Response: {response.json()}")
                status = True
            else:
                print(f"[Capture] ERROR: Server returned status {response.status_code}")
                print(f"[Capture] Server response: {response.text}")
                status = False

    except requests.exceptions.RequestException as e:
        print(f"[Capture] ERROR: Upload failed: {e}")
        status = False

    try:
        if os.path.exists(TEMP_IMAGE_NAME):
            os.remove(TEMP_IMAGE_NAME)
    except Exception as e:
        print(f"[Capture] WARN: Failed to remove temp file: {e}")

    return status
