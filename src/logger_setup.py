"""
logger_setup.py
---------------
Modul untuk setup logging terpusat ke file + console sekaligus.
Semua modul lain cukup import get_logger() dari sini.

TEST:
    python logger_setup.py
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "logs")
LOG_FILE = os.path.join(LOG_DIR, "monitor.log")

# Format log
CONSOLE_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
FILE_FORMAT    = "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s"
DATE_FORMAT    = "%Y-%m-%d %H:%M:%S"

_initialized = False


def setup_logging(level: int = logging.INFO, log_to_file: bool = True) -> None:
    """
    Inisialisasi root logger. Panggil sekali di entry point aplikasi.
    Modul lain tinggal pakai logging.getLogger(__name__).
    """
    global _initialized
    if _initialized:
        return
    _initialized = True

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # ── Console Handler ──────────────────────────────────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(CONSOLE_FORMAT, datefmt=DATE_FORMAT))
    root_logger.addHandler(console_handler)

    # ── File Handler (Rotating, maks 5MB × 3 file) ──────────────────────────
    if log_to_file:
        os.makedirs(LOG_DIR, exist_ok=True)
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)  # file menyimpan semua level
        file_handler.setFormatter(logging.Formatter(FILE_FORMAT, datefmt=DATE_FORMAT))
        root_logger.addHandler(file_handler)

    root_logger.info(f"Logging initialized. Log file: {LOG_FILE if log_to_file else 'disabled'}")


def get_logger(name: str) -> logging.Logger:
    """Shortcut untuk mendapatkan logger dengan nama modul."""
    return logging.getLogger(name)


# ── TEST STANDALONE ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    setup_logging(level=logging.DEBUG)
    log = get_logger("test")

    log.debug("Ini pesan DEBUG")
    log.info("Ini pesan INFO")
    log.warning("Ini pesan WARNING")
    log.error("Ini pesan ERROR")
    log.critical("Ini pesan CRITICAL")

    print(f"\nLog file tersimpan di: {os.path.abspath(LOG_FILE)}")
