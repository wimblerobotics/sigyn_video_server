import cv2
from flask import Flask, Response, render_template_string, request
import threading
import time
import os
from datetime import datetime

app = Flask(__name__)
SAVE_DIR = os.path.expanduser('~/training_images')
os.makedirs(SAVE_DIR, exist_ok=True)

# Shared frame buffer
frame_lock = threading.Lock()
current_frame = None

def camera_thread():
    global current_frame
    gst_str = (
        "libcamerasrc ! video/x-raw,format=RGB,width=640,height=480,framerate=10/1 ! "
        "videoconvert ! appsink"
    )
    cap = cv2.VideoCapture(gst_str, cv2.CAP_GSTREAMER)
    if not cap.isOpened():
        print("Failed to open camera with GStreamer pipeline.")
        return
    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.1)
            continue
        with frame_lock:
            current_frame = cv2.flip(frame, -1)
        time.sleep(0.10)  # ~10 fps
    cap.release()

@app.route('/')
def index():
    return render_template_string('''
        <h1>Pi Camera Stream</h1>
        <img src="/video_feed">
        <form action="/save_image" method="post">
            <button type="submit">Save Image</button>
        </form>
        {% if message %}
        <p>{{ message }}</p>
        {% endif %}
    ''')

def gen():
    global current_frame
    while True:
        with frame_lock:
            if current_frame is None:
                time.sleep(0.05)  # Sleep briefly to avoid busy waiting
                continue
            ret, jpeg = cv2.imencode('.jpg', current_frame)
            if not ret:
                time.sleep(0.05)
                continue
            frame = jpeg.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.1)  # Match your camera thread's 10 fps

@app.route('/video_feed')
def video_feed():
    return Response(gen(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/save_image', methods=['POST'])
def save_image():
    global current_frame
    with frame_lock:
        if current_frame is not None:
            filename = datetime.now().strftime("%Y%m%d_%H%M%S") + ".jpg"
            filepath = os.path.join(SAVE_DIR, filename)
            cv2.imwrite(filepath, current_frame)
            message = f"Image saved as {filename}"
        else:
            message = "No frame to save."
    return render_template_string('''
        <h1>Pi Camera Stream</h1>
        <img src="/video_feed">
        <form action="/save_image" method="post">
            <button type="submit">Save Image</button>
        </form>
        <p>{{ message }}</p>
    ''', message=message)

if __name__ == '__main__':
    t = threading.Thread(target=camera_thread, daemon=True)
    t.start()
    app.run(host='0.0.0.0', port=5000, threaded=True)