"""
session.py
----------
Modul session management yang lebih robust:
- Simpan/load cookies dari file JSON maupun database
- Cek validitas sesi (apakah masih login)
- Auto-refresh / trigger re-login jika expired

TEST:
    python session.py  (akan membuka browser — pastikan sudah install playwright)
"""

import asyncio
import json
import os
import logging
from datetime import datetime
from playwright.async_api import async_playwright, BrowserContext, Page

logger = logging.getLogger(__name__)

SESSION_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "session.json")
FB_HOME      = "https://www.facebook.com/"
FB_LOGIN     = "https://www.facebook.com/login"


class SessionManager:
    """
    Mengelola sesi Facebook menggunakan cookies Playwright.
    
    Usage:
        sm = SessionManager()
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            
            await sm.load(context)
            
            if not await sm.is_valid(context):
                await sm.login(context, email, password)
    """

    def __init__(self, session_file: str = SESSION_FILE):
        self.session_file = session_file
        os.makedirs(os.path.dirname(os.path.abspath(session_file)), exist_ok=True)

    # ── Simpan & Load ────────────────────────────────────────────────────────

    async def save(self, context: BrowserContext) -> None:
        """Simpan cookies aktif ke file JSON."""
        cookies = await context.cookies()
        payload = {
            "saved_at": datetime.now().isoformat(),
            "cookies": cookies,
        }
        with open(self.session_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        logger.info(f"Session disimpan ke: {self.session_file} ({len(cookies)} cookies)")

    async def load(self, context: BrowserContext) -> bool:
        """
        Muat cookies dari file ke context browser.
        Return True jika berhasil, False jika file tidak ada.
        """
        if not os.path.exists(self.session_file):
            logger.warning("File sesi tidak ditemukan.")
            return False

        with open(self.session_file, "r", encoding="utf-8") as f:
            payload = json.load(f)

        cookies = payload.get("cookies", [])
        if not cookies:
            logger.warning("File sesi kosong / tidak ada cookies.")
            return False

        await context.add_cookies(cookies)
        saved_at = payload.get("saved_at", "unknown")
        logger.info(f"Session dimuat dari file (disimpan: {saved_at}, {len(cookies)} cookies)")
        return True

    # ── Validasi ─────────────────────────────────────────────────────────────

    async def is_valid(self, context: BrowserContext) -> bool:
        """
        Cek apakah sesi masih valid dengan membuka Facebook dan melihat
        apakah kita masih login (tidak diredirect ke halaman login).
        """
        page = await context.new_page()
        try:
            await page.goto(FB_HOME, wait_until="domcontentloaded", timeout=15000)
            current_url = page.url

            # Jika diarahkan ke /login atau /checkpoint, sesi expired
            if "/login" in current_url or "/checkpoint" in current_url:
                logger.warning(f"Sesi tidak valid, redirect ke: {current_url}")
                return False

            # Coba cek keberadaan elemen yang hanya muncul saat logged in
            profile_icon = await page.query_selector('[aria-label="Your profile"]')
            nav_bar      = await page.query_selector('[data-pagelet="LeftRail"]')

            if profile_icon or nav_bar:
                logger.info("Sesi valid — user masih login.")
                return True
            else:
                # Fallback: kalau tidak redirect dan tidak ada login form, anggap valid
                login_form = await page.query_selector('input[name="email"]')
                if login_form:
                    logger.warning("Sesi tidak valid — halaman login terdeteksi.")
                    return False
                logger.info("Sesi kemungkinan valid (tidak ada indikasi logout).")
                return True

        except Exception as e:
            logger.error(f"Error saat validasi sesi: {e}")
            return False
        finally:
            await page.close()

    # ── Login ────────────────────────────────────────────────────────────────

    async def login(
        self,
        context: BrowserContext,
        email: str,
        password: str,
        headless: bool = False,
    ) -> bool:
        """
        Login ke Facebook dan simpan cookies setelah berhasil.
        Return True jika login berhasil.
        """
        page = await context.new_page()
        try:
            logger.info("Membuka halaman login Facebook...")
            await page.goto(FB_LOGIN, wait_until="domcontentloaded", timeout=15000)

            await page.fill('input[name="email"]', email)
            await page.fill('input[name="pass"]', password)
            await page.click('button[name="login"]')

            # Tunggu navigasi setelah klik login
            await page.wait_for_load_state("networkidle", timeout=20000)

            current_url = page.url
            if "/login" in current_url or "login_attempt" in current_url:
                logger.error("Login gagal — masih di halaman login.")
                return False

            if "/checkpoint" in current_url or "/two_step_verification" in current_url:
                logger.warning("Akun butuh verifikasi 2FA — selesaikan secara manual lalu tekan Enter...")
                input("Tekan Enter setelah verifikasi selesai di browser...")
                await page.wait_for_load_state("networkidle", timeout=30000)

            logger.info(f"Login berhasil! URL sekarang: {current_url}")
            await self.save(context)
            return True

        except Exception as e:
            logger.error(f"Error saat login: {e}")
            return False
        finally:
            await page.close()

    # ── Delete ───────────────────────────────────────────────────────────────

    def delete_session(self) -> None:
        """Hapus file sesi (untuk force re-login)."""
        if os.path.exists(self.session_file):
            os.remove(self.session_file)
            logger.info("File sesi dihapus.")


# ── Fungsi helper untuk digunakan modul lain ─────────────────────────────────

async def get_authenticated_context(
    playwright,
    email: str = "",
    password: str = "",
    headless: bool = True,
    session_file: str = SESSION_FILE,
):
    """
    Helper: buat browser context yang sudah authenticated.
    Jika sesi ada dan valid → pakai langsung.
    Jika tidak → login dulu (butuh email & password).
    
    Returns: (browser, context) — jangan lupa close setelah selesai.
    """
    sm = SessionManager(session_file=session_file)
    browser = await playwright.chromium.launch(headless=headless)
    context = await browser.new_context()

    # Coba load sesi
    loaded = await sm.load(context)

    if loaded:
        valid = await sm.is_valid(context)
        if valid:
            logger.info("Menggunakan sesi yang sudah ada.")
            return browser, context

        logger.warning("Sesi expired, melakukan re-login...")
        await context.clear_cookies()

    if not email or not password:
        raise ValueError("Sesi tidak valid dan tidak ada kredensial untuk login ulang.")

    success = await sm.login(context, email, password, headless=headless)
    if not success:
        raise RuntimeError("Login gagal.")

    return browser, context


# ── TEST STANDALONE ──────────────────────────────────────────────────────────
async def _test():
    """
    Test: cek apakah file sesi ada dan valid.
    Jika tidak ada, tampilkan instruksi.
    """
    sm = SessionManager()

    if not os.path.exists(sm.session_file):
        print("⚠  File sesi tidak ditemukan.")
        print("   Jalankan dulu: python auth.py login --email <email> --password <pass>")
        return

    print(f"File sesi ditemukan: {sm.session_file}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        loaded = await sm.load(context)
        print(f"Load session: {loaded}")

        if loaded:
            valid = await sm.is_valid(context)
            print(f"Session valid: {valid}")

        await browser.close()


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    asyncio.run(_test())
