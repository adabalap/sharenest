#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sqlite3
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

# OCI
try:
    import oci
except Exception:
    oci = None

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

LOGS_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOGS_DIR, "cleanup.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

DB_PATH = os.getenv("SQLITE_DB", os.path.join(BASE_DIR, "sharenest.db"))

OCI_TENANCY_OCID     = os.getenv("OCI_TENANCY_OCID")
OCI_USER_OCID        = os.getenv("OCI_USER_OCID")
OCI_FINGERPRINT      = os.getenv("OCI_FINGERPRINT")
OCI_PRIVATE_KEY_PATH = os.path.expanduser(os.getenv("OCI_PRIVATE_KEY_PATH", "~/.oci/oci_api_key.pem"))
OCI_REGION           = os.getenv("OCI_REGION")
OCI_NAMESPACE        = os.getenv("OCI_NAMESPACE")
OCI_BUCKET_NAME      = os.getenv("OCI_BUCKET_NAME")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def oci_client():
    if not oci:
        logging.warning("OCI SDK not installed; cleanup will only purge DB rows.")
        return None
    required = [OCI_TENANCY_OCID, OCI_USER_OCID, OCI_FINGERPRINT, OCI_PRIVATE_KEY_PATH, OCI_REGION, OCI_NAMESPACE, OCI_BUCKET_NAME]
    if any(not v for v in required):
        logging.error("Missing OCI config; will skip object deletions.")
        return None
    cfg = {
        "user": OCI_USER_OCID,
        "fingerprint": OCI_FINGERPRINT,
        "tenancy": OCI_TENANCY_OCID,
        "region": OCI_REGION,
        "key_file": OCI_PRIVATE_KEY_PATH,
    }
    try:
        return oci.object_storage.ObjectStorageClient(cfg)
    except Exception as e:
        logging.exception(f"OCI client init failed: {e}")
        return None

def delete_object(client, object_name: str) -> bool:
    if not client:
        return False
    try:
        client.delete_object(OCI_NAMESPACE, OCI_BUCKET_NAME, object_name)
        logging.info(f"Deleted OCI object: {object_name}")
        return True
    except Exception as e:
        # Ignore 404
        msg = str(e)
        if "NotAuthorizedOrNotFound" in msg or "404" in msg:
            logging.info(f"Object not found (already deleted): {object_name}")
            return True
        logging.exception(f"Error deleting {object_name}: {e}")
        return False

def run_cleanup():
    now_iso = datetime.now(timezone.utc).isoformat()
    logging.info(f"Cleanup start at {now_iso}")

    db = get_db()
    client = oci_client()
    total_deleted = 0
    batch_size = 100  # Process 100 at a time

    try:
        while True:
            # Fetch a batch of expired file IDs
            rows = db.execute("""
                SELECT id, object_name
                FROM files
                WHERE expiry_date < ? OR (max_downloads IS NOT NULL AND download_count >= max_downloads)
                LIMIT ?
            """, (now_iso, batch_size)).fetchall()

            if not rows:
                break  # No more expired files

            object_names_to_delete = [r["object_name"] for r in rows]
            file_ids_to_delete = [r["id"] for r in rows]

            # 1. Delete objects from OCI
            if client:
                for object_name in object_names_to_delete:
                    delete_object(client, object_name)

            # 2. Delete from the database
            # Use `id IN (...)` for batch deletion
            if file_ids_to_delete:
                # Create placeholders for the IN clause
                placeholders = ",".join("?" for _ in file_ids_to_delete)
                
                # The ON DELETE CASCADE foreign key will handle the `share_links` table
                db.execute(f"DELETE FROM files WHERE id IN ({placeholders})", file_ids_to_delete)
                
                db.commit()
                total_deleted += len(file_ids_to_delete)
                logging.info(f"Deleted batch of {len(file_ids_to_delete)} records.")

        logging.info(f"Cleanup complete. Removed {total_deleted} record(s) in total.")
    except Exception as e:
        db.rollback()
        logging.exception(f"Cleanup failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_cleanup()
