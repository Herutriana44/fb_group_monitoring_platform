"""
watcher.py
----------
Watcher engine: loop utama yang memantau feed grup Facebook secara realtime.

Features:
- Loop async dengan configurable interval
- Dedup via set in-memory + database
- Rate limiting (jitter antar request)
- Otomatis load sesi dari SessionManager
- Kirim ke FilterEngine → TelegramNotifier

TEST:
    python watcher.py
    (butuh sesi aktif — jalankan auth.py dulu)
"""

import asyncio
import hashlib
import logging
import random
import os
from datetime import datetime
from typing import Optional

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


def _make_post_id(group_id: str, content: str) -> str:
    """Buat ID unik dari hash konten (karena FB tidak selalu expose post_id)."""
    raw = f"{group_id}:{content[:200]}"
    return hashlib.md5(raw.encode()).hexdigest()


class GroupWatcher:
    """
    Watcher untuk satu atau beberapa grup Facebook.

    Args:
        group_ids       : List group ID / slug
        session_file    : Path ke file sesi JSON
        interval_seconds: Jeda antar scan (detik)
        headless        : Jalankan browser headless
        db              : Instance Database (opsional, untuk persistence dedup)
        filter_engine   : Instance FilterEngine (opsional)
        notifier        : Instance TelegramNotifier / Notifier (opsional)
    """

    def __init__(
        self,
        group_ids: list[str],
        session_file: str = None,
        interval_seconds: int = 60,
        headless: bool = True,
        db=None,
        filter_engine=None,
        notifier=None,
    ):
        self.group_ids        = group_ids
        self.session_file     = session_file or os.path.join(
            os.path.dirname(__file__), "..", "data", "session.json"
        )
        self.interval_seconds = interval_seconds
        self.headless         = headless
        self.db               = db
        self.filter_engine    = filter_engine
        self.notifier         = notifier

        # Set in-memory untuk dedup selama proses berjalan
        self._seen_posts: set[str] = set()
        self._running = False

    # ── Fetch satu grup ───────────────────────────────────────────────────────

    async def _fetch_group(self, page, group_id: str) -> list[dict]:
        """
        Navigasi ke grup dan ekstrak post terbaru.
        Return list of dict: {post_id, group_id, content, author, post_url}
        """
        url = f"https://www.facebook.com/groups/{group_id}"
        logger.info(f"Fetching group: {url}")

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_load_state("networkidle", timeout=15000)

            # Tunggu artikel muncul
            try:
                await page.wait_for_selector('div[role="article"]', timeout=10000)
            except Exception:
                logger.warning(f"Tidak ada artikel ditemukan di group {group_id}")
                return []

            # Scroll sekali untuk memuat lebih banyak post
            await page.keyboard.press("End")
            await page.wait_for_timeout(2000)

            raw_posts = await page.evaluate("""() => {
                const articles = document.querySelectorAll('div[role="article"]');
                const results = [];
                
                articles.forEach(article => {
                    // Coba ambil teks utama post
                    const textEl = article.querySelector('[data-ad-comet-preview="message"]')
                                || article.querySelector('[data-ad-preview="message"]')
                                || article;
                    
                    // Coba ambil nama author
                    const authorEl = article.querySelector('a[aria-label]')
                                  || article.querySelector('h3 a')
                                  || article.querySelector('strong a');
                    
                    // Coba ambil link post
                    const linkEl = article.querySelector('a[href*="/posts/"]')
                                || article.querySelector('a[href*="story_fbid"]');
                    
                    const content = textEl ? textEl.innerText.trim() : '';
                    const author  = authorEl ? authorEl.innerText.trim() : '';
                    const postUrl = linkEl ? linkEl.href : '';
                    
                    if (content.length > 10) {
                        results.push({ content, author, post_url: postUrl });
                    }
                });
                
                return results;
            }""")

            posts = []
            for raw in raw_posts:
                post_id = _make_post_id(group_id, raw["content"])
                posts.append({
                    "post_id":  post_id,
                    "group_id": group_id,
                    "content":  raw["content"],
                    "author":   raw.get("author", ""),
                    "post_url": raw.get("post_url", ""),
                })

            logger.info(f"Group {group_id}: {len(posts)} post diekstrak.")
            return posts

        except Exception as e:
            logger.error(f"Error saat fetch group {group_id}: {e}")
            return []

    # ── Proses satu siklus ────────────────────────────────────────────────────

    async def _process_new_posts(self, posts: list[dict]) -> int:
        """
        Filter post baru (belum pernah dilihat), jalankan filter engine,
        dan kirim notifikasi. Return jumlah post baru yang diproses.
        """
        new_count = 0

        for post_data in posts:
            pid = post_data["post_id"]

            # Skip jika sudah pernah diproses (in-memory dedup)
            if pid in self._seen_posts:
                continue

            # Skip jika ada di database (persistence dedup)
            if self.db and await self.db.post_exists(pid):
                self._seen_posts.add(pid)
                continue

            self._seen_posts.add(pid)
            new_count += 1

            logger.debug(f"Post baru: {pid} | {post_data['content'][:80]}...")

            # Jalankan filter engine
            if self.filter_engine:
                from filter_engine import PostData
                post_obj = PostData(
                    post_id=pid,
                    group_id=post_data["group_id"],
                    content=post_data["content"],
                    author=post_data.get("author", ""),
                    post_url=post_data.get("post_url", ""),
                )
                result = self.filter_engine.evaluate(post_obj)

                if result.matched:
                    logger.info(f"MATCH: {result}")

                    # Simpan ke DB
                    if self.db:
                        await self.db.save_post(
                            post_id=pid,
                            group_id=post_data["group_id"],
                            content=post_data["content"],
                            author=post_data.get("author", ""),
                            post_url=post_data.get("post_url", ""),
                            notified=False,
                        )

                    # Kirim notifikasi
                    if self.notifier:
                        try:
                            if hasattr(self.notifier, "send_post_alert"):
                                # TelegramNotifier
                                await self.notifier.send_post_alert(
                                    post_content=post_data["content"],
                                    post_url=post_data.get("post_url", ""),
                                    group_id=post_data["group_id"],
                                    matched_keywords=result.matched_keywords,
                                    author=post_data.get("author", ""),
                                )
                            else:
                                # Notifier lama (sync)
                                self.notifier.notify(
                                    f"Match: {post_data['content'][:100]}"
                                )
                        except Exception as e:
                            logger.error(f"Gagal kirim notifikasi: {e}")

                        if self.db:
                            await self.db.mark_notified(pid)
            else:
                # Tidak ada filter engine — log saja semua post baru
                logger.info(f"Post baru (no filter): {post_data['content'][:80]}")

        return new_count

    # ── Main Loop ─────────────────────────────────────────────────────────────

    async def run(self) -> None:
        """
        Jalankan watcher loop. Berhenti jika di-cancel atau KeyboardInterrupt.
        """
        from session import SessionManager

        self._running = True
        sm = SessionManager(session_file=self.session_file)

        logger.info(
            f"Watcher dimulai. Groups: {self.group_ids}, "
            f"Interval: {self.interval_seconds}s, Headless: {self.headless}"
        )

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            )

            # Load sesi
            loaded = await sm.load(context)
            if not loaded:
                logger.warning("Sesi tidak ditemukan. Beberapa fitur mungkin tidak berfungsi.")

            page = await context.new_page()

            try:
                while self._running:
                    cycle_start = datetime.now()
                    logger.info(f"=== Scan dimulai [{cycle_start.strftime('%H:%M:%S')}] ===")

                    total_new = 0
                    for group_id in self.group_ids:
                        posts = await self._fetch_group(page, group_id)
                        new = await self._process_new_posts(posts)
                        total_new += new

                        # Jitter antar grup (1–3 detik)
                        if len(self.group_ids) > 1:
                            await asyncio.sleep(random.uniform(1, 3))

                    elapsed = (datetime.now() - cycle_start).seconds
                    logger.info(
                        f"=== Scan selesai. {total_new} post baru. "
                        f"Elapsed: {elapsed}s. Tidur {self.interval_seconds}s... ==="
                    )

                    # Jitter pada interval (±10%)
                    jitter = random.uniform(-0.1, 0.1) * self.interval_seconds
                    await asyncio.sleep(self.interval_seconds + jitter)

            except asyncio.CancelledError:
                logger.info("Watcher di-cancel.")
            except KeyboardInterrupt:
                logger.info("Watcher dihentikan (Ctrl+C).")
            finally:
                self._running = False
                await browser.close()
                logger.info("Browser ditutup. Watcher berhenti.")

    def stop(self) -> None:
        """Stop watcher (atur flag)."""
        self._running = False


