import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import QUrl

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEnginePage
    _WEBENGINE_AVAILABLE = True
except ImportError:
    _WEBENGINE_AVAILABLE = False


class SilisWebEnginePage(QWebEnginePage):
    """
    Custom WebEnginePage that forwards JavaScript console messages
    to registered message handlers (e.g. for ROHD Flutter bridge).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.message_handlers = []

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        if message:
            for handler in self.message_handlers:
                try:
                    handler(message)
                except Exception as e:
                    print(f"[SILIS WebEngine] Handler exception: {e}")
        super().javaScriptConsoleMessage(level, message, lineNumber, sourceID)


class SharedWebEngineManager:
    """
    Singleton manager providing a single, shared QWebEngineView instance
    across Silis tabs (Monaco Editor, DigitalJS Schematic Viewer, and ROHD Waveform Viewer).
    Avoids spinning up multiple QtWebEngineProcess instances, drastically reducing memory
    usage and eliminating GUI event loop stutter.
    """
    _instance = None
    _view = None
    _current_owner = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = SharedWebEngineManager()
        return cls._instance

    @classmethod
    def is_available(cls):
        return _WEBENGINE_AVAILABLE

    def get_view(self):
        if not _WEBENGINE_AVAILABLE:
            return None
        if self._view is None:
            self._view = QWebEngineView()
            self._page = SilisWebEnginePage(self._view)
            self._view.setPage(self._page)
        return self._view

    def add_console_handler(self, handler):
        self.get_view()
        if hasattr(self, '_page') and self._page and handler not in self._page.message_handlers:
            self._page.message_handlers.append(handler)

    def attach_to(self, target_widget, owner_id):
        """
        Attaches the single QWebEngineView into target_widget layout.
        Returns the QWebEngineView instance or None if WebEngine is unavailable.
        """
        view = self.get_view()
        if not view:
            return None

        # Detach from previous parent if any
        old_parent = view.parentWidget()
        if old_parent and old_parent != target_widget:
            if old_parent.layout():
                old_parent.layout().removeWidget(view)
            view.setParent(None)

        # Attach to target layout
        if target_widget.layout() is None:
            target_widget.setLayout(QVBoxLayout(target_widget))
            target_widget.layout().setContentsMargins(0, 0, 0, 0)
        
        target_widget.layout().addWidget(view)
        view.show()
        self._current_owner = owner_id
        return view

    def current_owner(self):
        return self._current_owner
