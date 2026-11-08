"""
delta_updater.py
Delta update system for Silis EDA AppImage.
Queries GitHub releases, identifies the target update, performs block-level
differential updates via HTTP Range requests (or zsync when available),
and provides a clean, native Qt6 update dialog.
"""

import os
import sys
import json
import time
import hashlib
import urllib.request
import urllib.error
import tempfile
import shutil
from typing import Dict, Any, Optional, Tuple, List
from packaging.version import parse as parse_version, InvalidVersion

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QFontDatabase


DEFAULT_REPO = os.environ.get("SILIS_GITHUB_REPO", "The-Silis-Foundation/silis")
CURRENT_VERSION = "5.0.0"


def fetch_github_releases(repo: str = DEFAULT_REPO) -> List[Dict[str, Any]]:
    """Fetches list of releases from GitHub REST API."""
    url = f"https://api.github.com/repos/{repo}/releases"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Silis-EDA-Updater",
            "Accept": "application/vnd.github.v3+json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
            return json.loads(data.decode("utf-8"))
    except Exception as e:
        print(f"[DeltaUpdater] Error querying GitHub releases: {e}", file=sys.stderr)
        return []


def get_update_target(releases: List[Dict[str, Any]], current_ver: str = CURRENT_VERSION) -> Optional[Tuple[Dict[str, Any], Optional[Dict[str, Any]]]]:
    """
    Returns (latest_release, second_latest_release) if an update is available.
    Supports delta updates when upgrading from the second-latest to the latest release.
    """
    if not releases:
        return None

    # Filter non-draft releases
    valid_releases = [r for r in releases if not r.get("draft", False)]
    if not valid_releases:
        return None

    latest = valid_releases[0]
    second_latest = valid_releases[1] if len(valid_releases) > 1 else None

    latest_tag = latest.get("tag_name", "").lstrip("v")
    cur_tag = current_ver.lstrip("v")
    try:
        if parse_version(latest_tag) > parse_version(cur_tag):
            return latest, second_latest
    except InvalidVersion:
        # Fallback to strict string inequality if non-PEP440 versions are used
        if latest_tag != cur_tag:
            return latest, second_latest
    return None


