#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import hashlib
import secrets
import sqlite3
import logging
from datetime import datetime, timedelta, timezone

from flask import (
    Flask, render_template, request, redirect, url_for, flash, abort, g, jsonify
)
from dotenv import load_dotenv

# OCI SDK
try:
    import oci
    from oci.object_storage.models import CreatePreauthenticatedRequestDetails
except Exception as e:
    oci = None
    CreatePreauthenticatedRequestDetails = None
    print("Warning: OCI SDK not available. Install with `pip install oci`.")

# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Load .env that sits in /opt/sharenest/.env
load_dotenv(os.path.join(BASE_DIR, ".env"))

class Config:
    SECRET_KEY        = os.getenv("SECRET_KEY", secrets.token_hex(24))
    PIN_SALT          = os.getenv("PIN_SALT",  secrets.token_hex(16))
    SQLITE_DB         = os.getenv("SQLITE_DB", os.path.join(BASE_DIR, "sharenest.db"))
    FILE_EXPIRY_DAYS  = int(os.getenv("FILE_EXPIRY_DAYS", "7"))
    MAX_DOWNLOADS     = int(os.getenv("MAX_DOWNLOADS", "5"))
    PAR_EXPIRY_MIN    = int(os.getenv("PAR_EXPIRY_MIN", "5"))
    MULTIPART_THRESHOLD_MB = int(os.getenv("MULTIPART_THRESHOLD_MB", "100"))
    MULTIPART_PART_SIZE_MB = int(os.getenv("MULTIPART_PART_SIZE_MB", "32"))
    APP_HOST          = os.getenv("APP_HOST", "http://127.0.0.1:6000")


    # OCI config (API key auth)
    OCI_TENANCY_OCID      = os.getenv("OCI_TENANCY_OCID")
    OCI_USER_OCID         = os.getenv("OCI_USER_OCID")
    OCI_FINGERPRINT       = os.getenv("OCI_FINGERPRINT")
    OCI_PRIVATE_KEY_PATH  = os.path.expanduser(os.getenv("OCI_PRIVATE_KEY_PATH", "~/.oci/oci_api_key.pem"))
    OCI_REGION            = os.getenv("OCI_REGION")  # e.g., "ap-hyderabad-1"
    OCI_NAMESPACE         = os.getenv("OCI_NAMESPACE")  # required
    OCI_BUCKET_NAME       = os.getenv("OCI_BUCKET_NAME")  # required

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config.from_object(Config)

# Logging (file + console)
LOGS_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, "app.log")),
        logging.StreamHandler()
    ],
)

# ------------------------------------------------------------------------------
# DB helpers
# ------------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["SQLITE_DB"], detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_=None):
    db = g.pop("db", None)
    if db:
        db.close()