# ── TEST STANDALONE ──────────────────────────────────────────────────────────
async def _test():
    """Test 1 siklus fetch tanpa filter/notifier."""
    import sys
    sys.path.insert(0, os.path.dirname(__file__))

    from session import SessionManager

    session_file = os.path.join(os.path.dirname(__file__), "..", "data", "session.json")

    if not os.path.exists(session_file):
        print("⚠  Sesi tidak ditemukan. Jalankan auth.py login dulu.")
        print("   python auth.py --action login --email <email> --password <pass>")
        return

    # Ganti dengan group ID yang kamu punya akses
    TEST_GROUP_ID = "GANTI_DENGAN_GROUP_ID_KAMU"

    watcher = GroupWatcher(
        group_ids=[TEST_GROUP_ID],
        session_file=session_file,
        headless=True,
    )

    print(f"Testing fetch 1 siklus untuk group: {TEST_GROUP_ID}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        sm = SessionManager(session_file=session_file)
        await sm.load(context)

        page = await context.new_page()
        posts = await watcher._fetch_group(page, TEST_GROUP_ID)

        await browser.close()

    print(f"\n=== Hasil Fetch ===")
    print(f"Total post ditemukan: {len(posts)}")
    for i, p in enumerate(posts[:3], 1):
        print(f"\n[Post {i}]")
        print(f"  ID     : {p['post_id']}")
        print(f"  Author : {p['author']}")
        print(f"  Content: {p['content'][:100]}...")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    asyncio.run(_test())
