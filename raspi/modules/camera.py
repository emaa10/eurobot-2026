import cv2
import numpy as np
from picamera2 import Picamera2
import time
import threading
import math
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class CratePosition:
    id: int
    tvec: np.ndarray
    rvec: np.ndarray
    distance: float
    timestamp: float

    def __str__(self):
        return (f"Crate ID {self.id}: "
                f"Position ({self.tvec[0][0]:.1f}, {self.tvec[1][0]:.1f}, {self.tvec[2][0]:.1f}) mm, "
                f"Distanz: {self.distance:.1f} mm")


@dataclass
class TagDetection:
    id: int
    horizontal_angle: float  # Grad, positiv = rechts
    distance: float          # mm


class Camera:
    CRATE_IDS = {36, 47, 41}

    def __init__(self, marker_size_mm: float = 40.0, camera_resolution: Tuple[int, int] = (1280, 720)):
        self.marker_size = marker_size_mm
        self.camera_resolution = camera_resolution
        self.logger = logging.getLogger(__name__)

        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        self.aruco_params = cv2.aruco.DetectorParameters()
        self.aruco_detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.aruco_params)

        self.picam2 = None
        self.camera_matrix = None
        self.dist_coeffs = None

        self.tracked_crates: Dict[int, CratePosition] = {}

        self._latest_tags: List[TagDetection] = []
        self._lock = threading.Lock()

        self.running = False
        self.thread = None

    # --- setup (aus camera.py übernommen) ---

    def setup_camera(self):
        self.picam2 = Picamera2()
        config = self.picam2.create_preview_configuration(
            main={"size": self.camera_resolution, "format": "RGB888"}
        )
        self.picam2.configure(config)
        self.picam2.start()
        time.sleep(2)
        self.logger.info("Kamera initialisiert")

    def load_camera_calibration(self, calib_file: str = "camera_calibration.npz"):
        try:
            calib_data = np.load(calib_file)
            self.camera_matrix = calib_data['camera_matrix']
            self.dist_coeffs = calib_data['dist_coeffs']
            self.logger.info(f"Kalibrierung geladen aus {calib_file}")
        except FileNotFoundError:
            self.logger.warning("Keine Kalibrierung gefunden – verwende Standard-Parameter")
            fx = fy = float(self.camera_resolution[0])
            cx, cy = self.camera_resolution[0] / 2.0, self.camera_resolution[1] / 2.0
            self.camera_matrix = np.array(
                [[fx, 0, cx], [0, fy, cy], [0, 0, 1]], dtype=np.float32
            )
            self.dist_coeffs = np.zeros((5, 1), dtype=np.float32)

    # --- pipeline (aus camera.py übernommen) ---

    def capture_frame(self) -> np.ndarray:
        frame = self.picam2.capture_array()
        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    def undistort_image(self, image: np.ndarray) -> np.ndarray:
        h, w = image.shape[:2]
        new_camera_matrix, _ = cv2.getOptimalNewCameraMatrix(
            self.camera_matrix, self.dist_coeffs, (w, h), 1, (w, h)
        )
        return cv2.undistort(image, self.camera_matrix, self.dist_coeffs, None, new_camera_matrix)

    def detect_aruco_markers(self, image: np.ndarray) -> Tuple[List, List, List]:
        corners, ids, rejected = self.aruco_detector.detectMarkers(image)
        return corners, ids, rejected

    def estimate_pose(self, corners: List, ids: List) -> List[CratePosition]:
        detected_crates = []
        if ids is not None:
            rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
                corners, self.marker_size, self.camera_matrix, self.dist_coeffs
            )
            for i, marker_id in enumerate(ids.flatten()):
                if marker_id in self.CRATE_IDS:
                    distance = np.linalg.norm(tvecs[i])
                    detected_crates.append(CratePosition(
                        id=int(marker_id),
                        tvec=tvecs[i],
                        rvec=rvecs[i],
                        distance=distance,
                        timestamp=time.time(),
                    ))
        return detected_crates

    def update_tracking(self, detected_crates: List[CratePosition]):
        for crate in detected_crates:
            self.tracked_crates[crate.id] = crate

    def process_frame(self) -> List[CratePosition]:
        frame = self.capture_frame()
        undistorted = self.undistort_image(frame)
        corners, ids, _ = self.detect_aruco_markers(undistorted)
        detected_crates = self.estimate_pose(corners, ids)
        self.update_tracking(detected_crates)
        return detected_crates

    def get_crate_info(self, crate_id: int) -> Optional[CratePosition]:
        return self.tracked_crates.get(crate_id)

    # --- modul-interface ---

    def start(self):
        self.setup_camera()
        self.load_camera_calibration()
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        self.logger.info("Camera thread started")

    def _capture_loop(self):
        self.logger.info("Camera capture loop running")
        while self.running:
            try:
                detected_crates = self.process_frame()

                tags: List[TagDetection] = []
                for crate in detected_crates:
                    tx, _ty, tz = crate.tvec[0]
                    horizontal_angle = math.degrees(math.atan2(tx, tz))
                    tags.append(TagDetection(
                        id=crate.id,
                        horizontal_angle=horizontal_angle,
                        distance=crate.distance,
                    ))

                with self._lock:
                    self._latest_tags = tags

            except Exception as e:
                if self.running:
                    self.logger.error(f"Camera error: {e}")

    def getTag(self) -> List[TagDetection]:
        """Gibt alle aktuell sichtbaren Marker zurück mit horizontalem Winkel in Grad."""
        with self._lock:
            return list(self._latest_tags)

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
            self.thread = None
        if self.picam2:
            try:
                self.picam2.stop()
            except Exception as e:
                self.logger.error(f"Error stopping camera: {e}")
            self.picam2 = None
        self.logger.info("Camera stopped")
