import os
import sqlite3

def init_db(db_path, legacy_path=None):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS wardrobe (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        image_path TEXT,
        main_category TEXT,
        sub_category TEXT,
        article_type TEXT,
        color TEXT,
        fit TEXT,
        material TEXT,
        gender TEXT DEFAULT 'unisex',
        season_tags TEXT,
        occasion_tags TEXT,
        style_tags TEXT,
        description TEXT
    );
    """)

    c.execute("PRAGMA table_info(wardrobe)")
    existing_columns = {row[1] for row in c.fetchall()}

    required_columns = {
        "fit": "TEXT",
        "material": "TEXT",
        "gender": "TEXT DEFAULT 'unisex'",
        "season_tags": "TEXT",
        "occasion_tags": "TEXT",
        "style_tags": "TEXT",
        "description": "TEXT",
        "extra_details": "TEXT",
    }

    for column_name, column_type in required_columns.items():
        if column_name not in existing_columns:
            c.execute(f"ALTER TABLE wardrobe ADD COLUMN {column_name} {column_type}")

    conn.commit()
    conn.close()

    if not legacy_path or legacy_path == db_path:
        return
    if not os.path.exists(legacy_path):
        return

    try:
        legacy_conn = sqlite3.connect(legacy_path)
        legacy_cursor = legacy_conn.cursor()
        legacy_cursor.execute("PRAGMA table_info(wardrobe)")
        legacy_columns = {row[1] for row in legacy_cursor.fetchall()}
        if not legacy_columns:
            legacy_conn.close()
            return

        select_columns = [
            "id",
            "user_id",
            "image_path",
            "main_category",
            "sub_category",
            "article_type",
            "color",
            "fit",
            "material",
            "gender",
            "season_tags",
            "occasion_tags",
            "style_tags",
            "description",
            "extra_details",
        ]
        available_columns = [col for col in select_columns if col in legacy_columns]
        legacy_cursor.execute(
            f"SELECT {', '.join(available_columns)} FROM wardrobe"
        )
        raw_rows = legacy_cursor.fetchall()
        legacy_conn.close()
    except Exception:
        return

    if not raw_rows:
        return

    rows = []
    for row in raw_rows:
        row_map = dict(zip(available_columns, row))
        rows.append(
            (
                row_map.get("id"),
                row_map.get("user_id"),
                row_map.get("image_path"),
                row_map.get("main_category"),
                row_map.get("sub_category"),
                row_map.get("article_type"),
                row_map.get("color"),
                row_map.get("fit"),
                row_map.get("material"),
                row_map.get("gender") or "unisex",
                row_map.get("season_tags"),
                row_map.get("occasion_tags"),
                row_map.get("style_tags"),
                row_map.get("description"),
                row_map.get("extra_details"),
            )
        )

    target_conn = sqlite3.connect(db_path)
    target_cursor = target_conn.cursor()
    target_cursor.executemany(
        """
        INSERT OR IGNORE INTO wardrobe
        (
            id, user_id, image_path, main_category, sub_category, article_type, color,
            fit, material, gender, season_tags, occasion_tags, style_tags, description, extra_details
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    target_conn.commit()
    target_conn.close()

