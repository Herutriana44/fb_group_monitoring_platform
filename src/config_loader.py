"""
config_loader.py
----------------
Modul untuk memuat dan memvalidasi konfigurasi dari settings.yaml.

TEST:
    python config_loader.py
"""

import os
import yaml
from dataclasses import dataclass, field
from typing import Optional


CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "settings.yaml")


@dataclass
class DatabaseConfig:
    path: str = "data/monitor.db"


@dataclass
class BrowserConfig:
    headless: bool = True
    timeout: int = 30000


@dataclass
class MonitoringConfig:
    interval_seconds: int = 60
    group_ids: list = field(default_factory=list)
    keywords: list = field(default_factory=list)


@dataclass
class TelegramConfig:
    bot_token: str = ""
    chat_id: str = ""


@dataclass
class WebhookConfig:
    url: str = ""
    secret: str = ""


@dataclass
class AppConfig:
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    webhook: WebhookConfig = field(default_factory=WebhookConfig)


def load_config(path: str = CONFIG_PATH) -> AppConfig:
    """Load dan parse settings.yaml menjadi AppConfig object."""
    if not os.path.exists(path):
        print(f"[WARNING] Config file tidak ditemukan di: {path}. Menggunakan default.")
        return AppConfig()

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    db_raw = raw.get("database", {})
    browser_raw = raw.get("browser", {})
    monitoring_raw = raw.get("monitoring", {})
    telegram_raw = raw.get("telegram", {})
    webhook_raw = raw.get("webhook", {})

    config = AppConfig(
        database=DatabaseConfig(
            path=db_raw.get("path", "data/monitor.db"),
        ),
        browser=BrowserConfig(
            headless=browser_raw.get("headless", True),
            timeout=browser_raw.get("timeout", 30000),
        ),
        monitoring=MonitoringConfig(
            interval_seconds=monitoring_raw.get("interval_seconds", 60),
            group_ids=monitoring_raw.get("group_ids", []),
            keywords=monitoring_raw.get("keywords", []),
        ),
        telegram=TelegramConfig(
            bot_token=telegram_raw.get("bot_token", ""),
            chat_id=telegram_raw.get("chat_id", ""),
        ),
        webhook=WebhookConfig(
            url=webhook_raw.get("url", ""),
            secret=webhook_raw.get("secret", ""),
        ),
    )

    return config


# ── TEST STANDALONE ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    cfg = load_config()
    print("=== Config Loaded ===")
    print(f"  DB Path         : {cfg.database.path}")
    print(f"  Browser Headless: {cfg.browser.headless}")
    print(f"  Browser Timeout : {cfg.browser.timeout}ms")
    print(f"  Check Interval  : {cfg.monitoring.interval_seconds}s")
    print(f"  Group IDs       : {cfg.monitoring.group_ids}")
    print(f"  Keywords        : {cfg.monitoring.keywords}")
    print(f"  Telegram Token  : {'SET' if cfg.telegram.bot_token else 'NOT SET'}")
    print(f"  Telegram Chat ID: {'SET' if cfg.telegram.chat_id else 'NOT SET'}")
    print(f"  Webhook URL     : {'SET' if cfg.webhook.url else 'NOT SET'}")
