#!/usr/bin/env python3
"""
Kamera-Livestream mit ArUco-Erkennung – wie camera_jakob.py, aber per HTTP MJPEG.
Aufruf: python3 raspi/camera_stream.py
Stream öffnen: http://192.168.0.78:8080
"""

import io
import time
import threading
import cv2
import numpy as np
from http.server import BaseHTTPRequestHandler, HTTPServer
from picamera2 import Picamera2

MARKER_SIZE_MM   = 40.0
CAMERA_RES       = (1280, 720)
CRATE_IDS        = {36, 47, 41}
TAG_NAMES        = {36: 'blau', 47: 'gelb', 41: 'ID41'}
PORT             = 8080

aruco_dict     = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
aruco_detector = cv2.aruco.ArucoDetector(aruco_dict, cv2.aruco.DetectorParameters())

fx = fy = float(CAMERA_RES[0])
cx, cy = CAMERA_RES[0] / 2.0, CAMERA_RES[1] / 2.0
camera_matrix = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], dtype=np.float32)
dist_coeffs   = np.zeros((5, 1), dtype=np.float32)

_frame_lock  = threading.Lock()
_latest_jpeg = b''


def _process_frame(frame_bgr: np.ndarray) -> np.ndarray:
    corners, ids, _ = aruco_detector.detectMarkers(frame_bgr)
    vis = frame_bgr.copy()
    if ids is not None:
        cv2.aruco.drawDetectedMarkers(vis, corners, ids)
        rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
            corners, MARKER_SIZE_MM, camera_matrix, dist_coeffs
        )
        for i, mid in enumerate(ids.flatten()):
            if mid in CRATE_IDS:
                dist = float(np.linalg.norm(tvecs[i]))
                tx   = float(tvecs[i][0][0])
                tz   = float(tvecs[i][0][2])
                import math
                angle = math.degrees(math.atan2(tx, tz))
                cv2.drawFrameAxes(vis, camera_matrix, dist_coeffs,
                                  rvecs[i], tvecs[i], MARKER_SIZE_MM * 0.5)
                corner   = corners[i][0][0]
                label    = f"{TAG_NAMES.get(mid, f'ID{mid}')}  {dist:.0f}mm  {angle:+.1f}°"
                text_pos = (int(corner[0]), max(int(corner[1]) - 10, 20))
                cv2.putText(vis, label, text_pos,
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    return vis


def _capture_loop():
    global _latest_jpeg
    picam2 = Picamera2()
    config = picam2.create_preview_configuration(
        main={"size": CAMERA_RES, "format": "RGB888"}
    )
    picam2.configure(config)
    picam2.start()
    time.sleep(2)
    print("Kamera bereit")
    try:
        while True:
            frame_rgb = picam2.capture_array()
            frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
            vis       = _process_frame(frame_bgr)
            ok, buf   = cv2.imencode('.jpg', vis, [cv2.IMWRITE_JPEG_QUALITY, 75])
            if ok:
                with _frame_lock:
                    _latest_jpeg = buf.tobytes()
    finally:
        picam2.stop()


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # kein HTTP-Log-Spam

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
            self.end_headers()
            try:
                while True:
                    with _frame_lock:
                        jpg = _latest_jpeg
                    if jpg:
                        self.wfile.write(
                            b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpg + b'\r\n'
                        )
                    time.sleep(0.05)
            except (BrokenPipeError, ConnectionResetError):
                pass
        else:
            self.send_response(404)
            self.end_headers()


if __name__ == '__main__':
    t = threading.Thread(target=_capture_loop, daemon=True)
    t.start()

    print(f"Stream läuft auf http://192.168.0.78:{PORT}")
    print("Strg+C zum Beenden")
    try:
        HTTPServer(('0.0.0.0', PORT), _Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nBeendet")
