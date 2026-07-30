import sys
import numpy as np
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton
from PyQt6 import sip

# Add build directory to path to find the .so module
sys.path.append("./build")
import fast_layout_viewer

class FastViewerWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # 1. Instantiate Pybind11 C++ Core Object
        self.core = fast_layout_viewer.FastLayoutViewerCore()
        
        # 2. Extract memory pointer and wrap in PyQt6 sip
        ptr = self.core.get_ptr()
        self.native_widget = sip.wrapinstance(ptr, QWidget)
        
        # 3. Embed into PyQt6 layout natively
        self.layout.addWidget(self.native_widget)

    def load_data(self, x, y, w, h):
        # Sends flat C-contiguous lists instantly to C++ std::vector<float>
        self.core.load_geometry(x, y, w, h)

class SilisApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Silis - FastLayoutViewer (100k Rects)")
        self.resize(1024, 768)
        
        self.viewer = FastViewerWidget()
        self.setCentralWidget(self.viewer)
        
        # Generate 100,000 random layout rectangles
        N = 100000
        x = np.random.uniform(0, 8000, N).astype(np.float32).tolist()
        y = np.random.uniform(0, 8000, N).astype(np.float32).tolist()
        w = np.random.uniform(10, 100, N).astype(np.float32).tolist()
        h = np.random.uniform(10, 100, N).astype(np.float32).tolist()
        
        # Offload to C++ Engine
        self.viewer.load_data(x, y, w, h)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SilisApp()
    window.show()
    sys.exit(app.exec())
