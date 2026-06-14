import sqlite3
import os
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict
from dataclasses import dataclass

DB_DIR = Path.home() / ".tgm_drive"
DB_FILE = DB_DIR / "files.db"


@dataclass
class FileRecord:
    id: int
    message_id: int
    filename: str
    size: int
    mime_type: str
    upload_date: str
    tags: str
    local_path: Optional[str]
    telegram_path: Optional[str]
    channel_id: int
    original_filename: str = ""


class Database:
    def __init__(self, db_path: str = None):
        self.db_path = str(db_path or DB_FILE)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER UNIQUE,
                    filename TEXT NOT NULL,
                    size INTEGER DEFAULT 0,
                    mime_type TEXT DEFAULT '',
                    upload_date TEXT DEFAULT '',
                    tags TEXT DEFAULT '',
                    local_path TEXT,
                    telegram_path TEXT,
                    channel_id INTEGER DEFAULT 0
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_filename ON files(filename)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tags ON files(tags)
                """
            )
            # Migration: add channel_id if missing
            cols = [row[1] for row in conn.execute("PRAGMA table_info(files)").fetchall()]
            if 'channel_id' not in cols:
                conn.execute("ALTER TABLE files ADD COLUMN channel_id INTEGER DEFAULT 0")
            # Migration: add original_filename if missing
            if 'original_filename' not in cols:
                conn.execute("ALTER TABLE files ADD COLUMN original_filename TEXT DEFAULT ''")
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_channel_id ON files(channel_id)
                """
            )
        # Channels table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS channels (
                channel_id INTEGER PRIMARY KEY,
                channel_name TEXT NOT NULL
            )
            """
        )
        # Favorite channels table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS favorite_channels (
                channel_id INTEGER PRIMARY KEY,
                channel_name TEXT NOT NULL,
                display_name TEXT NOT NULL,
                sort_order INTEGER DEFAULT 0
            )
            """
        )
        # Tags table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tags (
                tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tag_name TEXT NOT NULL UNIQUE,
                sort_order INTEGER DEFAULT 0
            )
            """
        )
        conn.commit()

    def insert_file(
        self,
        message_id: int,
        filename: str,
        size: int,
        mime_type: str,
        tags: str = "",
        local_path: Optional[str] = None,
        telegram_path: Optional[str] = None,
        channel_id: int = 0,
        original_filename: str = "",
    ) -> int:
        upload_date = datetime.now().isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO files (message_id, filename, size, mime_type, upload_date, tags, local_path, telegram_path, channel_id, original_filename)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(message_id) DO UPDATE SET
                    filename=excluded.filename,
                    size=excluded.size,
                    mime_type=excluded.mime_type,
                    upload_date=excluded.upload_date,
                    tags=CASE WHEN excluded.tags != '' THEN excluded.tags ELSE files.tags END,
                    local_path=excluded.local_path,
                    telegram_path=excluded.telegram_path,
                    channel_id=excluded.channel_id,
                    original_filename=excluded.original_filename
                """,
                (
                    message_id,
                    filename,
                    size,
                    mime_type,
                    upload_date,
                    tags,
                    local_path,
                    telegram_path,
                    channel_id,
                    original_filename,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_all_files(self, channel_id: int = 0) -> List[FileRecord]:
        with self._connect() as conn:
            if channel_id == -1:
                rows = conn.execute(
                    "SELECT * FROM files WHERE channel_id != 0 ORDER BY upload_date DESC"
                ).fetchall()
            elif channel_id:
                rows = conn.execute(
                    "SELECT * FROM files WHERE channel_id = ? ORDER BY upload_date DESC",
                    (channel_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM files ORDER BY upload_date DESC"
                ).fetchall()
            return [FileRecord(**dict(r)) for r in rows]

    def search_files(self, query: str, channel_id: int = 0) -> List[FileRecord]:
        # Substring search: split query by spaces and AND each term.
        # Escape LIKE wildcards (_ and %) so literal underscores are matched.
        terms = [t.strip() for t in query.split() if t.strip()]
        if not terms:
            return self.get_all_files(channel_id)
        like_tpl = "(filename LIKE ? ESCAPE '\\' OR tags LIKE ? ESCAPE '\\')"
        conditions = " AND ".join([like_tpl] * len(terms))
        params = []
        for t in terms:
            # Escape backslash first, then % and _
            escaped = t.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            sub_q = f"%{escaped}%"
            params.extend([sub_q, sub_q])
        with self._connect() as conn:
            if channel_id == -1:
                rows = conn.execute(
                    f"""
                    SELECT * FROM files
                    WHERE {conditions}
                    AND channel_id != 0
                    ORDER BY upload_date DESC
                    """,
                    params,
                ).fetchall()
            elif channel_id:
                rows = conn.execute(
                    f"""
                    SELECT * FROM files
                    WHERE {conditions}
                    AND channel_id = ?
                    ORDER BY upload_date DESC
                    """,
                    params + [channel_id],
                ).fetchall()
            else:
                rows = conn.execute(
                    f"""
                    SELECT * FROM files
                    WHERE {conditions}
                    ORDER BY upload_date DESC
                    """,
                    params,
                ).fetchall()
            return [FileRecord(**dict(r)) for r in rows]

    def delete_file(self, message_id: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM files WHERE message_id = ?", (message_id,))
            conn.commit()

    def get_file_by_message_id(self, message_id: int) -> Optional[FileRecord]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM files WHERE message_id = ?", (message_id,)
            ).fetchone()
            if row:
                return FileRecord(**dict(row))
            return None

    def get_channels(self) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT channel_id, channel_name FROM channels ORDER BY channel_name"
            ).fetchall()
            return [dict(r) for r in rows]

    def insert_or_update_channel(self, channel_id: int, channel_name: str):
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO channels (channel_id, channel_name)
                VALUES (?, ?)
                ON CONFLICT(channel_id) DO UPDATE SET
                    channel_name=excluded.channel_name
                """,
                (channel_id, channel_name),
            )
            conn.commit()

    def get_channel_name(self, channel_id: int) -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT channel_name FROM channels WHERE channel_id = ?", (channel_id,)
            ).fetchone()
            return row["channel_name"] if row else str(channel_id)

    def get_files_channel_ids(self) -> List[int]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT channel_id FROM files WHERE channel_id != 0 ORDER BY channel_id"
            ).fetchall()
            return [r["channel_id"] for r in rows]

    def get_favorite_channels(self) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT channel_id, channel_name, display_name, sort_order FROM favorite_channels ORDER BY sort_order, display_name"
            ).fetchall()
            return [dict(r) for r in rows]

    def add_favorite_channel(self, channel_id: int, channel_name: str, display_name: str = "", sort_order: int = 0):
        if not display_name:
            display_name = channel_name
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO favorite_channels (channel_id, channel_name, display_name, sort_order)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(channel_id) DO UPDATE SET
                    channel_name=excluded.channel_name,
                    display_name=excluded.display_name,
                    sort_order=excluded.sort_order
                """,
                (channel_id, channel_name, display_name, sort_order),
            )
            conn.commit()

    def remove_favorite_channel(self, channel_id: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM favorite_channels WHERE channel_id = ?", (channel_id,))
            conn.commit()

    def update_favorite_channel_display_name(self, channel_id: int, display_name: str):
        with self._connect() as conn:
            conn.execute(
                "UPDATE favorite_channels SET display_name = ? WHERE channel_id = ?",
                (display_name, channel_id),
            )
            conn.commit()

    def set_favorite_channels(self, channels: List[Dict]):
        with self._connect() as conn:
            conn.execute("DELETE FROM favorite_channels")
            for ch in channels:
                conn.execute(
                    """
                    INSERT INTO favorite_channels (channel_id, channel_name, display_name, sort_order)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        ch["channel_id"],
                        ch.get("channel_name", ch.get("display_name", str(ch["channel_id"]))),
                        ch.get("display_name", ch.get("channel_name", str(ch["channel_id"]))),
                        ch.get("sort_order", 0),
                    ),
                )
            conn.commit()

    def clear_all(self):
        with self._connect() as conn:
            conn.execute("DELETE FROM files")
            conn.commit()

    # ── Tags ───────────────────────────────────────────────────────

    def get_tags(self) -> List[Dict]:
        """Restituisce tutti i tag ordinati per sort_order."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT tag_id, tag_name, sort_order FROM tags ORDER BY sort_order, tag_name"
            ).fetchall()
            return [dict(r) for r in rows]

    def add_tag(self, tag_name: str, sort_order: int = 0) -> int:
        """Aggiunge un tag. Restituisce il tag_id."""
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO tags (tag_name, sort_order) VALUES (?, ?)",
                (tag_name, sort_order),
            )
            conn.commit()
            return cursor.lastrowid

    def remove_tag(self, tag_id: int):
        """Rimuove un tag e resetta il tag sui file che lo usano."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT tag_name FROM tags WHERE tag_id = ?", (tag_id,)
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE files SET tags = '' WHERE tags = ?", (row["tag_name"],)
                )
            conn.execute("DELETE FROM tags WHERE tag_id = ?", (tag_id,))
            conn.commit()

    def rename_tag(self, tag_id: int, new_name: str):
        """Rinomina un tag e aggiorna tutti i file che lo usano."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT tag_name FROM tags WHERE tag_id = ?", (tag_id,)
            ).fetchone()
            if row:
                old_name = row["tag_name"]
                conn.execute(
                    "UPDATE files SET tags = ? WHERE tags = ?",
                    (new_name, old_name),
                )
                conn.execute(
                    "UPDATE tags SET tag_name = ? WHERE tag_id = ?",
                    (new_name, tag_id),
                )
            conn.commit()

    def update_file_tag(self, message_id: int, tag_name: str):
        """Aggiorna il tag di un singolo file."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE files SET tags = ? WHERE message_id = ?",
                (tag_name, message_id),
            )
            conn.commit()

    def set_tags(self, tags: List[Dict]):
        """Sostituisce l'intera lista tag (per salvataggio da Settings)."""
        with self._connect() as conn:
            conn.execute("DELETE FROM tags")
            for t in tags:
                conn.execute(
                    "INSERT INTO tags (tag_name, sort_order) VALUES (?, ?)",
                    (t["tag_name"], t.get("sort_order", 0)),
                )
            conn.commit()

    def get_files_by_tag(self, tag_name: str, channel_id: int = 0) -> List[FileRecord]:
        """Restituisce tutti i file con un determinato tag (cross-channel)."""
        with self._connect() as conn:
            if channel_id == -1:
                rows = conn.execute(
                    "SELECT * FROM files WHERE tags = ? AND channel_id != 0 ORDER BY upload_date DESC",
                    (tag_name,),
                ).fetchall()
            elif channel_id:
                rows = conn.execute(
                    "SELECT * FROM files WHERE tags = ? AND channel_id = ? ORDER BY upload_date DESC",
                    (tag_name, channel_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM files WHERE tags = ? ORDER BY upload_date DESC",
                    (tag_name,),
                ).fetchall()
            return [FileRecord(**dict(r)) for r in rows]
