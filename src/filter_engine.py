"""
filter_engine.py
----------------
Modul untuk keyword filtering dan logika auto-comment.

Features:
- Whitelist keyword matching (case-insensitive)
- Blacklist keyword (exclude post yang mengandung kata tertentu)
- Hasil berupa objek FilterResult yang kaya info
- Auto-comment engine (simulasi klik + input komentar via Playwright)

TEST:
    python filter_engine.py
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PostData:
    """Representasi sebuah post Facebook."""
    post_id: str
    group_id: str
    content: str
    author: str = ""
    post_url: str = ""
    comment_count: int = 0


@dataclass
class FilterResult:
    """Hasil evaluasi filter terhadap sebuah post."""
    post: PostData
    matched: bool
    matched_keywords: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        if self.matched:
            return f"[MATCH] Post {self.post.post_id} → keywords: {self.matched_keywords}"
        return f"[SKIP]  Post {self.post.post_id} → blocked: {self.blocked_by or 'no match'}"


class FilterEngine:
    """
    Engine untuk memfilter post berdasarkan keyword.

    Args:
        keywords   : daftar kata yang harus ada (whitelist / OR logic)
        blacklist  : daftar kata yang membuat post diabaikan
        min_length : panjang minimum konten post (karakter)
    """

    def __init__(
        self,
        keywords: list[str],
        blacklist: list[str] = None,
        min_length: int = 5,
    ):
        self.keywords  = [k.lower().strip() for k in keywords]
        self.blacklist = [b.lower().strip() for b in (blacklist or [])]
        self.min_length = min_length

    def evaluate(self, post: PostData) -> FilterResult:
        """Evaluasi satu post. Return FilterResult."""
        content_lower = post.content.lower()

        # Cek panjang minimum
        if len(post.content.strip()) < self.min_length:
            return FilterResult(post=post, matched=False, blocked_by=["too_short"])

        # Cek blacklist dulu
        blocked = [b for b in self.blacklist if b in content_lower]
        if blocked:
            return FilterResult(post=post, matched=False, blocked_by=blocked)

        # Cek keyword whitelist
        matched = [k for k in self.keywords if k in content_lower]
        if matched:
            return FilterResult(post=post, matched=True, matched_keywords=matched)

        return FilterResult(post=post, matched=False)

    def filter_posts(self, posts: list[PostData]) -> list[FilterResult]:
        """Filter sekumpulan post. Return hanya yang matched=True."""
        results = [self.evaluate(p) for p in posts]
        matched = [r for r in results if r.matched]
        logger.info(
            f"Filter: {len(posts)} posts dievaluasi, {len(matched)} match, "
            f"{len(posts) - len(matched)} dilewati."
        )
        return matched


# ── Auto-Comment Engine ───────────────────────────────────────────────────────

class AutoCommentEngine:
    """
    Engine untuk auto-comment pada post lelang.
    
    Aturan bisnis (sesuai TODO):
    - User yang paling banyak komentar di post lelang → dapat barang.
    - Engine ini memosting komentar otomatis ke post yang match.
    
    Usage:
        engine = AutoCommentEngine(comment_template="Saya minat! {post_id}")
        await engine.post_comment(context, post_url, post_id="post_001")
    """

    def __init__(self, comment_template: str = "Saya berminat! 🙋"):
        self.comment_template = comment_template

    def _build_comment(self, post: Optional[PostData] = None, **kwargs) -> str:
        """Build teks komentar dari template."""
        replacements = {}
        if post:
            replacements["post_id"] = post.post_id
            replacements["author"]  = post.author
            replacements["group_id"] = post.group_id
        replacements.update(kwargs)

        comment = self.comment_template
        for key, value in replacements.items():
            comment = comment.replace(f"{{{key}}}", str(value))
        return comment

    async def post_comment(
        self,
        context,          # BrowserContext dari Playwright
        post_url: str,
        post: Optional[PostData] = None,
        comment_text: str = "",
        dry_run: bool = True,
    ) -> bool:
        """
        Post komentar ke sebuah post Facebook.

        Args:
            context     : Playwright BrowserContext (sudah authenticated)
            post_url    : URL post yang akan dikomentari
            post        : PostData opsional untuk template substitution
            comment_text: Override teks komentar (jika kosong pakai template)
            dry_run     : Jika True, tidak benar-benar klik Submit (untuk testing)
        
        Returns True jika berhasil.
        """
        text = comment_text or self._build_comment(post)
        logger.info(f"{'[DRY RUN] ' if dry_run else ''}Akan komentar di {post_url}: '{text[:60]}...'")

        if dry_run:
            logger.info("[DRY RUN] Komentar tidak dikirim (dry_run=True)")
            return True

        page = await context.new_page()
        try:
            await page.goto(post_url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_load_state("networkidle", timeout=10000)

            # Cari kotak komentar Facebook
            comment_box_selectors = [
                '[aria-label="Write a comment…"]',
                '[aria-label="Write a public comment…"]',
                '[data-lexical-editor="true"]',
                'div[role="textbox"]',
            ]

            comment_box = None
            for selector in comment_box_selectors:
                comment_box = await page.query_selector(selector)
                if comment_box:
                    break

            if not comment_box:
                logger.error("Kotak komentar tidak ditemukan.")
                return False

            await comment_box.click()
            await page.wait_for_timeout(500)
            await comment_box.fill(text)
            await page.wait_for_timeout(500)

            # Tekan Enter untuk submit
            await comment_box.press("Enter")
            await page.wait_for_timeout(2000)

            logger.info(f"Komentar berhasil diposting ke: {post_url}")
            return True

        except Exception as e:
            logger.error(f"Gagal posting komentar: {e}")
            return False
        finally:
            await page.close()


# ── TEST STANDALONE ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    print("=== FilterEngine Test ===\n")

    engine = FilterEngine(
        keywords=["lelang", "jual", "auction"],
        blacklist=["spam", "promosi berbayar"],
        min_length=10,
    )

    test_posts = [
        PostData("p001", "grp1", "Lelang sepatu Nike size 42, start 50rb!",   "UserA", "http://fb.com/p001"),
        PostData("p002", "grp1", "Jual motor bekas harga nego",                "UserB", "http://fb.com/p002"),
        PostData("p003", "grp1", "Selamat pagi semua!",                        "UserC", "http://fb.com/p003"),
        PostData("p004", "grp1", "ini spam promosi berbayar lelang palsu",     "UserD", "http://fb.com/p004"),
        PostData("p005", "grp1", "Hi",                                          "UserE", "http://fb.com/p005"),  # terlalu pendek
        PostData("p006", "grp1", "Auction jam tangan mewah mulai 100rb",       "UserF", "http://fb.com/p006"),
    ]

    results = engine.filter_posts(test_posts)

    print("Semua evaluasi:")
    all_results = [engine.evaluate(p) for p in test_posts]
    for r in all_results:
        print(f"  {r}")

    print(f"\nTotal match: {len(results)}")
    for r in results:
        print(f"  ✓ {r.post.content[:50]} | keywords: {r.matched_keywords}")

    print("\n=== AutoCommentEngine Test ===\n")
    comment_engine = AutoCommentEngine(comment_template="Saya minat! Post: {post_id} oleh {author}")
    comment = comment_engine._build_comment(test_posts[0])
    print(f"  Template result: {comment}")
    print("\n✓ Test selesai. Untuk test posting komentar, gunakan dry_run=False dengan context yang sudah authenticated.")
