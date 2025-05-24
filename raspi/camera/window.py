#!/usr/bin/env python3

import numpy as np
from picamera2 import Picamera2
from PIL import Image
import tkinter as tk
from tkinter import Label
from PIL import ImageTk
import threading
import time

class RotatedCameraViewer:
    def __init__(self):
        self.running = False
        self.picam2 = Picamera2()
        
        # Tkinter GUI setup
        self.root = tk.Tk()
        self.root.title("PiCam2 - 90° gedreht")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Label für das Bild
        self.image_label = Label(self.root)
        self.image_label.pack()
        
    def rotate_image_90(self, image_array):
        """Dreht das Bild um 90° im Uhrzeigersinn"""
        # Numpy rotate: 90° im Uhrzeigersinn = 3x90° gegen Uhrzeigersinn
        return np.rot90(image_array, k=-1)
    
    def start_camera(self):
        """Startet die Kamera"""
        # Kamera-Konfiguration
        config = self.picam2.create_preview_configuration(
            main={"size": (640, 480), "format": "RGB888"}
        )
        self.picam2.configure(config)
        self.picam2.start()
        self.running = True
        
    def update_frame(self):
        """Aktualisiert das angezeigte Bild"""
        while self.running:
            try:
                # Frame von der Kamera erfassen
                frame = self.picam2.capture_array()
                
                # Frame um 90° drehen
                rotated_frame = self.rotate_image_90(frame)
                
                # Numpy array zu PIL Image konvertieren
                pil_image = Image.fromarray(rotated_frame)
                
                # Für Tkinter konvertieren
                photo = ImageTk.PhotoImage(pil_image)
                
                # GUI im Hauptthread aktualisieren
                self.root.after(0, self.update_image_label, photo)
                
                # Kurze Pause für flüssige Darstellung
                time.sleep(0.033)  # ca. 30 FPS
                
            except Exception as e:
                print(f"Fehler beim Frame-Update: {e}")
                break
    
    def update_image_label(self, photo):
        """Aktualisiert das Label mit dem neuen Bild"""
        self.image_label.configure(image=photo)
        self.image_label.image = photo  # Referenz behalten
    
    def on_closing(self):
        """Wird aufgerufen wenn das Fenster geschlossen wird"""
        self.running = False
        self.picam2.stop()
        self.root.destroy()
        print("Kamera gestoppt und Fenster geschlossen.")
    
    def run(self):
        """Startet die Anwendung"""
        print("Kamera gestartet. Schließe das Fenster zum Beenden.")
        
        # Kamera starten
        self.start_camera()
        
        # Frame-Update Thread starten
        update_thread = threading.Thread(target=self.update_frame, daemon=True)
        update_thread.start()
        
        # Tkinter Hauptschleife starten
        self.root.mainloop()

def main():
    try:
        viewer = RotatedCameraViewer()
        viewer.run()
    except KeyboardInterrupt:
        print("\nProgramm durch Benutzer beendet.")
    except Exception as e:
        print(f"Fehler aufgetreten: {e}")

if __name__ == "__main__":
    main()
