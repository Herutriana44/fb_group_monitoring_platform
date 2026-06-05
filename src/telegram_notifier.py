"""
telegram_notifier.py
--------------------
Modul notifikasi via Telegram Bot API.

Features:
- Kirim pesan teks biasa
- Kirim pesan dengan format HTML/Markdown
- Kirim notifikasi post match dengan format rapi
- Webhook mode (opsional, untuk menerima reply dari Telegram)
- Retry otomatis jika request gagal

Setup:
1. Buat bot di @BotFather → dapat bot_token
2. Kirim /start ke bot kamu, lalu buka:
   https://api.telegram.org/bot<TOKEN>/getUpdates
   untuk mendapatkan chat_id

TEST:
    python telegram_notifier.py
    (butuh bot_token dan chat_id di config/settings.yaml)
"""

import asyncio
import aiohttp
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


class TelegramNotifier:
    """
    Kirim notifikasi ke Telegram via Bot API.

    Args:
        bot_token : Token dari @BotFather
        chat_id   : Chat ID tujuan (bisa user, grup, atau channel)
        max_retries: Jumlah retry jika request gagal
    """

    def __init__(self, bot_token: str, chat_id: str, max_retries: int = 3):
        if not bot_token or not chat_id:
            raise ValueError("bot_token dan chat_id harus diisi.")
        self.bot_token  = bot_token
        self.chat_id    = chat_id
        self.max_retries = max_retries
        self._base_url  = f"https://api.telegram.org/bot{bot_token}"

    def _url(self, method: str) -> str:
        return f"{self._base_url}/{method}"

    async def send_message(
        self,
        text: str,
        parse_mode: str = "HTML",
        disable_notification: bool = False,
    ) -> bool:
        """
        Kirim pesan teks ke chat_id.
        Return True jika berhasil.
        """
        payload = {
            "chat_id": self.chat_id,
            "text": text[:4096],  # Telegram max 4096 char
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
            "disable_notification": disable_notification,
        }

        for attempt in range(1, self.max_retries + 1):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self._url("sendMessage"),
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as resp:
                        data = await resp.json()
                        if data.get("ok"):
                            logger.info(f"Telegram: pesan terkirim (attempt {attempt})")
                            return True
                        else:
                            logger.warning(
                                f"Telegram API error (attempt {attempt}): {data.get('description')}"
                            )
            except aiohttp.ClientError as e:
                logger.error(f"Telegram request gagal (attempt {attempt}): {e}")

            if attempt < self.max_retries:
                await asyncio.sleep(2 ** attempt)  # exponential backoff

        logger.error("Telegram: gagal kirim pesan setelah semua retry.")
        return False

    async def send_post_alert(
        self,
        post_content: str,
        post_url: str = "",
        group_id: str = "",
        matched_keywords: list[str] = None,
        author: str = "",
    ) -> bool:
        """
        Kirim alert terformat untuk post yang match keyword.
        """
        keywords_str = ", ".join(f"<code>{k}</code>" for k in (matched_keywords or []))
        url_line     = f'\n🔗 <a href="{post_url}">Lihat Post</a>' if post_url else ""
        author_line  = f"\n👤 Author: {author}" if author else ""
        group_line   = f"\n📌 Group: {group_id}" if group_id else ""

        # Truncate konten post
        preview = post_content[:300] + "..." if len(post_content) > 300 else post_content

        message = (
            "🚨 <b>POST BARU TERDETEKSI</b>\n"
            f"{'─' * 30}\n"
            f"{preview}"
            f"{author_line}"
            f"{group_line}"
            f"\n🏷️  Keywords: {keywords_str or '-'}"
            f"{url_line}"
        )

        return await self.send_message(message)

    async def send_system_alert(self, level: str, message: str) -> bool:
        """
        Kirim alert sistem (error, warning, info).
        level: 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL'
        """
        icons = {
            "INFO":     "ℹ️",
            "WARNING":  "⚠️",
            "ERROR":    "❌",
            "CRITICAL": "🔥",
        }
        icon = icons.get(level.upper(), "📢")
        text = f"{icon} <b>[{level.upper()}]</b>\n{message}"
        return await self.send_message(text, disable_notification=(level == "INFO"))

    async def test_connection(self) -> bool:
        """
        Cek apakah bot_token valid menggunakan getMe API.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self._url("getMe"),
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    data = await resp.json()
                    if data.get("ok"):
                        bot_info = data.get("result", {})
                        logger.info(
                            f"Bot aktif: @{bot_info.get('username')} "
                            f"({bot_info.get('first_name')})"
                        )
                        return True
                    logger.error(f"getMe gagal: {data.get('description')}")
                    return False
        except Exception as e:
            logger.error(f"Koneksi Telegram gagal: {e}")
            return False


# ── Webhook Handler (sederhana, bukan full server) ────────────────────────────

async def receive_updates(bot_token: str, offset: int = 0) -> tuple[list, int]:
    """
    Ambil update terbaru dari Telegram (long-polling style).
    Return: (list_of_updates, next_offset)
    """
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    params = {"offset": offset, "timeout": 30}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=35)) as resp:
                data = await resp.json()
                if not data.get("ok"):
                    return [], offset
                updates = data.get("result", [])
                if updates:
                    next_offset = updates[-1]["update_id"] + 1
                else:
                    next_offset = offset
                return updates, next_offset
    except Exception as e:
        logger.error(f"Error saat getUpdates: {e}")
        return [], offset


# ── TEST STANDALONE ──────────────────────────────────────────────────────────
async def _test():
    """Test koneksi dan kirim pesan ke Telegram."""
    # Load config
    import sys
    import yaml
    sys.path.insert(0, os.path.dirname(__file__))

    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "settings.yaml")
    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)

    bot_token = cfg.get("telegram", {}).get("bot_token", "")
    chat_id   = cfg.get("telegram", {}).get("chat_id", "")

    if not bot_token or not chat_id:
        print("⚠  bot_token atau chat_id belum diisi di config/settings.yaml")
        print("   Format:\n   telegram:\n     bot_token: '123456:ABC...'\n     chat_id: '987654321'")
        return

    notifier = TelegramNotifier(bot_token=bot_token, chat_id=chat_id)

    print("Testing koneksi bot...")
    ok = await notifier.test_connection()
    print(f"  Koneksi: {'✓ OK' if ok else '✗ GAGAL'}")

    if ok:
        print("Mengirim pesan test...")
        sent = await notifier.send_message("✅ <b>Test notifikasi FB Monitor berhasil!</b>")
        print(f"  Kirim pesan: {'✓ OK' if sent else '✗ GAGAL'}")

        print("Mengirim post alert test...")
        sent2 = await notifier.send_post_alert(
            post_content="Lelang sepatu Nike Air Max 42, kondisi 9/10, start 200rb no reserve!",
            post_url="https://facebook.com/groups/contoh/posts/123",
            group_id="lelang_barang_bekas",
            matched_keywords=["lelang", "nike"],
            author="Budi Santoso",
        )
        print(f"  Kirim post alert: {'✓ OK' if sent2 else '✗ GAGAL'}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    asyncio.run(_test())
