"""
auth.py
-------
Entry point untuk login Facebook dan manajemen sesi.
Menggunakan SessionManager dari session.py.

USAGE:
    # Login (buka browser, isi kredensial)
    python auth.py --action login --email kamu@email.com --password passwordkamu

    # Cek status sesi
    python auth.py --action check

    # Hapus sesi (force re-login)
    python auth.py --action logout
"""

import asyncio
import argparse
import logging
import os
import sys

# Agar bisa import modul lain di folder src/
sys.path.insert(0, os.path.dirname(__file__))

from playwright.async_api import async_playwright
from session import SessionManager, SESSION_FILE
from logger_setup import setup_logging

logger = logging.getLogger(__name__)


async def do_login(email: str, password: str, headless: bool = False) -> bool:
    """Login ke Facebook dan simpan sesi."""
    sm = SessionManager()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )

        success = await sm.login(context, email, password, headless=headless)
        await browser.close()

    return success


async def do_check() -> None:
    """Cek apakah sesi aktif masih valid."""
    sm = SessionManager()

    if not os.path.exists(sm.session_file):
        print("⚠  Sesi tidak ditemukan. Silakan login terlebih dahulu.")
        return

    print(f"File sesi: {sm.session_file}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        loaded = await sm.load(context)
        if not loaded:
            print("✗  Gagal memuat sesi.")
            await browser.close()
            return

        valid = await sm.is_valid(context)
        await browser.close()

    if valid:
        print("✓  Sesi VALID — masih login.")
    else:
        print("✗  Sesi EXPIRED — silakan login ulang.")


def do_logout() -> None:
    """Hapus file sesi."""
    sm = SessionManager()
    sm.delete_session()
    print("✓  Sesi dihapus. Login ulang diperlukan.")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    setup_logging(level=logging.INFO)

    parser = argparse.ArgumentParser(description="FB Monitor — Auth Manager")
    parser.add_argument(
        "--action",
        choices=["login", "check", "logout"],
        required=True,
        help="Aksi yang akan dilakukan",
    )
    parser.add_argument("--email",    help="Email Facebook (untuk action=login)")
    parser.add_argument("--password", help="Password Facebook (untuk action=login)")
    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Jalankan browser headless (default: visible untuk login)",
    )

    args = parser.parse_args()

    if args.action == "login":
        if not args.email or not args.password:
            parser.error("--email dan --password diperlukan untuk action=login")

        print(f"Login sebagai: {args.email}")
        success = asyncio.run(do_login(args.email, args.password, headless=args.headless))
        if success:
            print(f"✓  Login berhasil! Sesi disimpan ke: {SESSION_FILE}")
        else:
            print("✗  Login gagal. Cek email/password atau tangani 2FA secara manual.")
            sys.exit(1)

    elif args.action == "check":
        asyncio.run(do_check())

    elif args.action == "logout":
        do_logout()


if __name__ == "__main__":
    main()
