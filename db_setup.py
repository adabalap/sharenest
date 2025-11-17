#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sqlite3
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))
DB_PATH = os.getenv("SQLITE_DB", os.path.join(BASE_DIR, "sharenest.db"))

def setup_database():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY,
                original_filename TEXT NOT NULL,
                object_name TEXT UNIQUE NOT NULL,
                pin_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expiry_date TEXT NOT NULL,
                max_downloads INTEGER NOT NULL,
                download_count INTEGER NOT NULL DEFAULT 0,
                size_bytes INTEGER DEFAULT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS share_links (
                token TEXT PRIMARY KEY,
                file_id INTEGER NOT NULL,
                FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_files_expiry ON files(expiry_date)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_files_object ON files(object_name)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_share_fileid ON share_links(file_id)")
        conn.commit()
        print(f"Database setup complete at {DB_PATH}")
    finally:
        conn.close()

if __name__ == "__main__":
    setup_database()