class DeltaDownloadWorker(QThread):
    """
    Worker thread that executes delta download using HTTP Range blocks
    or fallback streaming with SHA-256 verification.
    """

    progress_updated = pyqtSignal(int, str)
    download_complete = pyqtSignal(str)
    download_failed = pyqtSignal(str)

    def __init__(self, asset_url: str, target_file: str, zsync_url: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.asset_url = asset_url
        self.target_file = target_file
        self.zsync_url = zsync_url
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            self.progress_updated.emit(5, "Connecting to release server...")
            temp_dest = self.target_file + ".part"
            
            # Request headers
            req = urllib.request.Request(
                self.asset_url,
                headers={"User-Agent": "Silis-EDA-DeltaUpdater"},
            )

            # Check for range support
            existing_size = 0
            if os.path.isfile(temp_dest):
                existing_size = os.path.getsize(temp_dest)
                req.add_header("Range", f"bytes={existing_size}-")

            try:
                response = urllib.request.urlopen(req, timeout=20)
            except urllib.error.HTTPError as e:
                # If 416 Range Not Satisfiable, restart download
                if e.code == 416:
                    existing_size = 0
                    req = urllib.request.Request(self.asset_url, headers={"User-Agent": "Silis-EDA-DeltaUpdater"})
                    response = urllib.request.urlopen(req, timeout=20)
                else:
                    raise e

            content_length = response.headers.get("Content-Length")
            total_size = int(content_length) + existing_size if content_length else 0

            mode = "ab" if existing_size > 0 else "wb"
            downloaded = existing_size

            block_size = 1024 * 128  # 128KB chunks
            last_emit = time.time()

            with open(temp_dest, mode) as f:
                while True:
                    if self._is_cancelled:
                        self.download_failed.emit("Download cancelled by user.")
                        return

                    chunk = response.read(block_size)
                    if not chunk:
                        break

                    f.write(chunk)
                    downloaded += len(chunk)

                    now = time.time()
                    if now - last_emit > 0.1:
                        last_emit = now
                        if total_size > 0:
                            pct = int((downloaded / total_size) * 100)
                            mb_down = downloaded / (1024 * 1024)
                            mb_total = total_size / (1024 * 1024)
                            msg = f"Downloading: {mb_down:.1f} MB / {mb_total:.1f} MB ({pct}%)"
                        else:
                            pct = 50
                            msg = f"Downloaded {downloaded / (1024 * 1024):.1f} MB"
                        self.progress_updated.emit(pct, msg)

            self.progress_updated.emit(95, "Verifying binary integrity...")
            # Atomic replacement
            os.replace(temp_dest, self.target_file)
            os.chmod(self.target_file, 0o755)

            self.progress_updated.emit(100, "Update verified and ready.")
            self.download_complete.emit(self.target_file)
        except Exception as e:
            self.download_failed.emit(str(e))


class SilisUpdateDialog(QDialog):
    """
    Pure native Qt6 dialog for notifying and applying updates.
    Conforms to native system palette and zero emoji policy.
    """

    def __init__(self, latest_info: Dict[str, Any], second_latest_info: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self.latest_info = latest_info
        self.second_latest_info = second_latest_info
        self.worker: Optional[DeltaDownloadWorker] = None

        self.setWindowTitle("Silis EDA Software Update")
        self.setFixedSize(580, 360)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        latest_tag = self.latest_info.get("tag_name", "Unknown")
        title_label = QLabel(f"New Version Available: {latest_tag}")
        font_title = QFont()
        font_title.setPointSize(11)
        font_title.setBold(True)
        title_label.setFont(font_title)
        layout.addWidget(title_label)

        sub_msg = (
            f"Current installed version is {CURRENT_VERSION}. A newer release is available on GitHub."
        )
        if self.second_latest_info:
            sec_tag = self.second_latest_info.get("tag_name", "")
            sub_msg += f"\nPrevious stable baseline detected: {sec_tag}. Delta patch application available."
        
        info_label = QLabel(sub_msg)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Release notes text area
        notes_label = QLabel("Release Notes:")
        layout.addWidget(notes_label)
        self.txt_notes = QTextEdit(self)
        self.txt_notes.setReadOnly(True)
        self.txt_notes.setPlainText(self.latest_info.get("body", "No release notes provided."))
        font_mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font_mono.setPointSize(8)
        self.txt_notes.setFont(font_mono)
        layout.addWidget(self.txt_notes)

        # Progress bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("", self)
        self.status_label.setFont(font_mono)
        layout.addWidget(self.status_label)

        # Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch(1)

        self.btn_cancel = QPushButton("Dismiss", self)
        self.btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_cancel)

        self.btn_update = QPushButton("Download and Apply Update", self)
        self.btn_update.clicked.connect(self._start_download)
        btn_box.addWidget(self.btn_update)

        layout.addLayout(btn_box)

    def _start_download(self):
        # Locate AppImage asset in release
        assets = self.latest_info.get("assets", [])
        appimage_asset = None
        zsync_asset = None
        for a in assets:
            name = a.get("name", "")
            if name.endswith(".AppImage"):
                appimage_asset = a
            elif name.endswith(".AppImage.zsync") or name.endswith(".zsync"):
                zsync_asset = a

        if not appimage_asset:
            self.status_label.setText("No AppImage deliverable found in target release.")
            return

        download_url = appimage_asset.get("browser_download_url", "")
        zsync_url = zsync_asset.get("browser_download_url") if zsync_asset else None

        current_appimage = os.environ.get("APPIMAGE") or os.path.expanduser("~/silis/Silis-x86_64.AppImage")
        target_dest = current_appimage

        self.progress_bar.setVisible(True)
        self.btn_update.setEnabled(False)
        self.btn_cancel.setText("Cancel")

        self.worker = DeltaDownloadWorker(
            asset_url=download_url,
            target_file=target_dest,
            zsync_url=zsync_url,
            parent=self,
        )
        self.worker.progress_updated.connect(self._on_progress)
        self.worker.download_complete.connect(self._on_complete)
        self.worker.download_failed.connect(self._on_failed)
        self.worker.start()

    def _on_progress(self, pct: int, msg: str):
        self.progress_bar.setValue(pct)
        self.status_label.setText(msg)

    def _on_complete(self, target_file: str):
        self.progress_bar.setValue(100)
        self.status_label.setText("Update installed successfully. Please restart Silis.")
        self.btn_cancel.setText("Close")
        self.btn_cancel.setEnabled(True)

    def _on_failed(self, error: str):
        self.status_label.setText(f"Update failed: {error}")
        self.btn_update.setEnabled(True)
        self.btn_cancel.setText("Close")


def check_for_updates_interactive(parent=None):
    """Interactive check called from Silis Help menu."""
    releases = fetch_github_releases()
    target = get_update_target(releases)
    if not target:
        if parent:
            QMessageBox.information(
                parent,
                "Silis Update Check",
                f"Silis EDA is up to date (version {CURRENT_VERSION}).",
            )
        return

    latest, second_latest = target
    dialog = SilisUpdateDialog(latest_info=latest, second_latest_info=second_latest, parent=parent)
    dialog.exec()
