# -*- coding: utf-8 -*-
"""age.py

# age.py

import cv2
import time
import platform
from collections import Counter
import threading

try:
    from facelib import AgeGenderEstimator, FaceDetector
except ImportError as e:
    print(f"Error: 'facelib' library not found. Please install it: pip install facelib. Details: {e}")
    AgeGenderEstimator = None
    FaceDetector = None

WIDTH, HEIGHT = 640, 480
FPS_TARGET = 30
CAM_INDEX = 0
FACELIB_WIDTH = 640
HOLD_SECONDS = 3.0
RECENT_FACE_WINDOW = 1.0
RUN_DURATION = 10.0
WARMUP_SECONDS = 2.0

def open_camera(index=0):
    system = platform.system().lower()
    if "windows" in system:
        return cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if "linux" in system:
        return cv2.VideoCapture(index, cv2.CAP_V4L2)
    return cv2.VideoCapture(index)

def quadrant_index(x, y, mx, my):
    if x < mx and y < my: return 0
    if x >= mx and y < my: return 1
    if x < mx and y >= my: return 2
    return 3

def put_text(img, text, org, scale=0.6, thickness=2, color=(255,255,255)):
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale,
                (0,0,0), thickness+2, cv2.LINE_AA)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale,
                color, thickness, cv2.LINE_AA)

def mode_age(ages):
    if not ages: return None
    c = Counter(ages)
    m = max(c.values())
    cand = [k for k, v in c.items() if v == m]
    return int(round(sorted(cand)[0]))

def categorize_age_code(age_val):
    if age_val is None: return 2
    elif age_val <= 10: return 1
    else: return 0

g_model_load_error = None
fd, ag = None, None

if FaceDetector is not None and AgeGenderEstimator is not None:
    print("[age.py] Loading face detection and age estimation models...")
    try:
        fd = FaceDetector()
        ag = AgeGenderEstimator()
        print("[age.py] Models loaded successfully.")
        g_model_load_error = None
    except Exception as e:
        print(f"[age.py] CRITICAL: Error loading models: {e}")
        g_model_load_error = e
        fd, ag = None, None
else:
    if 'e' in locals():
        g_model_load_error = e
    else:
        g_model_load_error = "facelib library not found or failed to import."
    fd, ag = None, None

def age_result(stop_event: threading.Event = None):
    """
    Runs the age detection process.
    [MODIFIED] Checks stop_event to allow early exit.
    """
    if fd is None or ag is None:
        print("[age.py ERROR] Models are not loaded. Cannot run age detection.")
        if g_model_load_error:
            print(f"[age.py ERROR] Original cause: {g_model_load_error}")
        return (2, 2, 2, 2)

    if stop_event and stop_event.is_set():
        print("[age.py] Stop event received before starting. Exiting.")
        return (2, 2, 2, 2)

    cap = open_camera(CAM_INDEX)
    if not cap.isOpened():
        print("[age.py WARN] Failed to open camera.")
        return (2, 2, 2, 2)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, FPS_TARGET)
    try:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass

    age_buffer = [[], [], [], []]
    locked_age = [None]*4
    face_seen_ts = [0.0]*4
    S1_age, S2_age, S3_age, S4_age = None, None, None, None
    labels = ["S4", "S3", "S2", "S1"]

    script_start_time = time.monotonic()
    detection_start_time = None

    print(f"[{time.strftime('%H:%M:%S')}] Age Check starting: {WARMUP_SECONDS}s stabilization...")

    while True:
        if stop_event and stop_event.is_set():
            print("[age.py] Stop event received during analysis. Exiting loop.")
            break

        ok, frame_bgr = cap.read()
        if not ok:
            print("[age.py WARN] Failed to read frame.")
            break

        frame_bgr = cv2.resize(frame_bgr, (WIDTH, HEIGHT))
        vis = frame_bgr.copy()
        now = time.monotonic()
        mid_x, mid_y = WIDTH//2, HEIGHT//2

        if detection_start_time is None:
            if (now - script_start_time) < WARMUP_SECONDS:
                warmup_text = f"Stabilizing... {now - script_start_time:.1f}s"
                put_text(vis, warmup_text, (10, 30), 0.7, 2, (0, 0, 255))

                cv2.imshow("Age Check", vis)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                continue
            else:
                print(f"[{time.strftime('%H:%M:%S')}] Stabilization complete. Starting {RUN_DURATION}s detection.")
                detection_start_time = now

        elapsed = now - detection_start_time
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        h, w = frame_rgb.shape[:2]
        if w != FACELIB_WIDTH:
            s = FACELIB_WIDTH / float(w)
            fr_rgb = cv2.resize(frame_rgb, (FACELIB_WIDTH, int(h*s)), interpolation=cv2.INTER_LINEAR)
            scale_x = WIDTH / float(fr_rgb.shape[1])
            scale_y = HEIGHT / float(fr_rgb.shape[0])
        else:
            fr_rgb = frame_rgb
            scale_x = 1.0
            scale_y = 1.0

        faces, boxes, scores, landmarks = fd.detect_align(fr_rgb)
        genders, ages = (ag.detect(faces) if len(faces) > 0 else ([], []))

        if boxes is not None:
            for i, box in enumerate(boxes):
                x1, y1, x2, y2 = [int(v) for v in box]
                x1d, y1d = int(x1*scale_x), int(y1*scale_y)
                x2d, y2d = int(x2*scale_x), int(y2*scale_y)
                cv2.rectangle(vis, (x1d, y1d), (x2d, y2d), (0,255,0), 2)
                cx, cy = int((x1d+x2d)/2), int((y1d+y2d)/2)
                q = quadrant_index(cx, cy, mid_x, mid_y)
                face_seen_ts[q] = now
                if locked_age[q] is not None:
                    continue
                if i < len(ages):
                    try:
                        a = int(round(float(ages[i])))
                        if 0 <= a <= 120:
                            age_buffer[q].append((now, a))
                        put_text(vis, str(a), (x1d, max(0, y1d-8)), 0.6, 2, (255,255,255))
                    except: pass

        for q in range(4):
            if locked_age[q] is not None: continue
            age_buffer[q] = [(t,a) for (t,a) in age_buffer[q] if now - t <= (HOLD_SECONDS + 0.5)]
            has_recent_face = (now - face_seen_ts[q] <= RECENT_FACE_WINDOW)
            if has_recent_face:
                if age_buffer[q] and (now - age_buffer[q][0][0] >= (HOLD_SECONDS - 0.1)):
                    final_age = mode_age([a for (_,a) in age_buffer[q]])
                    locked_age[q] = final_age
                    if q == 0:    S4_age = final_age
                    elif q == 1: S3_age = final_age
                    elif q == 2: S2_age = final_age
                    elif q == 3: S1_age = final_age
                    print(f"[{time.strftime('%H:%M:%S')}] Quad {q} ({labels[q]}): lock age = {final_age}")

        cv2.line(vis, (mid_x, 0), (mid_x, HEIGHT), (0, 255, 255), 2)
        cv2.line(vis, (0, mid_y), (WIDTH, mid_y), (0, 255, 255), 2)
        rois = [
            (0, 0, mid_x, mid_y), (mid_x, 0, WIDTH, mid_y),
            (0, mid_y, mid_x, HEIGHT), (mid_x, mid_y, WIDTH, HEIGHT),
        ]
        for i, (x1, y1, x2, y2) in enumerate(rois):
            put_text(vis, labels[i], (x1 + 10, y1 + 25), 0.8, 2, (0,255,255))
            if locked_age[i] is not None:
                put_text(vis, f"LOCK {locked_age[i]}", (x1 + 10, y1 + 50), 0.7, 2, (0,200,255))
        timer_text = f"DETECTING: {elapsed:.1f}s / {RUN_DURATION:.1f}s"
        put_text(vis, timer_text, (10, HEIGHT - 20), 0.7, 2, (0, 255, 0))

        cv2.imshow("Age Check", vis)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            print("[WARN] User manually quit")
            break

        if elapsed >= RUN_DURATION:
            print(f"[{time.strftime('%H:%M:%S')}] {RUN_DURATION}s detection complete.")
            break

        if all(age is not None for age in locked_age):
            print(f"[{time.strftime('%H:%M:%S')}] All 4 quadrants locked. Exiting early.")
            time.sleep(0.5)
            break

    cap.release()
    try:
        cv2.destroyWindow("Age Check")
    except cv2.error:
        pass

    # Finalize Values
    S1_age_code = categorize_age_code(S1_age)
    S2_age_code = categorize_age_code(S2_age)
    S3_age_code = categorize_age_code(S3_age)
    S4_age_code = categorize_age_code(S4_age)

    return (S1_age_code, S2_age_code, S3_age_code, S4_age_code)
