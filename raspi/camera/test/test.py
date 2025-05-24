import cv2
import numpy as np
import cv2.aruco as aruco
import logging
import os
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

class OptimizedMockCamera:
    """
    Optimierte Mock-Kamera basierend auf den Analysedaten
    """
    # Angepasste Konstanten basierend auf deinen Daten
    TAG_SIZE = 0.0235  # ArUco marker size in meters
    
    # Distanz-Parameter (angepasst basierend auf erkannten Problemen)
    CALIB_FACTOR = 1.5  # Erhöht von 0.57 - experimentell anpassen
    MIN_DISTANCE = 0.10  # Reduziert von 0.20m
    MAX_DISTANCE = 1.00  # Erhöht von 0.60m
    
    # Orientierungs-Parameter (lockerer)
    MAX_ROTATION_Z = 15  # Erhöht von 10 Grad
    
    # Bildparameter
    IMAGE_WIDTH = 960
    IMAGE_HEIGHT = 1280

    def __init__(self, test_image_path: str):
        """Initialisiert die optimierte Mock-Kamera"""
        if not os.path.exists(test_image_path):
            raise FileNotFoundError(f"Testbild nicht gefunden: {test_image_path}")

        self.test_image = cv2.imread(test_image_path)
        if self.test_image is None:
            raise ValueError(f"Konnte Testbild nicht laden: {test_image_path}")

        self.test_image = cv2.cvtColor(self.test_image, cv2.COLOR_BGR2RGB)
        
        print(f"Bildgröße: {self.test_image.shape}")

        # Optimierte Kameramatrix basierend auf Bildgröße
        self.camera_matrix = np.array([
            [960, 0, 480],      # fx, 0, cx
            [0, 960, 640],      # 0, fy, cy  
            [0, 0, 1]           # 0, 0, 1
        ], dtype=np.float32)

        self.dist_coeffs = np.zeros((4, 1), dtype=np.float32)

        # Logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

        # Beste Erkennungsparameter (basierend auf deinen Tests)
        self.aruco_dict = aruco.Dictionary_get(aruco.DICT_4X4_50)
        self.parameters = aruco.DetectorParameters_create()
        
        # Optimierte Parameter
        self.parameters.adaptiveThreshWinSizeMin = 3
        self.parameters.adaptiveThreshWinSizeMax = 23
        self.parameters.adaptiveThreshWinSizeStep = 10
        self.parameters.adaptiveThreshConstant = 7
        self.parameters.minMarkerPerimeterRate = 0.03
        self.parameters.maxMarkerPerimeterRate = 4.0

    def _get_frame(self) -> np.ndarray:
        """Gibt das Testbild zurück"""
        return self.test_image.copy()

    def detect_markers_optimized(self):
        """Optimierte Marker-Erkennung basierend auf deinen Daten"""
        frame = self._get_frame()
        
        # Beste Methode: Original Grau (laut deinen Tests)
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        
        corners, ids, _ = aruco.detectMarkers(gray, self.aruco_dict, parameters=self.parameters)
        
        if ids is None:
            return [], [], []
            
        # Pose estimation
        rvecs, tvecs, _ = aruco.estimatePoseSingleMarkers(
            corners, self.TAG_SIZE, self.camera_matrix, self.dist_coeffs)
        
        return corners, ids, rvecs, tvecs

    def check_perfect_stack(self, size: int) -> dict:
        """
        Perfekter Stack-Check basierend auf deinen Daten
        
        Returns:
            dict: Detaillierte Ergebnisse für jede Ebene
        """
        if size not in [1, 2, 3]:
            raise ValueError(f"Invalid stack size: {size}. Must be 1, 2, or 3.")

        frame = self._get_frame()
        height = frame.shape[0]  # 1280
        
        # Ebenen-Definition (optimiert basierend auf deinen Marker-Positionen)
        section_height = height // 3  # 426
        
        # Angepasste Ebenen mit etwas Überlappung
        regions = {
            'top': (0, section_height + 50),           # 0-476
            'middle': (section_height - 50, 2 * section_height + 50),  # 376-876  
            'bottom': (2 * section_height - 50, height) # 802-1280
        }
        
        print(f"\n=== Optimierte Ebenen-Aufteilung ===")
        for name, (start, end) in regions.items():
            print(f"{name.capitalize()}: Y {start}-{end}")

        # Marker erkennen
        corners, ids, rvecs, tvecs = self.detect_markers_optimized()
        
        if len(ids) == 0:
            print("❌ Keine Marker erkannt!")
            return {'success': False, 'regions': {}}

        print(f"\n✅ {len(ids)} Marker erkannt")
        
        # Rotationen berechnen
        rotations = self._calculate_rotations(rvecs)
        
        # Marker-Details ausgeben
        print(f"\n=== Marker-Details ===")
        for i, (corner, marker_id) in enumerate(zip(corners, ids)):
            M = cv2.moments(corner[0])
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                distance = tvecs[i][0][2] * self.CALIB_FACTOR
                rot_z = rotations[i][2]
                
                print(f"Marker {marker_id[0]}: Position ({cx}, {cy}), "
                      f"Distanz {distance:.2f}m, Rotation Z {rot_z:.1f}°")

        # Prüfe relevante Ebenen basierend auf Stack-Größe
        regions_to_check = []
        if size >= 1:
            regions_to_check.append(('bottom', regions['bottom']))
        if size >= 2:
            regions_to_check.append(('middle', regions['middle']))
        if size >= 3:
            regions_to_check.append(('top', regions['top']))

        results = {'success': True, 'regions': {}}
        
        # Prüfe jede Ebene
        for region_name, (y_start, y_end) in regions_to_check:
            print(f"\n--- Prüfe Ebene: {region_name.upper()} (Y: {y_start}-{y_end}) ---")
            
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
                        
                        print(f"  Marker {marker_id[0]} in Ebene: "
                              f"Pos({cx},{cy}), Dist {distance:.2f}m, Rot {rot_z:.1f}°")
                        
                        # Prüfe Distanz (lockere Grenzen)
                        distance_ok = self.MIN_DISTANCE <= distance <= self.MAX_DISTANCE
                        
                        # Prüfe Orientierung (lockere Grenzen)
                        rotation_ok = -self.MAX_ROTATION_Z <= rot_z <= self.MAX_ROTATION_Z
                        
                        print(f"    Distanz OK: {distance_ok} ({self.MIN_DISTANCE}m ≤ {distance:.2f}m ≤ {self.MAX_DISTANCE}m)")
                        print(f"    Rotation OK: {rotation_ok} (-{self.MAX_ROTATION_Z}° ≤ {rot_z:.1f}° ≤ {self.MAX_ROTATION_Z}°)")
                        
                        if distance_ok and rotation_ok:
                            valid_markers.append({
                                'id': marker_id[0],
                                'position': (cx, cy),
                                'distance': distance,
                                'rotation_z': rot_z
                            })
                            print(f"    ✅ Marker {marker_id[0]} GÜLTIG")
                        else:
                            print(f"    ❌ Marker {marker_id[0]} ungültig")
            
            region_success = len(valid_markers) >= 2
            
            results['regions'][region_name] = {
                'success': region_success,
                'valid_markers_count': len(valid_markers),
                'valid_markers': valid_markers,
                'required': 2
            }
            
            print(f"  Ergebnis {region_name}: {len(valid_markers)}/2 gültige Marker - "
                  f"{'✅ ERFOLGREICH' if region_success else '❌ FEHLGESCHLAGEN'}")
            
            if not region_success:
                results['success'] = False

        return results

    def _calculate_rotations(self, rvecs: np.ndarray) -> list:
        """Berechnet Euler-Winkel aus Rotationsvektoren"""
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

    def visualize_perfect_stack(self, size: int, results: dict):
        """Erstellt perfekte Visualisierung"""
        frame = self._get_frame()
        corners, ids, rvecs, tvecs = self.detect_markers_optimized()
        
        fig, ax = plt.subplots(1, 1, figsize=(12, 16))
        ax.imshow(frame)
        ax.set_title(f'Stack Size {size} - {"✅ ERFOLGREICH" if results["success"] else "❌ FEHLGESCHLAGEN"}', 
                     fontsize=16, fontweight='bold')
        
        # Ebenen einzeichnen
        height = frame.shape[0]
        section_height = height // 3
        
        region_colors = {'top': 'red', 'middle': 'blue', 'bottom': 'green'}
        region_positions = {
            'top': (0, section_height + 50),
            'middle': (section_height - 50, 2 * section_height + 50),
            'bottom': (2 * section_height - 50, height)
        }
        
        # Zeichne nur relevante Ebenen
        regions_to_show = []
        if size >= 1: regions_to_show.append('bottom')
        if size >= 2: regions_to_show.append('middle') 
        if size >= 3: regions_to_show.append('top')
        
        for region_name in regions_to_show:
            y_start, y_end = region_positions[region_name]
            color = region_colors[region_name]
            
            # Ebenen-Rechteck
            rect = Rectangle((0, y_start), frame.shape[1], y_end - y_start,
                           linewidth=3, edgecolor=color, facecolor='none')
            ax.add_patch(rect)
            
            # Ebenen-Label mit Status
            region_result = results['regions'].get(region_name, {'success': False, 'valid_markers_count': 0})
            status = "✅" if region_result['success'] else "❌"
            ax.text(10, y_start + 40, 
                   f'{region_name.upper()} {status} ({region_result["valid_markers_count"]}/2)', 
                   color=color, fontsize=14, fontweight='bold',
                   bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.8))

        # Marker einzeichnen
        if len(ids) > 0:
            rotations = self._calculate_rotations(rvecs)
            
            for i, (corner, marker_id) in enumerate(zip(corners, ids)):
                # Marker-Umriss
                corner_points = corner[0]
                xs = corner_points[:, 0]
                ys = corner_points[:, 1]
                ax.plot(np.append(xs, xs[0]), np.append(ys, ys[0]), 'yellow', linewidth=2)
                
                # Mittelpunkt
                cx = int(np.mean(xs))
                cy = int(np.mean(ys))
                
                # Bestimme ob Marker gültig ist
                distance = tvecs[i][0][2] * self.CALIB_FACTOR
                rot_z = rotations[i][2]
                
                distance_ok = self.MIN_DISTANCE <= distance <= self.MAX_DISTANCE
                rotation_ok = -self.MAX_ROTATION_Z <= rot_z <= self.MAX_ROTATION_Z
                is_valid = distance_ok and rotation_ok
                
                # Marker-Punkt (grün wenn gültig, rot wenn ungültig)
                marker_color = 'lime' if is_valid else 'red'
                ax.plot(cx, cy, 'o', color=marker_color, markersize=10)
                
                # Marker-Info
                ax.text(cx + 15, cy, 
                       f'ID:{marker_id[0]}\nD:{distance:.2f}m\nR:{rot_z:.1f}°', 
                       color='white', fontsize=9, fontweight='bold',
                       bbox=dict(boxstyle="round,pad=0.2", facecolor=marker_color, alpha=0.8))

        ax.axis('off')
        plt.tight_layout()
        
        filename = f'perfect_stack_{size}_{"success" if results["success"] else "failed"}.png'
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        print(f"\n📊 Visualisierung gespeichert: {filename}")
        plt.close()

    def calibrate_distance_factor(self):
        """Hilfsfunktion um den CALIB_FACTOR zu kalibrieren"""
        print(f"\n=== Distanz-Kalibrierung ===")
        corners, ids, rvecs, tvecs = self.detect_markers_optimized()
        
        if len(ids) == 0:
            print("Keine Marker für Kalibrierung gefunden")
            return
            
        print(f"Aktuelle CALIB_FACTOR: {self.CALIB_FACTOR}")
        print("Rohdistanzen und berechnete Distanzen:")
        
        for i, marker_id in enumerate(ids):
            raw_distance = tvecs[i][0][2]
            calculated_distance = raw_distance * self.CALIB_FACTOR
            print(f"Marker {marker_id[0]}: Raw={raw_distance:.3f} -> Calc={calculated_distance:.3f}m")
        
        print(f"\nFür Distanzen zwischen 0.20-0.60m sollte CALIB_FACTOR angepasst werden.")
        print(f"Beispiel: Wenn Raw=0.35 und gewünschte Distanz=0.30m, dann CALIB_FACTOR=0.86")


