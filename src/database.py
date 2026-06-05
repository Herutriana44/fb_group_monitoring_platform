"""
database.py
-----------
Modul untuk semua operasi database SQLite.
Tabel: posts, keywords, logs, sessions

TEST:
    python database.py
"""

import asyncio
import aiosqlite
import os
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "monitor.db")


class Database:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

    async def init(self) -> None:
        """Buat semua tabel jika belum ada."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS posts (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id     TEXT    UNIQUE NOT NULL,
                    group_id    TEXT    NOT NULL,
                    content     TEXT,
                    author      TEXT,
                    post_url    TEXT,
                    detected_at TEXT    NOT NULL,
                    notified    INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS keywords (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword    TEXT UNIQUE NOT NULL,
                    active     INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS logs (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    level      TEXT NOT NULL,
                    message    TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    account    TEXT UNIQUE NOT NULL,
                    cookies    TEXT,
                    updated_at TEXT NOT NULL,
                    valid      INTEGER DEFAULT 1
                );
            """)
            await db.commit()
        logger.info(f"Database initialized: {self.db_path}")

    # ── POSTS ────────────────────────────────────────────────────────────────

    async def post_exists(self, post_id: str) -> bool:
        """Cek apakah post sudah pernah diproses (untuk dedup)."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT 1 FROM posts WHERE post_id = ?", (post_id,)
            ) as cursor:
                return await cursor.fetchone() is not None

    async def save_post(
        self,
        post_id: str,
        group_id: str,
        content: str,
        author: str = "",
        post_url: str = "",
        notified: bool = False,
    ) -> bool:
        """Simpan post baru. Return True jika berhasil, False jika duplikat."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """INSERT INTO posts (post_id, group_id, content, author, post_url, detected_at, notified)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        post_id,
                        group_id,
                        content,
                        author,
                        post_url,
                        datetime.now().isoformat(),
                        int(notified),
                    ),
                )
                await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False  # duplikat

    async def mark_notified(self, post_id: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE posts SET notified = 1 WHERE post_id = ?", (post_id,)
            )
            await db.commit()

    async def get_recent_posts(self, limit: int = 20) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM posts ORDER BY detected_at DESC LIMIT ?", (limit,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    # ── KEYWORDS ─────────────────────────────────────────────────────────────

    async def add_keyword(self, keyword: str) -> bool:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT INTO keywords (keyword, created_at) VALUES (?, ?)",
                    (keyword.lower().strip(), datetime.now().isoformat()),
                )
                await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False  # sudah ada

    async def get_active_keywords(self) -> list[str]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT keyword FROM keywords WHERE active = 1"
            ) as cursor:
                rows = await cursor.fetchall()
                return [r[0] for r in rows]

    async def delete_keyword(self, keyword: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM keywords WHERE keyword = ?", (keyword.lower().strip(),)
            )
            await db.commit()

    # ── LOGS ─────────────────────────────────────────────────────────────────

    async def write_log(self, level: str, message: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO logs (level, message, created_at) VALUES (?, ?, ?)",
                (level, message, datetime.now().isoformat()),
            )
            await db.commit()

    async def get_logs(self, limit: int = 50, level: Optional[str] = None) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if level:
                cursor_query = "SELECT * FROM logs WHERE level = ? ORDER BY created_at DESC LIMIT ?"
                params = (level.upper(), limit)
            else:
                cursor_query = "SELECT * FROM logs ORDER BY created_at DESC LIMIT ?"
                params = (limit,)
            async with db.execute(cursor_query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    # ── SESSIONS ─────────────────────────────────────────────────────────────

    async def save_session(self, account: str, cookies_json: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO sessions (account, cookies, updated_at, valid)
                   VALUES (?, ?, ?, 1)
                   ON CONFLICT(account) DO UPDATE SET
                       cookies    = excluded.cookies,
                       updated_at = excluded.updated_at,
                       valid      = 1""",
                (account, cookies_json, datetime.now().isoformat()),
            )
            await db.commit()

    async def get_session(self, account: str) -> Optional[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM sessions WHERE account = ? AND valid = 1", (account,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def invalidate_session(self, account: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE sessions SET valid = 0 WHERE account = ?", (account,)
            )
            await db.commit()

    # ── STATS ─────────────────────────────────────────────────────────────────

    async def get_stats(self) -> dict:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM posts") as c:
                total_posts = (await c.fetchone())[0]
            async with db.execute("SELECT COUNT(*) FROM posts WHERE notified = 1") as c:
                notified_posts = (await c.fetchone())[0]
            async with db.execute("SELECT COUNT(*) FROM keywords WHERE active = 1") as c:
                active_keywords = (await c.fetchone())[0]
        return {
            "total_posts_detected": total_posts,
            "total_notified": notified_posts,
            "active_keywords": active_keywords,
        }


# ── TEST STANDALONE ──────────────────────────────────────────────────────────
async def _test():
    db = Database("data/test_monitor.db")
    await db.init()

    # Test keywords
    print("=== Keywords ===")
    await db.add_keyword("lelang")
    await db.add_keyword("jual")
    await db.add_keyword("lelang")  # duplikat, harusnya False
    keywords = await db.get_active_keywords()
    print(f"  Active keywords: {keywords}")

    # Test posts
    print("\n=== Posts ===")
    saved = await db.save_post("post_001", "group_123", "Lelang sepatu murah!", "UserA", "http://fb.com/1")
    print(f"  Post saved: {saved}")
    dup = await db.save_post("post_001", "group_123", "Duplikat post", "UserA")
    print(f"  Duplicate blocked: {not dup}")
    exists = await db.post_exists("post_001")
    print(f"  post_exists('post_001'): {exists}")

    await db.mark_notified("post_001")
    posts = await db.get_recent_posts()
    print(f"  Recent posts count: {len(posts)}, notified: {posts[0]['notified']}")

    # Test logs
    print("\n=== Logs ===")
    await db.write_log("INFO", "Monitoring started")
    await db.write_log("ERROR", "Connection timeout")
    logs = await db.get_logs(limit=5)
    print(f"  Logs saved: {len(logs)}")

    # Test sessions
    print("\n=== Sessions ===")
    await db.save_session("user@example.com", '{"cookies": []}')
    session = await db.get_session("user@example.com")
    print(f"  Session found: {session is not None}")
    await db.invalidate_session("user@example.com")
    session_after = await db.get_session("user@example.com")
    print(f"  Session after invalidate: {session_after}")

    # Test stats
    print("\n=== Stats ===")
    stats = await db.get_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")

    # Cleanup test db
    os.remove("data/test_monitor.db")
    print("\n✓ Semua test passed.")


if __name__ == "__main__":
    asyncio.run(_test())
