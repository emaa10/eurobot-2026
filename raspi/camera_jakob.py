import cv2
import numpy as np
from picamera2 import Picamera2
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

@dataclass
class CratePosition:
    id: int
    tvec: np.ndarray  # Translation vector (x, y, z)
    rvec: np.ndarray  # Rotation vector
    distance: float   # Distanz zur Kamera in mm
    timestamp: float
    
    def __str__(self):
        return (f"Crate ID {self.id}: "
                f"Position ({self.tvec[0][0]:.1f}, {self.tvec[1][0]:.1f}, {self.tvec[2][0]:.1f}) mm, "
                f"Distanz: {self.distance:.1f} mm")

class ArUcoVisionPipeline:
    CRATE_IDS = {36, 47, 41}
    
    def __init__(self, marker_size_mm: float = 40.0, aruco_dict_type: int = cv2.aruco.DICT_4X4_50, camera_resolution: Tuple[int, int] = (1280, 720)):
        self.marker_size = marker_size_mm
        self.camera_resolution = camera_resolution
        
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(aruco_dict_type)
        self.aruco_params = cv2.aruco.DetectorParameters()
        self.aruco_detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.aruco_params)
        
        self.picam2 = None
        self.camera_matrix = None
        self.dist_coeffs = None
        
        self.tracked_crates: Dict[int, CratePosition] = {}
        
    def setup_camera(self):
        self.picam2 = Picamera2()
        config = self.picam2.create_preview_configuration(
            main={"size": self.camera_resolution, "format": "RGB888"}
        )
        self.picam2.configure(config)
        self.picam2.start()
        
        time.sleep(2)
        print("Kamera initialisiert")
    
    def load_camera_calibration(self, calib_file: str = "camera_calibration.npz"):
        try:
            calib_data = np.load(calib_file)
            self.camera_matrix = calib_data['camera_matrix']
            self.dist_coeffs = calib_data['dist_coeffs']
            print(f"Kalibrierung geladen aus {calib_file}")
        except FileNotFoundError:
            print("Keine Kalibrierung gefunden - verwende Standard-Parameter")
            # Standard Kameramatrix für Raspberry Pi Camera V2
            # nein, einfach nein...
            fx = fy = self.camera_resolution[0]
            cx, cy = self.camera_resolution[0] / 2, self.camera_resolution[1] / 2
            self.camera_matrix = np.array([
                [fx, 0, cx],
                [0, fy, cy],
                [0, 0, 1]
            ], dtype=np.float32)
            self.dist_coeffs = np.zeros((5, 1), dtype=np.float32)
    
    def capture_frame(self) -> np.ndarray:
        frame = self.picam2.capture_array()
        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    
    def undistort_image(self, image: np.ndarray) -> np.ndarray:
        h, w = image.shape[:2]
        new_camera_matrix, roi = cv2.getOptimalNewCameraMatrix(
            self.camera_matrix, self.dist_coeffs, (w, h), 1, (w, h)
        )
        undistorted = cv2.undistort(
            image, self.camera_matrix, self.dist_coeffs, 
            None, new_camera_matrix
        )
        return undistorted
    
    def detect_aruco_markers(self, image: np.ndarray) -> Tuple[List, List, List]:
        corners, ids, rejected = self.aruco_detector.detectMarkers(image)
        return corners, ids, rejected
    
    def estimate_pose(self, corners: List, ids: List) -> List[CratePosition]:
        detected_crates = []
        
        if ids is not None:
            rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
                corners, self.marker_size, 
                self.camera_matrix, self.dist_coeffs
            )
            
            for i, marker_id in enumerate(ids.flatten()):
                if marker_id in self.CRATE_IDS:
                    distance = np.linalg.norm(tvecs[i])
                    
                    crate_pos = CratePosition(
                        id=int(marker_id),
                        tvec=tvecs[i],
                        rvec=rvecs[i],
                        distance=distance,
                        timestamp=time.time()
                    )
                    detected_crates.append(crate_pos)
        
        return detected_crates
    
    def update_tracking(self, detected_crates: List[CratePosition]):
        for crate in detected_crates:
            self.tracked_crates[crate.id] = crate
    
    def draw_detections(self, image: np.ndarray, corners: List, ids: List, crate_positions: List[CratePosition]) -> np.ndarray:
        vis_image = image.copy()
        
        if ids is not None:
            cv2.aruco.drawDetectedMarkers(vis_image, corners, ids)
            
            for crate_pos in crate_positions:
                idx = np.where(ids.flatten() == crate_pos.id)[0]
                if len(idx) > 0:
                    cv2.drawFrameAxes(
                        vis_image, self.camera_matrix, self.dist_coeffs,
                        crate_pos.rvec, crate_pos.tvec, self.marker_size * 0.5
                    )
                    
                    corner = corners[idx[0]][0][0]
                    text_pos = (int(corner[0]), int(corner[1]) - 10)
                    text = f"ID {crate_pos.id}: {crate_pos.distance:.0f}mm"
                    cv2.putText(vis_image, text, text_pos, 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        return vis_image
    
    def process_frame(self, visualize: bool = True) -> Tuple[np.ndarray, List[CratePosition]]:
        """
        Verarbeitet einen Frame durch die komplette Pipeline
        
        Returns:
            processed_image: Verarbeitetes Bild (mit Visualisierungen falls aktiviert)
            detected_crates: Liste der erkannten Crates
        """
        frame = self.capture_frame()
        
        undistorted = self.undistort_image(frame)
        
        corners, ids, rejected = self.detect_aruco_markers(undistorted)
        
        detected_crates = self.estimate_pose(corners, ids)
        
        self.update_tracking(detected_crates)
        
        if visualize:
            vis_image = self.draw_detections(undistorted, corners, ids, detected_crates)
        else:
            vis_image = undistorted
        
        return vis_image, detected_crates
    
    def get_crate_info(self, crate_id: int) -> Optional[CratePosition]:
        # geht besser... 
        return self.tracked_crates.get(crate_id)
    
    def cleanup(self):
        if self.picam2:
            self.picam2.stop()
            print("Kamera gestoppt")


def main():
    pipeline = ArUcoVisionPipeline(marker_size_mm=40.0)
    
    pipeline.setup_camera()
    pipeline.load_camera_calibration()
    
    print("\nArUco Vision Pipeline gestartet")
    print(f"Tracking Crates mit IDs: {pipeline.CRATE_IDS}")
    print("Drücke 'q' zum Beenden\n")
    
    try:
        frame_count = 0
        while True:
            vis_image, detected_crates = pipeline.process_frame(visualize=True)
            
            if frame_count % 30 == 0:
                if detected_crates:
                    print(f"\n--- Frame {frame_count} ---")
                    for crate in detected_crates:
                        print(crate)
                else:
                    print(f"Frame {frame_count}: Keine Crates erkannt")
            
            cv2.imshow('ArUco Tracking', vis_image)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            
            frame_count += 1
    
    except KeyboardInterrupt:
        print("\nBeende durch Benutzer...")
    
    finally:
        pipeline.cleanup()
        cv2.destroyAllWindows()
        print("Programm beendet")

if __name__ == "__main__":
    main()