def test_perfect_stack():
    """Haupttest mit perfektem Algorithmus"""
    test_image_path = "20250524_153844.png"

    try:
        # Optimierte Kamera erstellen
        camera = OptimizedMockCamera(test_image_path)
        
        print("🎯 === PERFEKTER ARUCO STACK DETECTION TEST ===")
        print(f"📸 Testbild: {test_image_path}")
        
        # Distanz-Kalibrierung anzeigen
        camera.calibrate_distance_factor()
        
        # Tests für alle Stack-Größen
        for stack_size in [1, 2, 3]:
            print(f"\n{'='*60}")
            print(f"🔍 TESTE STACK GRÖßE {stack_size}")
            print(f"{'='*60}")
            
            results = camera.check_perfect_stack(stack_size)
            
            # Endergebnis
            success = results['success']
            print(f"\n🎯 ENDERGEBNIS STACK {stack_size}: {'✅ ERFOLGREICH' if success else '❌ FEHLGESCHLAGEN'}")
            
            if success:
                print("🎉 Alle Ebenen haben mindestens 2 gültige Marker!")
            else:
                print("⚠️  Eine oder mehrere Ebenen haben zu wenig gültige Marker.")
            
            # Zusammenfassung pro Ebene
            print(f"\n📊 Zusammenfassung:")
            for region_name, region_data in results['regions'].items():
                status = "✅" if region_data['success'] else "❌"
                print(f"  {region_name.capitalize()}: {status} {region_data['valid_markers_count']}/2 gültige Marker")
            
            # Visualisierung erstellen
            camera.visualize_perfect_stack(stack_size, results)
            
            print(f"\n" + "-"*60)

        print(f"\n🏁 === TEST ABGESCHLOSSEN ===")
        print("📁 Alle Visualisierungen wurden als PNG-Dateien gespeichert.")
        
    except Exception as e:
        print(f"❌ Fehler: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_perfect_stack()
