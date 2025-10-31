
import os
import time
from datetime import datetime
from pathlib import Path
import cv2

# =========================
# CONFIG — tweak to taste
# =========================
# Map hotkeys to gesture labels (press these keys while the window is focused)
LABEL_KEYS = {
    "1": "travel",
    "2": "double_dribble",
    "3": "blocking",
    "4": "carrying",
    "5": "technical_foul",          # add/remove as you like
    "6": "24_second_violation",
    "9": "idle",            # record "no call"/standing still
}

CLIP_SECONDS = 4           # length of each saved clip
COUNTDOWN = 2.0            # small lead-in before recording starts (seconds)
OUTPUT_ROOT = Path("data/raw")  # clips saved under data/raw/<label>/
CAM_INDEX = 1              # try 1 or 2 if you have multiple cameras
TARGET_FPS = 30            # used when camera FPS is unknown
FRAME_SIZE = None          # None = use camera default; or set like (1280, 720)

# =========================
# Utilities
# =========================
def ensure_dirs():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    for label in LABEL_KEYS.values():
        (OUTPUT_ROOT / label).mkdir(parents=True, exist_ok=True)

def put_text(img, text, org, scale=0.7, color=(255,255,255), thickness=2):
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)

def draw_hud(frame, status, last_saved):
    h, w = frame.shape[:2]
    # translucent banner
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 90), (0, 0, 0), -1)
    frame = cv2.addWeighted(overlay, 0.35, frame, 0.65, 0)

    put_text(frame, "Ref Signals Clipper — keys: " + ", ".join([f"{k}:{v}" for k,v in LABEL_KEYS.items()]),
             (10, 25), scale=0.6)
    put_text(frame, "Press number key to record; 'q' to quit",
             (10, 50), scale=0.6)
    if status:
        put_text(frame, status, (10, 80), scale=0.7, color=(0,255,0), thickness=2)
    if last_saved:
        put_text(frame, f"Saved: {last_saved}", (10, h-10), scale=0.5, color=(200,255,200), thickness=1)
    return frame

def timestamped_name(label):
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{label}_{ts}.mp4"

def open_writer(path, fps, frame_size):
    # MP4V works on most platforms; if not, try 'avc1' or fallback to .avi with 'XVID'
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    return cv2.VideoWriter(str(path), fourcc, fps, frame_size)

# =========================
# Main
# =========================
def main():
    ensure_dirs()

    cap = cv2.VideoCapture(CAM_INDEX)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera index {CAM_INDEX}")

    # Try to set frame size if requested
    if FRAME_SIZE:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_SIZE[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_SIZE[1])

    # Read actual camera params (some webcams don’t report FPS)
    cam_fps = cap.get(cv2.CAP_PROP_FPS)
    if not cam_fps or cam_fps <= 1:
        cam_fps = TARGET_FPS
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_size = (width, height)

    last_saved = ""
    status = ""

    print("=== Controls ===")
    for k, v in LABEL_KEYS.items():
        print(f"[{k}] → {v}")
    print("[q]   → quit")
    print("================")

    # Pre-create a named window so it stays focused
    cv2.namedWindow("RefSignals", cv2.WINDOW_NORMAL)

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        frame_disp = draw_hud(frame.copy(), status, last_saved)
        cv2.imshow("RefSignals", frame_disp)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break

        # If pressed a mapping key, record a clip
        if key != 255:  # any key pressed
            kchr = chr(key)
            if kchr in LABEL_KEYS:
                label = LABEL_KEYS[kchr]
                status = f"Get ready: recording '{label}' in {COUNTDOWN:.1f}s for {CLIP_SECONDS}s…"
                # Show countdown
                t_end = time.time() + COUNTDOWN
                while time.time() < t_end:
                    ret, frame = cap.read()
                    if not ret:
                        continue
                    countdown_left = max(0, t_end - time.time())
                    frame_cc = frame.copy()
                    put_text(frame_cc, f"{label.upper()} — starting in {countdown_left:.1f}s",
                             (10, 80), scale=0.9, color=(0,255,255), thickness=2)
                    cv2.imshow("RefSignals", frame_cc)
                    cv2.waitKey(1)

                # Start recording
                clip_name = timestamped_name(label)
                out_path = OUTPUT_ROOT / label / clip_name
                writer = open_writer(out_path, cam_fps, frame_size)

                frames_to_write = int(cam_fps * CLIP_SECONDS)
                written = 0
                t_record_end = time.time() + CLIP_SECONDS + 0.05

                while time.time() < t_record_end and (written < frames_to_write or cam_fps == 0):
                    ret, frame = cap.read()
                    if not ret:
                        continue
                    # Big on-screen REC indicator
                    rec = frame.copy()
                    cv2.rectangle(rec, (10, 10), (130, 50), (0, 0, 255), -1)
                    put_text(rec, "REC", (20, 40), scale=0.9, color=(255,255,255), thickness=2)
                    put_text(rec, f"{label}", (150, 40), scale=0.9, color=(0,255,0), thickness=2)
                    writer.write(rec)
                    written += 1
                    cv2.imshow("RefSignals", rec)
                    cv2.waitKey(1)

                writer.release()
                last_saved = f"{label}/{clip_name}"
                status = f"Saved {last_saved}  ({written} frames)"
            else:
                status = f"Unknown key: '{kchr}' — use {', '.join(LABEL_KEYS.keys())}"

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
