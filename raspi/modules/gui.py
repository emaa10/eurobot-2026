import sys
import asyncio
import time
import logging
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, 
                           QVBoxLayout, QWidget, QLabel, QGridLayout)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QPalette
from new_motor_controller import Motorcontroller

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MotorWorker(QThread):
    status_update = pyqtSignal(str)
    
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.loop = asyncio.new_event_loop()
        self.running = True
        
    def run(self):
        asyncio.set_event_loop(self.loop)
        while self.running:
            try:
                self.loop.run_forever()
            except Exception as e:
                logger.error(f"Error in event loop: {e}")
                self.status_update.emit(f"Error: {str(e)}")
                
    def stop(self):
        self.running = False
        self.loop.call_soon_threadsafe(self.loop.stop)
        
    async def run_test_case(self, case_number):
        try:
            if case_number == 1:
                await self.controller.drive(50)
                time.sleep(3)
                await self.controller.drive(-50)
            elif case_number == 2:
                await self.controller.drive(100)
                time.sleep(3)
                await self.controller.drive(-100)
            elif case_number == 3:
                await self.controller.turn(90)
                time.sleep(2)
                await self.controller.turn(-90)
            elif case_number == 4:
                await self.controller.turn(360)
                time.sleep(2)
                await self.controller.turn(-360)
            self.status_update.emit("Test completed!")
        except Exception as e:
            logger.error(f"Error in test case {case_number}: {e}")
            self.status_update.emit(f"Error: {str(e)}")

class MotorControllerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Motor Controller Test Interface")
        self.setGeometry(100, 100, 800, 600)  # Increased window size
        
        # Initialize motor controller
        self.controller = Motorcontroller()
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Add title label
        title_label = QLabel("Select Test Case to Run:")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; margin: 20px;")
        main_layout.addWidget(title_label)
        
        # Create grid layout for buttons
        grid_layout = QGridLayout()
        grid_layout.setSpacing(20)  # Add spacing between buttons
        
        # Create buttons for each test case
        self.test_buttons = []
        button_colors = [
            ("#FF6B6B", "#FF8E8E"),  # Red
            ("#4ECDC4", "#6EDDD6"),  # Teal
            ("#45B7D1", "#65C7E1"),  # Blue
            ("#96CEB4", "#B6DEC4")   # Green
        ]
        
        test_cases = ["drive 50", "drive 100", "turn 90", "turn 360"]
        
        
        for i, case in enumerate(test_cases):
            btn = QPushButton(case)
            btn.setMinimumSize(200, 150)  # Make buttons larger
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {button_colors[i][0]};
                    color: white;
                    font-size: 20px;
                    font-weight: bold;
                    border-radius: 10px;
                    padding: 10px;
                }}
                QPushButton:hover {{
                    background-color: {button_colors[i][1]};
                }}
                QPushButton:pressed {{
                    background-color: {button_colors[i][0]};
                }}
            """)
            btn.clicked.connect(lambda checked, case=i+1: self.run_test_case(case))
            self.test_buttons.append(btn)
            
            # Calculate grid position
            row = (i) // 2
            col = (i) % 2
            grid_layout.addWidget(btn, row, col)
        
        main_layout.addLayout(grid_layout)
        
        # Add status label
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 24px; font-weight: bold; margin: 20px; color: #333333;")
        main_layout.addWidget(self.status_label)
        
        # Add stretch to push everything to the top
        main_layout.addStretch()
        
        # Initialize worker thread
        self.worker = MotorWorker(self.controller)
        self.worker.status_update.connect(self.update_status)
        self.worker.start()
    
    def update_status(self, message):
        self.status_label.setText(message)
        QApplication.processEvents()
    
    def run_test_case(self, case_number):
        self.status_label.setText(f"Running Test Case {case_number}...")
        QApplication.processEvents()
        
        # Run the test case in the worker thread
        asyncio.run_coroutine_threadsafe(
            self.worker.run_test_case(case_number),
            self.worker.loop
        )

    def closeEvent(self, event):
        # Clean up the worker thread
        self.worker.stop()
        self.worker.wait()
        event.accept()

def main():
    try:
        app = QApplication(sys.argv)
        window = MotorControllerGUI()
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 