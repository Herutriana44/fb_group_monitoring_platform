import asyncio
from playwright.async_api import async_playwright
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class GroupCollector:
    def __init__(self, group_id):
        self.group_id = group_id
        self.base_url = f"https://www.facebook.com/groups/{group_id}"

    async def fetch_feed(self):
        logger.info(f"Navigating to group: {self.base_url}")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            # TODO: Load cookies from auth session
            await page.goto(self.base_url)
            await page.wait_for_load_state("networkidle")
            
            # Simple content extraction example
            posts = await page.eval_on_selector_all('div[role="article"]', '(elements) => elements.map(el => el.innerText)')
            
            await browser.close()
            return posts


    async def new_fetch_feed(self):
        logger.info(f"Navigating to group: {self.base_url}")
        
        async with async_playwright() as p:
            # headless=True aman digunakan jika cookies valid
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            
            # Masuk ke URL target
            await page.goto(self.base_url)
            await page.wait_for_load_state("networkidle")
            
            # --- REVISI 2: Pastikan selector artikel sudah muncul di layar ---
            # Menghindari selector kosong karena jeda render javascript halaman
            article_selector = 'div[role="article"]'
            try:
                await page.wait_for_selector(article_selector, timeout=10000)
            except Exception as e:
                logger.error(f"Timeout waiting for articles: {e}")
                await browser.close()
                return []

            # Metode ini mengambil text dari elemen artikel yang paling pertama dimuat (paling atas/terbaru)
            posts = await page.eval_on_selector_all(
                article_selector, 
                '(elements) => elements.map(el => el.innerText.trim()).filter(text => text.length > 0)'
            )
            
            await browser.close()
            
            # Mengembalikan list posts. Index [0] adalah yang paling baru (paling atas di feed)
            logger.info(f"Successfully fetched {len(posts)} posts.")
            return posts

    async def fetch_and_sort_comments(self, post_url: str, sort_by: str = "newest"):
        """
        Mengambil semua komentar dari postingan tertentu dan mengurutkannya berdasarkan waktu (hingga milidetik).
        
        :param post_url: URL lengkap dari postingan yang ingin di-scrape.
        :param sort_by: 'newest' untuk terbaru ke terlama, 'oldest' untuk terlama ke terbaru.
        """
        if sort_by not in ["newest", "oldest"]:
            raise ValueError("Parameter sort_by harus berisikan 'newest' atau 'oldest'")

        logger.info(f"Navigating to post: {post_url}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            
            # Load cookies agar bisa melihat komentar lengkap
            cookies_path = 'data/cookies.json'
            if os.path.exists(cookies_path):
                with open(cookies_path, 'r') as f:
                    await context.add_cookies(json.load(f))
            
            page = await context.new_page()
            await page.goto(post_url)
            await page.wait_for_load_state("networkidle")
            
            # --- PROSES SCROLL / LOAD ALL COMMENTS ---
            # Beberapa platform butuh klik "Lihat komentar lainnya" atau scroll down.
            # Kode ini mensimulasikan scroll ke bawah beberapa kali untuk memuat semua komentar dinamis.
            for _ in range(5):  # Sesuaikan angka range ini dengan banyaknya komentar
                await page.keyboard.press("End")
                await page.wait_for_timeout(1500) # Tunggu render konten baru
                
                # OPSIONAL: Jika ada tombol "Load more comments", klik otomatis di sini
                # load_more_btn = await page.query_selector('text="Lihat komentar lainnya"')
                # if load_more_btn: await load_more_btn.click()

            # --- EKSTRAKSI DATA KOMENTAR ---
            # Kita berasumsi struktur HTML komentar memiliki kontainer utama, elemen teks, dan elemen waktu.
            # Catatan: Sesuaikan selector 'div[data-comment]' dan 'time' dengan platform target Anda.
            raw_comments = await page.evaluate('''() => {
                const commentNodes = document.querySelectorAll('div[role="comment"]', 'div[data-comment]');
                const data = [];
                
                commentNodes.forEach(node => {
                    const textEl = node.querySelector('.comment-text-selector') || node; 
                    // Mencari tag <time> atau elemen yang menyimpan atribut waktu (ISO String / Unix Timestamp)
                    const timeEl = node.querySelector('time');
                    
                    let timestamp = null;
                    if (timeEl) {
                        // Mengambil dari atribut datetime jika ada (biasanya format ISO: 2026-05-31T20:47:01.123Z)
                        timestamp = timeEl.getAttribute('datetime') || timeEl.getAttribute('data-time') || timeEl.innerText;
                    }
                    
                    data.push({
                        text: textEl.innerText.trim(),
                        raw_time: timestamp
                    });
                });
                return data;
            }''')
            
            await browser.close()
            
            # --- PARSING & SORTING DI PYTHON ---
            parsed_comments = []
            for c in raw_comments:
                if not c['text'] or not c['raw_time']:
                    continue
                    
                try:
                    # Konversi string waktu menjadi objek datetime Python untuk sorting akurat.
                    # Contoh jika formatnya ISO 8601 (mengandung milidetik/Z): "2026-05-31T20:47:01.123Z"
                    # Suffix "Z" dihilangkan atau diganti agar bisa dibaca oleh fromisoformat
                    clean_time_str = c['raw_time'].replace('Z', '+00:00')
                    dt_object = datetime.fromisoformat(clean_time_str)
                except Exception:
                    # Fallback: Jika gagal parsing milidetik (misal format teks biasa), gunakan waktu saat ini agar tidak error
                    logger.warning(f"Gagal parsing format waktu: {c['raw_time']}. Menggunakan fallback.")
                    dt_object = datetime.now()
                    
                parsed_comments.append({
                    "text": c['text'],
                    "datetime": dt_object,
                    "timestamp_str": c['raw_time']
                })
                
            # Proses Pengurutan (Sorting) berdasarkan objek datetime
            is_reverse = True if sort_by == "newest" else False
            sorted_comments = sorted(parsed_comments, key=lambda x: x['datetime'], reverse=is_reverse)
            
            # Kembalikan hasil akhir (Datetime dikonversi kembali ke string agar mudah dibaca/di-save ke JSON)
            final_result = [
                {"text": item["text"], "time": item["timestamp_str"]} 
                for item in sorted_comments
            ]
            
            logger.info(f"Berhasil mengambil & mengurutkan {len(final_result)} komentar secara {sort_by}.")
            return final_result