def init_db():
    db = get_db()
    c = db.cursor()
    # files: one row per uploaded file
    c.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY,
            original_filename TEXT NOT NULL,
            object_name TEXT UNIQUE NOT NULL,
            pin_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,       -- ISO 8601 UTC
            expiry_date TEXT NOT NULL,      -- ISO 8601 UTC
            max_downloads INTEGER NOT NULL,
            download_count INTEGER NOT NULL DEFAULT 0,
            size_bytes INTEGER DEFAULT NULL
        )
    """)
    # share_links: public token -> file_id
    c.execute("""
        CREATE TABLE IF NOT EXISTS share_links (
            token TEXT PRIMARY KEY,
            file_id INTEGER NOT NULL,
            FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE
        )
    """)
    # helpful indexes
    c.execute("CREATE INDEX IF NOT EXISTS idx_files_expiry ON files(expiry_date)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_files_object ON files(object_name)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_share_fileid ON share_links(file_id)")
    # pwa_installs: track PWA installation events
    c.execute("""
        CREATE TABLE IF NOT EXISTS pwa_installs (
            id INTEGER PRIMARY KEY,
            installed_at TEXT NOT NULL,
            user_agent TEXT,
            ip_address TEXT
        )
    """)
    db.commit()

with app.app_context():
    init_db()

# ------------------------------------------------------------------------------
# Crypto / PIN
# ------------------------------------------------------------------------------
def hash_pin(pin: str) -> str:
    salted = (pin or "").encode("utf-8") + app.config["PIN_SALT"].encode("utf-8")
    return hashlib.sha256(salted).hexdigest()

# ------------------------------------------------------------------------------
# OCI helpers
# ------------------------------------------------------------------------------
def oci_client():
    """
    Build and cache an ObjectStorageClient from env vars in the request context.
    """
    if "oci_client" not in g:
        required = [
            app.config["OCI_TENANCY_OCID"],
            app.config["OCI_USER_OCID"],
            app.config["OCI_FINGERPRINT"],
            app.config["OCI_PRIVATE_KEY_PATH"],
            app.config["OCI_REGION"],
            app.config["OCI_BUCKET_NAME"],
            app.config["OCI_NAMESPACE"],
        ]
        if any(not v for v in required):
            logging.error("OCI config incomplete; cannot create client.")
            g.oci_client = None
            return None

        cfg = {
            "user": app.config["OCI_USER_OCID"],
            "fingerprint": app.config["OCI_FINGERPRINT"],
            "tenancy": app.config["OCI_TENANCY_OCID"],
            "region": app.config["OCI_REGION"],
            "key_file": app.config["OCI_PRIVATE_KEY_PATH"],
        }
        try:
            g.oci_client = oci.object_storage.ObjectStorageClient(cfg)
        except Exception as e:
            logging.exception(f"OCI client init failed: {e}")
            g.oci_client = None
    return g.oci_client

def oci_upload(stream, object_name: str) -> bool:
    """
    Streams the incoming file directly to OCI.
    """
    if not oci or not CreatePreauthenticatedRequestDetails:
        # dev mode
        logging.warning("OCI SDK not installed; mock-upload success.")
        return True

    client = oci_client()
    if not client:
        return False
    try:
        client.put_object(
            namespace_name=app.config["OCI_NAMESPACE"],
            bucket_name=app.config["OCI_BUCKET_NAME"],
            object_name=object_name,
            put_object_body=stream  # file-like stream
        )
        return True
    except Exception as e:
        logging.exception(f"OCI upload error: {e}")
        return False

def oci_generate_par(object_name: str) -> str | None:
    """
    Creates a short-lived PAR URL (ObjectRead) and returns a full HTTPS URL.
    """
    if not oci or not CreatePreauthenticatedRequestDetails:
        # dev mode
        return f"https://mock.oci/par/{object_name}-{secrets.token_hex(6)}"

    client = oci_client()
    if not client:
        return None

    try:
        expires = datetime.now(timezone.utc) + timedelta(minutes=app.config["PAR_EXPIRY_MIN"])
        details = CreatePreauthenticatedRequestDetails(
            name=f"par-{object_name}",
            object_name=object_name,
            access_type="ObjectRead",
            time_expires=expires
        )
        resp = client.create_preauthenticated_request(
            namespace_name=app.config["OCI_NAMESPACE"],
            bucket_name=app.config["OCI_BUCKET_NAME"],
            create_preauthenticated_request_details=details
        )
        # resp.data.access_uri provides the path component for the PAR URL.
        base = f"https://objectstorage.{app.config['OCI_REGION']}.oraclecloud.com"
        return base + resp.data.access_uri
    except Exception as e:
        logging.exception(f"PAR creation failed: {e}")
        return None

def oci_generate_write_par(object_name: str) -> str | None:
    """
    Creates a short-lived PAR URL (ObjectWrite) and returns a full HTTPS URL.
    """
    if not oci or not CreatePreauthenticatedRequestDetails:
        # dev mode
        return f"https://mock.oci/par-write/{object_name}-{secrets.token_hex(6)}"

    client = oci_client()
    if not client:
        return None

    try:
        # Give more time for large uploads
        expires = datetime.now(timezone.utc) + timedelta(minutes=app.config["PAR_EXPIRY_MIN"] * 4)
        details = CreatePreauthenticatedRequestDetails(
            name=f"par-write-{object_name}",
            object_name=object_name,
            access_type="ObjectWrite",
            time_expires=expires
        )
        resp = client.create_preauthenticated_request(
            namespace_name=app.config["OCI_NAMESPACE"],
            bucket_name=app.config["OCI_BUCKET_NAME"],
            create_preauthenticated_request_details=details
        )
        # Write PARs use a different hostname format
        base = f"https://{app.config['OCI_NAMESPACE']}.objectstorage.{app.config['OCI_REGION']}.oci.customer-oci.com"
        return base + resp.data.access_uri
    except Exception as e:
        logging.exception(f"PAR (write) creation failed: {e}")
        return None

def oci_create_multipart_upload(object_name: str) -> str | None:
    """
    Initiates a multipart upload with OCI and returns the upload ID.
    """
    if not oci:
        return f"mock-upload-id-{secrets.token_hex(8)}"

    client = oci_client()
    if not client:
        return None
    try:
        details = oci.object_storage.models.CreateMultipartUploadDetails(object=object_name)
        resp = client.create_multipart_upload(
            namespace_name=app.config["OCI_NAMESPACE"],
            bucket_name=app.config["OCI_BUCKET_NAME"],
            create_multipart_upload_details=details
        )
        return resp.data.upload_id
    except Exception as e:
        logging.exception(f"Multipart upload initiation failed: {e}")
        return None

def oci_commit_multipart_upload(object_name: str, upload_id: str, parts: list) -> bool:
    """
    Commits a multipart upload after all parts are uploaded.
    `parts` is a list of dicts, e.g., [{"partNum": 1, "etag": "..."}]
    """
    if not oci:
        return True

    client = oci_client()
    if not client:
        return False
    try:
        details = oci.object_storage.models.CommitMultipartUploadDetails(
            parts_to_commit=[
                oci.object_storage.models.CommitMultipartUploadPartDetails(
                    part_num=p["partNum"], etag=p["etag"]
                ) for p in parts
            ]
        )
        client.commit_multipart_upload(
            namespace_name=app.config["OCI_NAMESPACE"],
            bucket_name=app.config["OCI_BUCKET_NAME"],
            object_name=object_name,
            upload_id=upload_id,
            commit_multipart_upload_details=details
        )
        return True
    except Exception as e:
        logging.exception(f"Multipart commit failed: {e}")
        return False

def oci_abort_multipart_upload(object_name: str, upload_id: str) -> bool:
    """
    Aborts a stalled or failed multipart upload.
    """
    if not oci:
        return True

    client = oci_client()
    if not client:
        return False
    try:
        client.abort_multipart_upload(
            namespace_name=app.config["OCI_NAMESPACE"],
            bucket_name=app.config["OCI_BUCKET_NAME"],
            object_name=object_name,
            upload_id=upload_id
        )
        logging.info(f"Aborted multipart upload {upload_id} for {object_name}")
        return True
    except Exception as e:
        logging.exception(f"Multipart abort failed: {e}")
        return False



# ------------------------------------------------------------------------------
# Utilities
# ------------------------------------------------------------------------------
def iso_now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()

def iso_to_dt(iso_str: str) -> datetime:
    # stored as ISO 8601 with timezone; parse safely
    return datetime.fromisoformat(iso_str)

def pretty_remaining(expiry_iso: str) -> str:
    try:
        delta = iso_to_dt(expiry_iso) - datetime.now(timezone.utc)
        if delta.total_seconds() <= 0:
            return "Expired"
        days = delta.days
        hours = (delta.seconds // 3600)
        mins = (delta.seconds % 3600) // 60
        parts = []
        if days: parts.append(f"{days}d")
        if hours: parts.append(f"{hours}h")
        if mins: parts.append(f"{mins}m")
        return " ".join(parts) or "<1m"
    except Exception:
        return "-"

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")

# --- PWA and Static File Routes ---
@app.route('/manifest.json')
def serve_manifest():
    return app.send_static_file('manifest.json')

@app.route('/sw.js')
def serve_sw():
    return app.send_static_file('sw.js')

# ------------------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------------------

@app.route("/api/initiate-upload", methods=["POST"])
def initiate_upload():
    """
    Initiates a direct or multipart upload based on file size.
    - For small files, generates a direct write PAR.
    - For large files, creates a multipart upload session.
    """
    data = request.get_json()
    filename = data.get("filename")
    file_size_bytes = data.get("file_size_bytes")

    if not filename:
        return jsonify(error="Filename is required."), 400

    # Sanitize filename
    filename = "".join(c for c in filename if c.isalnum() or c in (" ", ".", "_", "-")).strip() or "file"
    object_name = f"{secrets.token_hex(8)}_{filename}"

    # Decide strategy based on size
    threshold_bytes = app.config["MULTIPART_THRESHOLD_MB"] * 1024 * 1024
    if file_size_bytes and file_size_bytes > threshold_bytes:
        # --- Multipart Upload ---
        upload_id = oci_create_multipart_upload(object_name)
        if not upload_id:
            return jsonify(error="Could not initiate multipart upload."), 500

        # For multipart, we also need a single write PAR for the object
        par_url = oci_generate_write_par(object_name)
        if not par_url:
            # If PAR fails, abort the multipart upload to clean up
            oci_abort_multipart_upload(object_name, upload_id)
            return jsonify(error="Could not create a secure upload link for multipart."), 500

        return jsonify({
            "upload_type": "multipart",
            "upload_id": upload_id,
            "object_name": object_name,
            "par_url": par_url,  # The base URL for all parts
            "part_size_bytes": app.config["MULTIPART_PART_SIZE_MB"] * 1024 * 1024
        })
    else:
        # --- Direct Upload ---
        par_url = oci_generate_write_par(object_name)
        if not par_url:
            return jsonify(error="Could not create a secure upload link."), 500

        return jsonify({
            "upload_type": "direct",
            "par_url": par_url,
            "object_name": object_name
        })



@app.route("/api/finalize-upload", methods=["POST"])
def finalize_upload():
    data = request.get_json()
    pin = data.get("pin")
    original_filename = data.get("original_filename")
    object_name = data.get("object_name")
    size_bytes = data.get("size_bytes")
    # Multipart-specific fields
    upload_id = data.get("upload_id")
    parts = data.get("parts")

    if not all([pin, original_filename, object_name, isinstance(size_bytes, int)]):
        return jsonify(error="Missing required data for finalization."), 400
    if len(pin) < 4:
        return jsonify(error="Security phrase must be at least 4 characters."), 400

    # If it was a multipart upload, commit it first.
    if upload_id and parts:
        if not oci_commit_multipart_upload(object_name, upload_id, parts):
            # Abort the failed commit to prevent orphaned parts
            oci_abort_multipart_upload(object_name, upload_id)
            return jsonify(error="Failed to commit multipart upload."), 500

    pin_hash = hash_pin(pin)
    created = iso_now_utc()
    expiry = (datetime.now(timezone.utc) + timedelta(days=app.config["FILE_EXPIRY_DAYS"])).isoformat()

    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            INSERT INTO files
                (original_filename, object_name, pin_hash, created_at, expiry_date, max_downloads, download_count, size_bytes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (original_filename, object_name, pin_hash, created, expiry, app.config["MAX_DOWNLOADS"], 0, size_bytes))
        file_id = cur.lastrowid
        token = secrets.token_urlsafe(16)
        cur.execute("INSERT INTO share_links (token, file_id) VALUES (?, ?)", (token, file_id))
        db.commit()

        share_url = f"{app.config['APP_HOST']}{url_for('share_gate', token=token)}"
        return jsonify({
            "share_url": share_url,
            "filename": original_filename,
            "expiry": expiry,
            "expiry_pretty": pretty_remaining(expiry)
        })
    except sqlite3.IntegrityError:
        logging.warning(f"IntegrityError on finalize, likely duplicate: {object_name}")
        return jsonify(error="This file may have already been finalized."), 409
    except Exception as e:
        logging.exception(f"DB error during finalization: {e}")
        db.rollback()
        return jsonify(error="An internal error occurred during finalization."), 500

@app.route("/api/abort-upload", methods=["POST"])
def abort_upload():
    """
    Aborts a multipart upload, useful for client-side cancellation.
    """
    data = request.get_json()
    object_name = data.get("object_name")
    upload_id = data.get("upload_id")

    if not all([object_name, upload_id]):
        return jsonify(error="object_name and upload_id are required."), 400

    if oci_abort_multipart_upload(object_name, upload_id):
        return jsonify(status="aborted")
    else:
        return jsonify(error="Failed to abort upload."), 500



@app.route("/share/<token>", methods=["GET"])
def share_gate(token: str):
    db = get_db()
    row = db.execute("""
        SELECT f.id AS file_id, f.original_filename, f.object_name,
               f.expiry_date, f.download_count, f.max_downloads
        FROM share_links s
        JOIN files f ON f.id = s.file_id
        WHERE s.token = ?
    """, (token,)).fetchone()

    if not row:
        abort(404, "Share link not found.")

    expired = iso_to_dt(row["expiry_date"]) <= datetime.now(timezone.utc)
    limit_reached = row["download_count"] >= row["max_downloads"]

    if expired:
        flash("This share link has expired and the file has been removed.", "error")
    elif limit_reached:
        flash(f"This file has reached its maximum download limit ({row['max_downloads']}).", "error")

    return render_template(
        "download.html",
        token=token,
        file_info=row,
        expired=expired,
        limit_reached=limit_reached,
        expiry_pretty=pretty_remaining(row["expiry_date"])
    )

@app.route("/download/<token>", methods=["POST"])
def download_after_pin(token: str):
    pin = request.form.get("security_phrase", "").strip()
    if not pin:
        flash("Security phrase is required.", "error")
        return redirect(url_for("share_gate", token=token))

    db = get_db()
    row = db.execute("""
        SELECT f.id, f.pin_hash, f.object_name, f.expiry_date,
               f.download_count, f.max_downloads
        FROM share_links s
        JOIN files f ON f.id = s.file_id
        WHERE s.token = ?
    """, (token,)).fetchone()

    if not row:
        abort(404, "Share link not found.")

    # Re-validate expiry and download limit before proceeding
    if iso_to_dt(row["expiry_date"]) <= datetime.now(timezone.utc):
        flash("This share link has expired.", "error")
        return redirect(url_for("share_gate", token=token))
    if row["download_count"] >= row["max_downloads"]:
        flash("This file has reached its maximum download limit.", "error")
        return redirect(url_for("share_gate", token=token))

    if hash_pin(pin) != row["pin_hash"]:
        flash("Incorrect security phrase. Please try again.", "error")
        return redirect(url_for("share_gate", token=token))

    # All checks passed, generate the download link
    par_url = oci_generate_par(row["object_name"])
    if not par_url:
        flash("Could not generate a secure download link at this time. Please try again later.", "error")
        return redirect(url_for("share_gate", token=token))

    # Increment download count
    try:
        db.execute("UPDATE files SET download_count = download_count + 1 WHERE id = ?", (row["id"],))
        db.commit()
    except Exception as e:
        logging.warning(f"Failed to update download_count for file ID {row['id']}: {e}")
        # Do not block the download if this fails; it's non-critical
    
    return redirect(par_url)

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify(status="ok", time=iso_now_utc())

@app.route("/api/track-install", methods=["POST"])
def track_install():
    """
    Tracks a PWA installation event.
    """
    try:
        db = get_db()
        db.execute(
            "INSERT INTO pwa_installs (installed_at, user_agent, ip_address) VALUES (?, ?, ?)",
            (
                iso_now_utc(),
                request.headers.get("User-Agent", "Unknown"),
                request.remote_addr
            )
        )
        db.commit()
        return jsonify(status="ok"), 201
    except Exception as e:
        logging.error(f"PWA install tracking failed: {e}")
        return jsonify(error="Internal server error"), 500

if __name__ == "__main__":
    # For local debugging only. In prod we use gunicorn (see systemd unit).
    app.run(host="0.0.0.0", port=6000, debug=True)
