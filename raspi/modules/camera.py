import time
import cv2
import numpy as np
from picamera2 import Picamera2
import cv2.aruco as aruco
import libcamera
import threading
import math
import os
import logging


class Camera:
    CALIB_FACTOR = 0.57
    TAG_SIZE = 0.0235  # size of the ArUco marker in meters
    IMAGE_WIDTH = 1280
    IMAGE_HEIGHT = 960
    MAX_ANGLE = 32
    GROUP_DISTANCE = 0.04

    def __init__(self,
                 matrix_path: str = "camera/camera_matrix.npy",
                 dist_path: str = "camera/dist_coeffs.npy",
                 rotate: int = 270):
        # Load camera calibration data
        cv2.setUseOptimized(False)
        cv2.ocl.setUseOpenCL(False)
        self.camera_matrix = np.load(matrix_path)
        self.dist_coeffs = np.load(dist_path)

        logging.basicConfig(filename='/home/eurobot/main-bot/raspi/eurobot.log', level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        # Initialize Picamera2
        self.picam2 = Picamera2()
        self.picam2.rotate = rotate
        config = self.picam2.create_video_configuration(
            main={"size": (self.IMAGE_WIDTH, self.IMAGE_HEIGHT), "format": "RGB888"},
            transform=libcamera.Transform(hflip=1, vflip=1)
        )
        self.picam2.configure(config)

        # aruco detection
        self.aruco_dict = aruco.Dictionary_get(aruco.DICT_4X4_50)
        self.parameters = aruco.DetectorParameters_create()

        # For background capture - not needed since we dont capture in the background anymore
        self.frame = None
        self.running = False
        self._lock = threading.Lock()

    def start(self) -> None:
        self.picam2.start()
        #! time.sleep(2)  # warm-up
        self.running = True

    def stop(self) -> None:
        self.running = False
        self.picam2.stop()

    def _get_frame(self) -> np.ndarray:
        """
        Retrieve the latest frame. Raises if no frame available yet.
        """
        frame = self.picam2.capture_array()
        frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        threading.Thread(target=cv2.imwrite, args=(f"/home/eurobot/Desktop/camera/{time.strftime('%Y%m%d_%H%M%S')}.png", frame)).start()
        return frame

            
    def get_angle(self, mid_distance, mid_angle):
        """
        Liefert die actions zum anfahren der dosen
        """
        frame = self._get_frame()
        left_angle, left_distance, right_angle, right_distance = self._process_angle(frame)

        def polar_to_cartesian(distance, angle_deg):
            angle_rad = math.radians(angle_deg)
            x = distance * math.sin(angle_rad)
            z = distance * math.cos(angle_rad)
            return x, z
        
        left_x, left_z = polar_to_cartesian(left_distance, left_angle)
        mid_x, mid_z = polar_to_cartesian(mid_distance, mid_angle)
        right_x, right_z = polar_to_cartesian(right_distance, right_angle)
        
        x_values = [left_x, mid_x, right_x]
        z_values = [left_z, mid_z, right_z]
        
        A = np.vstack([x_values, np.ones(len(x_values))]).T
        m, b = np.linalg.lstsq(A, z_values, rcond=None)[0]
        
        robot_angle_rad = math.atan(m)
        robot_angle_deg = math.degrees(robot_angle_rad)
        
        wall_center_x = (left_x + right_x) / 2
        wall_center_z = (left_z + right_z) / 2
        
        optimal_distance = wall_center_x * math.sin(robot_angle_rad) + wall_center_z * math.cos(robot_angle_rad)
        
        # actions = [
        #     f"ta{-90+robot_angle_deg:.1f}",     # Drehe parallel zur Wand
        #     f"dd{optimal_distance:.1f}",     # Fahre optimale Distanz
        #     "ta90.0"                         # Drehe 90 Grad nach right
        # ]
        
        return robot_angle_deg, optimal_distance

    def get_distance(self) -> list:
        """
        Use latest frame, detect cans, show analysis for 3s,
        return [angle_deg, distance_m].
        """
        frame = self._get_frame()
        display, angle, distance = self._process_distance(frame)
        
        distance *= 1000

        # cv2.imshow("Distance Analysis", display)
        # cv2.waitKey(3000)
        # cv2.destroyWindow("Distance Analysis")

        return [angle, distance]

    def check_cans(self) -> bool:
        """
        Use latest frame, verify can placement, show preview 3s,
        return True if OK, else False.
        """
        frame = self._get_frame()
        self.logger.info("Camera: got frame")
        ok, display = self._process_check(frame)

        return ok

    def check_stacks(self, size: int, debug_cam: bool = False) -> bool:
        """
        Prüft ob ein Stack der gewünschten Größe korrekt aufgebaut ist.
        
        Args:
            size (int): Gewünschte Stack-Größe (1, 2, oder 3)
            debug_cam (bool): Debug-Ausgaben aktivieren
            
        Returns:
            bool: True wenn Stack korrekt, False sonst
        """
        frame = self._get_frame()
        if debug_cam:
            print(f"🎯 Prüfe Stack-Größe {size}")
        
        height = frame.shape[0]  # 1280
        width = frame.shape[1]   # 960
        
        # Ebenen-Definition (exakte Y-Bereiche)
        regions = {
            'top': (0, 335),           # oben: 0-335
            'middle': (335, 783),      # mitte: 335-783
            'bottom': (783, 1280)      # unten: 783-1280
        }
        
        if debug_cam:
            print(f"Bildgröße: {width}x{height}")
            print(f"Ebenen-Aufteilung:")
            for name, (start, end) in regions.items():
                print(f"  {name.capitalize()}: Y {start}-{end}")
        
        # Graustufen-Verarbeitung
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        processed = clahe.apply(gray)

        # Marker erkennen mit optimierten Parametern
        corners, ids, _ = aruco.detectMarkers(processed, self.aruco_dict, parameters=self.parameters)
        
        if ids is None:
            if debug_cam:
                print("❌ Keine Marker erkannt!")
            return False
        
        if debug_cam:
            print(f"✅ {len(ids)} Marker erkannt")

        # Pose estimation für Orientierungs- und Distanzprüfung
        rvecs, tvecs, _ = aruco.estimatePoseSingleMarkers(
            corners, self.TAG_SIZE, self.camera_matrix, self.dist_coeffs)
        
        # Rotationen berechnen
        rotations = self._calculate_rotations(rvecs)
        
        # Optimierte Grenzen
        MIN_DISTANCE = 0.10  # Reduziert von 0.20m
        MAX_DISTANCE = 1.00  # Erhöht von 0.60m
        MAX_ROTATION_Z = 15  # Erhöht von 10 Grad
        
        # Prüfe relevante Ebenen basierend auf Stack-Größe
        regions_to_check = []
        if size >= 1:
            regions_to_check.append(('bottom', regions['bottom']))
        if size >= 2:
            regions_to_check.append(('middle', regions['middle']))
        if size >= 3:
            regions_to_check.append(('top', regions['top']))
        
        # Prüfe jede Ebene
        for region_name, (y_start, y_end) in regions_to_check:
            if debug_cam:
                print(f"--- Prüfe Ebene: {region_name.upper()} (Y: {y_start}-{y_end}) ---")
            
            valid_markers = []
            
            # Finde Marker in dieser Ebene
            for i, (corner, marker_id) in enumerate(zip(corners, ids)):
                M = cv2.moments(corner[0])
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    
                    # Prüfe Y-Position
                    if y_start <= cy <= y_end:
                        distance = tvecs[i][0][2] * self.CALIB_FACTOR
                        rot_z = rotations[i][2]
                        
                        if debug_cam:
                            print(f"  Marker {marker_id[0]} in Ebene: "
                                f"Pos({cx},{cy}), Dist {distance:.2f}m, Rot {rot_z:.1f}°")
                        
                        # Prüfe Distanz (lockere Grenzen)
                        distance_ok = MIN_DISTANCE <= distance <= MAX_DISTANCE
                        
                        # Prüfe Orientierung (lockere Grenzen)
                        rotation_ok = -MAX_ROTATION_Z <= rot_z <= MAX_ROTATION_Z
                        
                        if debug_cam:
                            print(f"    Distanz OK: {distance_ok} ({MIN_DISTANCE}m ≤ {distance:.2f}m ≤ {MAX_DISTANCE}m)")
                            print(f"    Rotation OK: {rotation_ok} (-{MAX_ROTATION_Z}° ≤ {rot_z:.1f}° ≤ {MAX_ROTATION_Z}°)")
                        
                        if distance_ok and rotation_ok:
                            # Speichere gültige Marker mit ihrer 3D-Position
                            valid_markers.append({
                                'id': marker_id[0],
                                'pixel_pos': (cx, cy),
                                '3d_pos': tvecs[i][0],  # 3D Position für Distanzberechnung
                                'distance': distance,
                                'rotation_z': rot_z
                            })
                            if debug_cam:
                                print(f"    ✅ Marker {marker_id[0]} GÜLTIG")
                        else:
                            if debug_cam:
                                print(f"    ❌ Marker {marker_id[0]} ungültig")
            
            # Prüfe ob mindestens 2 gültige Marker vorhanden sind
            if len(valid_markers) < 2:
                if debug_cam:
                    print(f"  ❌ Nur {len(valid_markers)} gültige Marker, mindestens 2 benötigt")
                    print(f"❌ Stack-Größe {size} fehlgeschlagen: Ebene {region_name} hat nur {len(valid_markers)}/2 gültige Marker")
                self.logger.info(f"Stack size {size} failed: region {region_name} has only {len(valid_markers)}/2 valid markers")
                return False
            
            # Prüfe 4cm-Abstand zwischen Markern
            has_4cm_distance = False
            MIN_DISTANCE_3D = 0.03  # 4cm in Metern
            
            if debug_cam:
                print(f"  Prüfe 4cm-Abstände zwischen {len(valid_markers)} Markern:")
            
            for i in range(len(valid_markers)):
                for j in range(i + 1, len(valid_markers)):
                    marker1 = valid_markers[i]
                    marker2 = valid_markers[j]
                    
                    # Berechne 3D-Distanz zwischen den beiden Markern
                    pos1 = marker1['3d_pos']
                    pos2 = marker2['3d_pos']
                    distance_3d = np.linalg.norm(pos1 - pos2) * self.CALIB_FACTOR
                    
                    if debug_cam:
                        print(f"    Marker {marker1['id']} <-> Marker {marker2['id']}: {distance_3d:.3f}m")
                    
                    if distance_3d >= MIN_DISTANCE_3D:
                        has_4cm_distance = True
                        if debug_cam:
                            print(f"    ✅ 4cm-Abstand gefunden: {distance_3d:.3f}m >= {MIN_DISTANCE_3D}m")
                        break
                
                if has_4cm_distance:
                    break
            
            if not has_4cm_distance:
                if debug_cam:
                    print(f"  ❌ Kein 4cm-Abstand zwischen Markern gefunden")
                    print(f"❌ Stack-Größe {size} fehlgeschlagen: Ebene {region_name} hat keinen 4cm-Abstand zwischen Markern")
                self.logger.info(f"Stack size {size} failed: region {region_name} has no 4cm distance between markers")
                return False
            
            if debug_cam:
                print(f"  ✅ Ergebnis {region_name}: {len(valid_markers)} gültige Marker mit 4cm-Abstand - ERFOLGREICH")
        
        if debug_cam:
            print(f"✅ Stack-Größe {size} erfolgreich validiert")
        self.logger.info(f"Stack size {size} validation successful")
        return True

    def _group_markers_by_x_distance(self, markers: list, max_pixel_distance: int) -> list:
        """
        Gruppiert Marker basierend auf horizontaler Pixel-Distanz.
        
        Args:
            markers: Liste von (index, cx, cy) Tupeln
            max_pixel_distance: Maximale horizontale Pixel-Distanz für Gruppierung
            
        Returns:
            list: Liste von Gruppen (jede Gruppe ist Liste von Marker-Tupeln)
        """
        if not markers:
            return []
        
        groups = []
        visited = [False] * len(markers)
        
        for i, (idx, cx, cy) in enumerate(markers):
            if not visited[i]:
                group = [markers[i]]
                visited[i] = True
                
                # Finde alle Marker in horizontaler Nähe
                for j, (other_idx, other_cx, other_cy) in enumerate(markers):
                    if not visited[j]:
                        x_distance = abs(cx - other_cx)
                        if x_distance <= max_pixel_distance:
                            group.append(markers[j])
                            visited[j] = True
                
                groups.append(group)
        
        return groups

    # Internal: process for distance
    def _process_distance(self, frame: np.ndarray) -> tuple:
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        processed = clahe.apply(gray)

        corners, ids, _ = aruco.detectMarkers(processed, self.aruco_dict, parameters=self.parameters)
        display = frame.copy()

        all_centers, all_distances = [], []
        angle, distance = None, None

        if ids is not None:
            rvecs, tvecs, _ = aruco.estimatePoseSingleMarkers(
                corners, self.TAG_SIZE, self.camera_matrix, self.dist_coeffs)

            # Group nearby markers
            groups, visited = [], [False] * len(ids)
            for i in range(len(ids)):
                if not visited[i]:
                    group = [i]
                    visited[i] = True
                    j = 0
                    while j < len(group):
                        cur = group[j]
                        for k in range(len(ids)):
                            if not visited[k] and np.linalg.norm(tvecs[cur][0] - tvecs[k][0]) <= self.GROUP_DISTANCE:
                                group.append(k)
                                visited[k] = True
                        j += 1
                    groups.append(group)

            self.logger.info(f"Detected groups: {len(groups)}")
            for group in groups:
                vecs = [tvecs[i][0] for i in group]
                avg_t = np.mean(vecs, axis=0)
                dist_m = avg_t[2] * self.CALIB_FACTOR

                pts = []
                for i in group:
                    M = cv2.moments(corners[i][0])
                    if M["m00"]:
                        pts.append((int(M["m10"]/M["m00"]), int(M["m01"]/M["m00"])))
                if not pts:
                    continue
                avg_px = int(np.mean([p[0] for p in pts]))

                all_centers.append((avg_px, 0))
                all_distances.append(dist_m)

                # cv2.circle(display, (avg_px, int(self.IMAGE_HEIGHT/2)), 10, (0, 255, 0), -1)
                # cv2.putText(display, f"{dist_m:.2f}m", (avg_px+15, int(self.IMAGE_HEIGHT/2)-5),
                #             cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)

            if all_centers:
                mx = int(np.mean([c[0] for c in all_centers]))
                distance = np.mean(all_distances)
                angle = ((mx - self.IMAGE_WIDTH//2) / (self.IMAGE_WIDTH//2)) * self.MAX_ANGLE

                # cv2.circle(display, (mx, int(self.IMAGE_HEIGHT/2)), 15, (255, 0, 0), -1)
                # cv2.putText(display, f"Gesamt: {angle:.1f}\u00b0 | {distance:.2f}m",
                #             (mx-100, int(self.IMAGE_HEIGHT/2)-20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

        return display, angle, distance

    # Internal: compute rotations
    def _calculate_rotations(self, rvecs: np.ndarray) -> list:
        rotations = []
        for r in rvecs:
            R, _ = cv2.Rodrigues(r)
            sy = np.sqrt(R[0,0]**2 + R[1,0]**2)
            if sy < 1e-6:
                x = np.arctan2(-R[1,2], R[1,1])
                y = np.arctan2(-R[2,0], sy)
                z = 0
            else:
                x = np.arctan2(R[2,1], R[2,2])
                y = np.arctan2(-R[2,0], sy)
                z = np.arctan2(R[1,0], R[0,0])
            rotations.append(tuple(np.degrees((x, y, z))))
        return rotations

    # Internal: process for checking cans
    def _process_check(self, frame: np.ndarray) -> tuple:
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        processed = clahe.apply(gray)

        corners, ids, _ = aruco.detectMarkers(processed, self.aruco_dict, parameters=self.parameters)
        display = frame.copy()
        ok = False

        if ids is not None:
            rvecs, tvecs, _ = aruco.estimatePoseSingleMarkers(
                corners, self.TAG_SIZE, self.camera_matrix, self.dist_coeffs)
            rots = self._calculate_rotations(rvecs)

            groups, visited = [], [False] * len(ids)
            for i in range(len(ids)):
                if not visited[i]:
                    group = [i]
                    visited[i] = True
                    j = 0
                    while j < len(group):
                        cur = group[j]
                        for k in range(len(ids)):
                            if not visited[k] and np.linalg.norm(tvecs[cur][0] - tvecs[k][0]) <= self.GROUP_DISTANCE:
                                group.append(k)
                                visited[k] = True
                        j += 1
                    groups.append(group)
            
            correct_count = len(groups) >= 3
            dist_ok = all(
                0.6 >= np.mean([tvecs[i][0][2]*self.CALIB_FACTOR for i in g]) >= 0.02
                for g in groups)
            rot_ok = any(-10 < r[2] < 10 for r in rots)
            ok = correct_count and dist_ok and rot_ok
            self.logger.info(f"correct count: {correct_count} - dist_ok: {dist_ok} - rot_ok - {rot_ok}")
            self.logger.info(f"len groups: {len(groups)}")

            for group in groups:
                pts = []
                for i in group:
                    M = cv2.moments(corners[i][0])
                    if M['m00']:
                        pts.append((int(M['m10']/M['m00']), int(M['m01']/M['m00'])))
                if pts:
                    cx = int(np.mean([p[0] for p in pts]))
                    cy = int(np.mean([p[1] for p in pts]))
                    # cv2.circle(display, (cx, cy), 10, (0,255,0), -1)

        color = (0,255,0) if ok else (0,0,255)
        # cv2.putText(display, f"Check Cans: {ok}", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
        return ok, display
        
    def _process_angle(self, frame: np.ndarray):
        """
        Interne Verarbeitung: erkennt Dosen, gruppiert sie, ermittelt
        die äußersten links & rechts und berechnet Winkel + Abstand.
        Gibt zurück: (l_angle, l_dist, r_angle, r_dist)
        """
        # 1) Graustufen + CLAHE
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        processed = clahe.apply(gray)

        # 2) Marker erkennen
        corners, ids, _ = aruco.detectMarkers(
            processed, self.aruco_dict, parameters=self.parameters
        )
        if ids is None or len(ids) < 2:
            return None, None, None, None

        # 3) Pose schätzen
        _, tvecs, _ = aruco.estimatePoseSingleMarkers(
            corners, self.TAG_SIZE, self.camera_matrix, self.dist_coeffs
        )

        # 4) Gruppenbildung
        groups, visited = [], [False] * len(ids)
        for i in range(len(ids)):
            if not visited[i]:
                group = [i]
                visited[i] = True
                for j in group:
                    for k in range(len(ids)):
                        if not visited[k] and np.linalg.norm(tvecs[j][0] - tvecs[k][0]) <= self.GROUP_DISTANCE:
                            group.append(k)
                            visited[k] = True
                groups.append(group)

        # 5) Für jede Gruppe mittleren Pixel-x und Abstand sammeln
        px_list, dist_list = [], []
        for grp in groups:
            vecs = [tvecs[i][0] for i in grp]
            avg_t = np.mean(vecs, axis=0)
            dist_m = avg_t[2] * self.CALIB_FACTOR

            # Bild-Mittelpunkt in x
            pts = []
            for i in grp:
                M = cv2.moments(corners[i][0])
                if M["m00"]:
                    pts.append((M["m10"]/M["m00"], M["m01"]/M["m00"]))
            if not pts:
                continue
            avg_px = float(np.mean([p[0] for p in pts]))

            px_list.append(avg_px)
            dist_list.append(dist_m)

        if len(px_list) < 2:
            return None, None, None, None

        # 6) äußerste links/rechts finden
        left_idx, right_idx = int(np.argmin(px_list)), int(np.argmax(px_list))

        # 7) Winkel berechnen
        center = self.IMAGE_WIDTH / 2.0
        left_angle  = ((px_list[left_idx]  - center) / center) * self.MAX_ANGLE
        right_angle = ((px_list[right_idx] - center) / center) * self.MAX_ANGLE

        # 8) Abstände
        left_dist, right_dist = dist_list[left_idx], dist_list[right_idx]

        return left_angle, left_dist, right_angle, right_dist


def main():
    # task = Task(None, [['d500', 't50'], ['d340', 't50'], ['d650', 't76']])
    # task = Task(None, [])
    print("started main")
    
if __name__ == '__main__':
    main()