#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import hashlib
import secrets
import sqlite3
import logging
from datetime import datetime, timedelta, timezone

import concurrent.futures
from flask import (
    Flask, render_template, request, redirect, url_for, flash, abort, g, jsonify, session
)
from dotenv import load_dotenv
from authlib.integrations.flask_client import OAuth

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
    PAR_EXPIRY_MIN    = int(os.getenv("PAR_EXPIRY_MIN", "60"))
    APP_HOST          = os.getenv("APP_HOST", "http://127.0.0.1:6000")


    # OCI config (API key auth)
    OCI_TENANCY_OCID      = os.getenv("OCI_TENANCY_OCID")
    OCI_USER_OCID         = os.getenv("OCI_USER_OCID")
    OCI_FINGERPRINT       = os.getenv("OCI_FINGERPRINT")
    OCI_PRIVATE_KEY_PATH  = os.path.expanduser(os.getenv("OCI_PRIVATE_KEY_PATH", "~/.oci/oci_api_key.pem"))
    OCI_REGION            = os.getenv("OCI_REGION")  # e.g., "ap-hyderabad-1"
    OCI_NAMESPACE         = os.getenv("OCI_NAMESPACE")  # required
    OCI_BUCKET_NAME       = os.getenv("OCI_BUCKET_NAME")  # required
    OCI_TIMEOUT           = int(os.getenv("OCI_TIMEOUT", "60")) # OCI API call timeout in seconds

    ADMIN_USER            = os.getenv("ADMIN_USER")
    ADMIN_PASSWORD        = os.getenv("ADMIN_PASSWORD")

    # Google OAuth
    GOOGLE_CLIENT_ID      = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET  = os.getenv("GOOGLE_CLIENT_SECRET")

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config.from_object(Config)

# Authlib OAuth initialization
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=app.config["GOOGLE_CLIENT_ID"],
    client_secret=app.config["GOOGLE_CLIENT_SECRET"],
    access_token_url='https://accounts.google.com/o/oauth2/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params=None,
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    client_kwargs={'scope': 'openid email profile'},
    jwks_uri='https://www.googleapis.com/oauth2/v3/certs'
)

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
            size_bytes INTEGER DEFAULT NULL,
            user_email TEXT,                -- New column for associated user email (nullable)
            sharing_message TEXT,            -- New column for sharing message (nullable)
            city TEXT,      -- New column for city (nullable)
            country TEXT    -- New column for country (nullable)
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
    # users: stores information about Google OAuth authenticated users
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', -- 'allowed', 'pending', 'denied'
            created_at TEXT NOT NULL,
            last_login_at TEXT
        )
    """)
    db.commit()

with app.app_context():
    init_db()

from functools import wraps

def admin_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            flash("Please log in to access the admin page.", "error")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated_function

def user_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in") and not session.get("google_logged_in"):
            flash("Please log in to access this page.", "error")
            return redirect(url_for("index")) # New root landing page
        return f(*args, **kwargs)
    return decorated_function

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("logged_in"):
        return redirect(url_for("admin_dashboard")) # Redirect if already logged in

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # Basic rate limiting can be added here if needed, but keeping it simple for now.
        if username == app.config["ADMIN_USER"] and password == app.config["ADMIN_PASSWORD"]:
            session["logged_in"] = True
            flash("Logged in successfully!", "success")
            return redirect(url_for("admin_dashboard")) # Will be created later
        else:
            flash("Invalid credentials.", "error")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("logged_in", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("admin_login"))

@app.route("/logout/google")
def google_logout():
    session.pop("google_logged_in", None)
    session.pop("email", None)
    flash("You have been logged out from ShareNest.", "info")
    return redirect(url_for("index"))

@app.route('/login/google/authorized', methods=['GET', 'POST'])
def authorize_google():
    logging.info("Received callback from Google OAuth.")
    try:
        if request.method == 'POST':
            # New GSI flow
            token = request.form.get('credential')
            if not token:
                raise Exception("No credential in POST request.")
            nonce = session.pop('nonce', None)
            user_info = google.parse_id_token({'id_token': token}, nonce=nonce)
        else:
            # Old OAuth flow
            token = google.authorize_access_token()
            nonce = session.get('nonce')
            user_info = google.parse_id_token(token, nonce=nonce)

        user_email = user_info['email']
        logging.info(f"Successfully authenticated Google user: {user_email}")

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (user_email,)).fetchone()

        if user:
            # User exists, update last login
            db.execute(
                "UPDATE users SET last_login_at = ? WHERE email = ?",
                (iso_now_utc(), user_email)
            )
            db.commit()
            logging.info(f"User {user_email} already exists. Status: {user['status']}")

            if user['status'] == 'allowed':
                session['google_logged_in'] = True
                session['email'] = user_email
                session['first_name'] = user_info.get('given_name') # Store first name
                flash(f"Welcome, {user_info.get('given_name', user_email)}!", "success") # Use first name in flash message
                logging.info(f"User {user_email} (allowed) logged in via Google. Redirecting to home.")
                return redirect(url_for('home'))
            elif user['status'] == 'pending':
                flash("Your access is pending approval.", "info")
                logging.info(f"User {user_email} access pending approval. Redirecting to status page.")
                return redirect(url_for('status'))
            elif user['status'] == 'denied':
                flash("Your access has been denied. Please contact support.", "error")
                logging.warning(f"User {user_email} access denied. Redirecting to status page.")
                return redirect(url_for('status'))
        else:
            # New user, add to DB with pending status
            db.execute(
                "INSERT INTO users (email, status, created_at, last_login_at) VALUES (?, ?, ?, ?)",
                (user_email, 'pending', iso_now_utc(), iso_now_utc())
            )
            db.commit()
            logging.info(f"New user {user_email} registered with 'pending' status.")
            flash("Your access is pending approval.", "info")
            logging.info(f"New user {user_email} created and access pending approval. Redirecting to status page.")
            return redirect(url_for('status'))

    except Exception as e:
        logging.exception(f"Google OAuth authorization failed. Error: {e}")
        flash("Google login failed. Please try again.", "error")
        return redirect(url_for('index'))


@app.route("/status")
def status():
    return render_template("pending.html")

@app.route("/admin/files", methods=["GET"])
@admin_login_required
def admin_get_files():
    logging.info("admin_get_files: Starting redesigned file listing process.")
    all_files_for_display = []
    
    try:
        # 1. Get all OCI object summaries
        logging.info("admin_get_files: Calling oci_list_objects to retrieve OCI object summaries.")
        oci_object_summaries = oci_list_objects(app) # Pass app
        logging.info(f"admin_get_files: Received {len(oci_object_summaries)} object summaries from OCI.")
        
        oci_object_names_set = set()
        for obj_summary in oci_object_summaries:
            if obj_summary.name:
                oci_object_names_set.add(obj_summary.name)

        # 2. Get all file records from the local database for efficient lookup
        db = get_db()
        logging.info("admin_get_files: Fetching all file records from local database.")
        
        query = """
            SELECT id, original_filename, object_name, created_at, expiry_date,
                   max_downloads, download_count, size_bytes, user_email, sharing_message,
                   city, country
            FROM files
        """
        params = []

        logging.info("admin_get_files: No specific user logged in via Google, fetching all files.")

        db_files_cursor = db.execute(query, params)
        db_files_map = {row['object_name']: dict(row) for row in db_files_cursor.fetchall()}
        logging.info(f"admin_get_files: Fetched {len(db_files_map)} records from database.")

        # Keep track of database object names that have been matched with OCI objects
        matched_db_object_names = set()

        # 3. Iterate through OCI objects (primary source)
        for obj_summary in oci_object_summaries:
            object_name = obj_summary.name
            if not object_name:
                continue

            file_entry = {
                "object_name": object_name,
                "original_filename": object_name, # Default to object name if not in DB
                "size_bytes": obj_summary.size if obj_summary else None,
                "created_at": iso_to_dt(obj_summary.time_created).isoformat() if obj_summary and obj_summary.time_created else None,
                "expiry_date": None,
                "download_count": 'N/A',
                "max_downloads": 'N/A',
                "id": None,
            }

            if object_name in db_files_map:
                # This OCI object is also in our database (synced)
                db_data = db_files_map[object_name]
                file_entry.update(db_data) # Overwrite OCI data with more complete DB data
                file_entry['status'] = 'synced'
                matched_db_object_names.add(object_name)
            else:
                # This OCI object is not in our database (orphaned)
                file_entry['status'] = 'orphaned'
            
            all_files_for_display.append(file_entry)
        
        logging.info(f"admin_get_files: Processed {len(oci_object_summaries)} OCI objects.")

        # 4. Identify and add missing DB records (in DB, not in OCI)
        missing_db_object_names = set(db_files_map.keys()) - matched_db_object_names
        if missing_db_object_names:
            logging.info(f"admin_get_files: Found {len(missing_db_object_names)} missing DB records.")
            for object_name in missing_db_object_names:
                db_data = db_files_map[object_name]
                file_entry = db_data
                file_entry['status'] = 'missing'
                all_files_for_display.append(file_entry)

        # Sort the final list
        def sort_key(f):
            status_order = {'missing': 0, 'orphaned': 1, 'synced': 2}
            date_str = f.get('created_at') or '1970-01-01T00:00:00.000000+00:00'
            try:
                dt = iso_to_dt(date_str)
            except Exception:
                logging.warning(f"admin_get_files: Could not parse date '{date_str}' for sorting. Using epoch.")
                dt = iso_to_dt('1970-01-01T00:00:00.000000+00:00')
            return (status_order.get(f['status'], 9), dt)

        all_files_for_display.sort(key=sort_key, reverse=True) # Newest first for dates
        logging.info("admin_get_files: Finished sorting files.")
        
        return jsonify(all_files_for_display)

    except Exception as e:
        logging.exception("admin_get_files: An unexpected error occurred during file listing and reconciliation.")
        return jsonify(error="An internal server error occurred while loading files. Please check server logs."), 500

@app.route("/admin/users", methods=["GET"])
@admin_login_required
def admin_get_users():
    try:
        db = get_db()
        users_cursor = db.execute("SELECT id, email, status, created_at, last_login_at FROM users ORDER BY created_at DESC")
        users = [dict(row) for row in users_cursor.fetchall()]
        return jsonify(users)
    except Exception as e:
        logging.exception("An error occurred while fetching users for the admin dashboard.")
        return jsonify(error="An internal server error occurred while fetching users."), 500


@app.route("/admin/users/<int:user_id>/status", methods=["PUT"])
@admin_login_required
def admin_update_user_status(user_id):
    data = request.get_json()
    new_status = data.get("status")

    if not new_status or new_status not in ['allowed', 'pending', 'denied']:
        return jsonify(error="Invalid status provided."), 400

    try:
        db = get_db()
        cur = db.execute("UPDATE users SET status = ? WHERE id = ?", (new_status, user_id))
        if cur.rowcount == 0:
            return jsonify(error="User not found."), 404
        db.commit()
        logging.info(f"Admin updated user {user_id} to status '{new_status}'")
        return jsonify(success=True, message=f"User status updated to {new_status}.")
    except Exception as e:
        logging.exception(f"An error occurred while updating status for user {user_id}.")
        db.rollback()
        return jsonify(error="An internal server error occurred."), 500


@app.route("/admin")
@admin_login_required
def admin_dashboard():
    return render_template("admin.html")


# ------------------------------------------------------------------------------
# Crypto / PIN
# ------------------------------------------------------------------------------
def hash_pin(pin: str) -> str:
    salted = (pin or "").encode("utf-8") + app.config["PIN_SALT"].encode("utf-8")
    return hashlib.sha256(salted).hexdigest()

# ------------------------------------------------------------------------------
# OCI helpers
# ------------------------------------------------------------------------------
def oci_client(app):
    """
    Build and cache an ObjectStorageClient from env vars in the request context.
    """
    with app.app_context(): # Ensure app context is available
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
            logging.info(f"oci_client: Initializing OCI ObjectStorageClient with timeout: {app.config['OCI_TIMEOUT']}s.")
            try:
                g.oci_client = oci.object_storage.ObjectStorageClient(cfg, timeout=app.config["OCI_TIMEOUT"])
            except Exception as e:
                logging.exception(f"OCI client init failed: {e}")
                g.oci_client = None
        return g.oci_client



def oci_generate_par(app, object_name: str) -> str | None:
    """
    Creates a short-lived PAR URL (ObjectRead) and returns a full HTTPS URL.
    """
    with app.app_context():
        if not oci or not CreatePreauthenticatedRequestDetails:
            # dev mode
            return f"https://mock.oci/par/{object_name}-{secrets.token_hex(6)}"

        client = oci_client(app) # Pass app to oci_client
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
            par_url = base + resp.data.access_uri
            logging.info(f"Generated PAR for object '{object_name}': {par_url}")
            return par_url
        except Exception as e:
            logging.exception(f"PAR creation failed: {e}")
            return None

def oci_generate_upload_par(app, object_name: str) -> str | None:
    """
    Creates a short-lived PAR URL (ObjectWrite) and returns a full HTTPS URL.
    """
    with app.app_context():
        if not oci or not CreatePreauthenticatedRequestDetails:
            # dev mode
            return f"https://mock.oci/par-upload/{object_name}-{secrets.token_hex(6)}"

        client = oci_client(app) # Pass app to oci_client
        if not client:
            return None

        try:
            # Give more time for large uploads
            expires = datetime.now(timezone.utc) + timedelta(minutes=app.config["PAR_EXPIRY_MIN"] * 4)
            details = CreatePreauthenticatedRequestDetails(
                name=f"par-write-{object_name}",
                object_name=object_name,
                access_type="ObjectReadWrite", # Changed from ObjectWrite
                time_expires=expires
            )
            resp = client.create_preauthenticated_request(
                namespace_name=app.config["OCI_NAMESPACE"],
                bucket_name=app.config["OCI_BUCKET_NAME"],
                create_preauthenticated_request_details=details
            )
            # Write PARs use a different hostname format
            base = f"https://{app.config['OCI_NAMESPACE']}.objectstorage.{app.config['OCI_REGION']}.oci.customer-oci.com"
            par_url = base + resp.data.access_uri
            logging.info(f"Generated upload PAR for object '{object_name}': {par_url}")
            return par_url

        except Exception as e:
            logging.exception(f"PAR (write) creation failed: {e}")
            return None


def oci_delete_object(app, object_name: str) -> bool:
    """
    Deletes an object from OCI Object Storage.
    """
    with app.app_context():
        if not oci:
            logging.warning(f"OCI SDK not installed; mock-delete success for {object_name}.")
            return True

        client = oci_client(app) # Pass app to oci_client
        if not client:
            return False

        try:
            client.delete_object(
                namespace_name=app.config["OCI_NAMESPACE"],
                bucket_name=app.config["OCI_BUCKET_NAME"],
                object_name=object_name
            )
            logging.info(f"Successfully deleted object '{object_name}' from OCI.")
            return True
        except oci.exceptions.ServiceError as e:
            if e.status == 404:
                logging.warning(f"Attempted to delete non-existent object '{object_name}' from OCI. Treating as success.")
                return True # Object already gone, treat as success
            logging.exception(f"OCI delete error for '{object_name}': {e}")
            return False
        except Exception as e:
            logging.exception(f"Unexpected error during OCI object deletion for '{object_name}': {e}")
            return False

def oci_list_objects(app):
    """
    Lists a limited number of objects in the OCI bucket. Handles pagination.
    NOTE: This is intentionally limited to 1000 objects for performance reasons.
    A full background reconciliation would be needed for larger buckets.
    """
    with app.app_context():
        if not oci:
            logging.warning("OCI SDK not available. Returning mock object list.")
            # Return mock ObjectSummary-like objects
            return [
                type('obj', (object,), {'name': "mock_object_1", 'size': 1024, 'time_created': datetime.now(timezone.utc) - timedelta(days=5)}),
                type('obj', (object,), {'name': "mock_object_2", 'size': 2048, 'time_created': datetime.now(timezone.utc) - timedelta(days=2)})
            ]

        client = oci_client(app) # Pass app to oci_client
        if not client:
            return []

        all_objects = []
        try:
            response = client.list_objects(
                namespace_name=app.config["OCI_NAMESPACE"],
                bucket_name=app.config["OCI_BUCKET_NAME"],
                limit=1000
            )
            if response.data.objects:
                all_objects.extend(response.data.objects) # Now extending with ObjectSummary objects
            
            logging.info(f"Listed {len(all_objects)} objects from OCI bucket '{app.config['OCI_BUCKET_NAME']}' (limited to 1000).")
            return all_objects
        except Exception as e:
            logging.exception(f"Failed to list objects from OCI: {e}")
            return []

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

def get_user_files(email: str) -> list:
    """
    Retrieves all files uploaded by a specific user.
    """
    db = get_db()
    files = db.execute("""
        SELECT f.id, f.original_filename, f.created_at, f.expiry_date, f.download_count, f.max_downloads, f.sharing_message, s.token
        FROM files f
        LEFT JOIN share_links s ON f.id = s.file_id
        WHERE f.user_email = ?
        ORDER BY f.created_at DESC
    """, (email,)).fetchall()
    
    file_list = []
    for file in files:
        file_dict = dict(file)
        if file_dict.get('created_at'):
            file_dict['created_at'] = iso_to_dt(file_dict['created_at'])
        if file_dict.get('expiry_date'):
            file_dict['expiry_date'] = iso_to_dt(file_dict['expiry_date'])
        file_list.append(file_dict)
    return file_list

@app.route("/", methods=["GET"])
def index(): # Renamed 'story' to 'index' for consistency with root path
    if session.get("logged_in") or session.get("google_logged_in"):
        return redirect(url_for("home"))
    nonce = secrets.token_urlsafe(16)
    session['nonce'] = nonce
    return render_template("landing.html", google_client_id=app.config["GOOGLE_CLIENT_ID"], nonce=nonce)

@app.route("/home", methods=["GET"])
@user_login_required
def home():
    return render_template("home.html")

@app.route("/dashboard", methods=["GET"])
@user_login_required
def dashboard():
    user_email = session.get("email")
    if not user_email:
        flash("You must be logged in to view the dashboard.", "error")
        return redirect(url_for("login_google"))

    files = get_user_files(user_email)
    return render_template("dashboard.html", files=files)

@app.route("/about", methods=["GET"])
def about():
    return render_template("about.html")

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
@user_login_required
def initiate_upload():
    """
    Initiates a direct upload by generating a Pre-Authenticated Request URL.
    """
    logging.info(f"[/api/initiate-upload] - Received request from {request.remote_addr}")
    data = request.get_json()
    logging.info(f"[/api/initiate-upload] - Request data: {data}")
    filename = data.get("filename")
    
    if not filename:
        logging.warning("[/api/initiate-upload] - Filename is required but not provided.")
        return jsonify(error="Filename is required."), 400

    # Sanitize filename
    filename = "".join(c for c in filename if c.isalnum() or c in (" ", ".", "_", "-")).strip() or "file"
    object_name = f"{secrets.token_hex(8)}_{filename}"
    logging.info(f"[/api/initiate-upload] - Sanitized filename: {filename}, Object name: {object_name}")

    # Always use the direct upload flow
    logging.info(f"[/api/initiate-upload] - Starting direct upload for {object_name}")
    par_url = oci_generate_upload_par(app, object_name) # Pass app
    if not par_url:
        logging.error(f"[/api/initiate-upload] - Failed to generate direct upload PAR for object: {object_name}")
        return jsonify(error="Could not create a secure upload link."), 500
    
    logging.info(f"[/api/initiate-upload] - Initiated direct upload for {object_name}")
    response_data = {
        "upload_type": "direct",
        "par_url": par_url,
        "object_name": object_name
    }
    logging.info(f"[/api/initiate-upload] - Sending response: {response_data}")
    return jsonify(response_data)



@app.route("/api/finalize-upload", methods=["POST"])
@user_login_required
def finalize_upload():
    logging.info(f"[/api/finalize-upload] - Received request from {request.remote_addr}")
    data = request.get_json()
    # Avoid logging PIN
    logged_data = {k: v for k, v in data.items() if k != 'pin'}
    logging.info(f"[/api/finalize-upload] - Request data: {logged_data}")
    pin = data.get("pin")
    original_filename = data.get("original_filename")
    object_name = data.get("object_name")
    size_bytes = data.get("size_bytes")
    sharing_message = data.get("sharing_message") # Retrieve sharing message
    city = data.get("city") # Retrieve city
    country = data.get("country") # Retrieve country

    if not all([pin, original_filename, object_name, isinstance(size_bytes, int)]):
        logging.warning("[/api/finalize-upload] - Missing required data for finalization.")
        return jsonify(error="Missing required data for finalization."), 400
    if len(pin) < 4:
        logging.warning("[/api/finalize-upload] - Security phrase too short.")
        return jsonify(error="Security phrase must be at least 4 characters."), 400

    logging.info(f"[/api/finalize-upload] - Finalizing PAR-based upload for {object_name}. Client is expected to have committed.")

    # --- Record file in DB and create share link ---
    logging.info(f"[/api/finalize-upload] - Recording file '{object_name}' in database.")
    pin_hash = hash_pin(pin)
    created = iso_now_utc()
    expiry = (datetime.now(timezone.utc) + timedelta(days=app.config["FILE_EXPIRY_DAYS"])).isoformat()
    uploader_email = session.get('email') # Get email from session if Google user is logged in

    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            INSERT INTO files
                (original_filename, object_name, pin_hash, created_at, expiry_date, max_downloads, download_count, size_bytes, user_email, sharing_message, city, country)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (original_filename, object_name, pin_hash, created, expiry, app.config["MAX_DOWNLOADS"], 0, size_bytes, uploader_email, sharing_message, city, country))
        file_id = cur.lastrowid
        token = secrets.token_urlsafe(16)
        cur.execute("INSERT INTO share_links (token, file_id) VALUES (?, ?)", (token, file_id))
        db.commit()

        share_url = f"{app.config['APP_HOST']}{url_for('share_gate', token=token)}"
        logging.info(f"[/api/finalize-upload] - Successfully finalized {object_name} (size: {size_bytes} bytes).")
        
        response_data = {
            "share_url": share_url,
            "filename": original_filename,
            "expiry": expiry,
            "expiry_pretty": pretty_remaining(expiry)
        }
        logging.info(f"[/api/finalize-upload] - Sending response: {response_data}")
        return jsonify(response_data)
    except sqlite3.IntegrityError:
        logging.warning(f"[/api/finalize-upload] - IntegrityError on finalize, likely duplicate: {object_name}")
        return jsonify(error="This file may have already been finalized."), 409
    except Exception as e:
        logging.exception(f"[/api/finalize-upload] - DB error during finalization: {e}")
        db.rollback()
        return jsonify(error="An internal error occurred during finalization."), 500

@app.route("/api/abort-upload", methods=["POST"])
@user_login_required
def abort_upload():
    """
    Aborts a multipart upload.
    - In 'par' flow, this is a no-op on the server, as the client is responsible
      for canceling. The client should issue a DELETE request to the PAR URL.
    """
    data = request.get_json()
    object_name = data.get("object_name")

    if not object_name:
        return jsonify(error="object_name is required."), 400

    logging.info(f"Received abort request for PAR upload on object '{object_name}'. "
                 "This is a client-side responsibility. No server action taken.")
    return jsonify(status="client_responsibility")

@app.route("/admin/cleanup", methods=["POST"])
@admin_login_required
def admin_cleanup_files():
    data = request.get_json()
    file_ids = data.get("file_ids", [])
    object_names = data.get("object_names", []) # For orphaned files

    if not file_ids and not object_names:
        return jsonify(error="Either file_ids or object_names is required."), 400

    db = get_db()
    
    # Get object names for all file_ids provided
    files_from_db = []
    if file_ids:
        placeholders = ",".join("?" for _ in file_ids)
        files_from_db = db.execute(f"SELECT id, object_name FROM files WHERE id IN ({placeholders})", file_ids).fetchall()
    
    results = {
        "success": [], "failed_db": [], "failed_oci": [], "failed_both": []
    }

    def delete_db_record(app, file_id):
        # This function is thread-safe because it creates its own connection
        with app.app_context():
            try:
                con = sqlite3.connect(app.config["SQLITE_DB"])
                cur = con.cursor()
                cur.execute("DELETE FROM share_links WHERE file_id = ?", (file_id,))
                cur.execute("DELETE FROM files WHERE id = ?", (file_id,))
                con.commit()
                con.close()
                logging.info(f"Successfully deleted DB records for file_id {file_id}")
                return True
            except Exception as e:
                logging.exception(f"Database deletion failed for file_id {file_id}: {e}")
                return False

    # Using a dict to track results for each task type (oci, db) per object_name
    # This avoids race conditions on the shared 'results' dict inside the threads
    task_results = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_task = {}

        # --- Submit OCI Deletion Tasks ---
        all_object_names = set(object_names) | set(f['object_name'] for f in files_from_db)
        for name in all_object_names:
            task_results[name] = {"oci": None, "db": None}
            future = executor.submit(oci_delete_object, app, name) # Pass app
            future_to_task[future] = (name, "oci")

        # --- Submit DB Deletion Tasks ---
        for file_info in files_from_db:
            future = executor.submit(delete_db_record, app, file_info["id"]) # Pass app
            future_to_task[future] = (file_info["object_name"], "db")

        # --- Collect Results ---
        for future in concurrent.futures.as_completed(future_to_task):
            name, task_type = future_to_task[future]
            try:
                success = future.result()
                task_results[name][task_type] = success
            except Exception as exc:
                logging.exception(f"Deletion task {name}/{task_type} generated exception: {exc}")
                task_results[name][task_type] = False

    # --- Consolidate Results ---
    db_map = {f['object_name']: f['id'] for f in files_from_db}
    for name, res in task_results.items():
        oci_success = res['oci']
        # If it was never a DB task (orphaned), db result is implicitly successful
        db_success = res['db'] if name in db_map else True
        file_id = db_map.get(name)

        item = {"id": file_id, "object_name": name}
        if oci_success and db_success:
            results["success"].append(item)
        elif oci_success and not db_success:
            results["failed_db"].append(item)
        elif not oci_success and db_success:
            results["failed_oci"].append(item)
        else: # Both failed or one failed and other wasn't applicable but we assume failure
            results["failed_both"].append(item)

    return jsonify(results), 200

@app.route("/share/<token>", methods=["GET"])
def share_gate(token: str):
    db = get_db()
    row = db.execute("""
        SELECT f.id AS file_id, f.original_filename, f.object_name,
               f.expiry_date, f.download_count, f.max_downloads, f.sharing_message
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
        expiry_pretty=pretty_remaining(row["expiry_date"]),
        sharing_message=row["sharing_message"] if row else ""
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
    par_url = oci_generate_par(app, row["object_name"]) # Pass app
    if not par_url:
        logging.error(f"Failed to generate PAR for object: {row['object_name']} for token: {token}")
        flash("Could not generate a secure download link at this time. Please try again later.", "error")
        return redirect(url_for("share_gate", token=token))

    logging.info(f"Redirecting to PAR URL: {par_url} for object: {row['object_name']} (token: {token})")
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

@app.route("/api/file/<int:file_id>/message", methods=["POST"])
@user_login_required
def update_sharing_message(file_id):
    data = request.get_json()
    new_message = data.get("message")
    user_email = session.get("email")

    if new_message is None:
        return jsonify(error="New message is required."), 400

    db = get_db()
    # check if the file belongs to the user
    file = db.execute("SELECT 1 FROM files WHERE id = ? AND user_email = ?", (file_id, user_email)).fetchone()
    if not file:
        return jsonify(error="File not found or access denied."), 404

    db.execute("UPDATE files SET sharing_message = ? WHERE id = ?", (new_message, file_id))
    db.commit()
    return jsonify(success=True, message="Sharing message updated successfully.")

@app.route("/api/file/<int:file_id>/downloads", methods=["POST"])
@user_login_required
def update_max_downloads(file_id):
    data = request.get_json()
    new_max_downloads = data.get("max_downloads")
    user_email = session.get("email")

    try:
        new_max_downloads = int(new_max_downloads)
        if new_max_downloads <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify(error="Invalid value for max downloads. Must be a positive integer."), 400

    db = get_db()
    file = db.execute("SELECT 1 FROM files WHERE id = ? AND user_email = ?", (file_id, user_email)).fetchone()
    if not file:
        return jsonify(error="File not found or access denied."), 404

    db.execute("UPDATE files SET max_downloads = ? WHERE id = ?", (new_max_downloads, file_id))
    db.commit()
    return jsonify(success=True, message="Max downloads updated successfully.")

@app.route("/api/file/<int:file_id>/expiry", methods=["POST"])
@user_login_required
def update_expiry_date(file_id):
    data = request.get_json()
    new_expiry_date_str = data.get("expiry_date")
    user_email = session.get("email")

    if not new_expiry_date_str:
        return jsonify(error="Expiry date is required."), 400

    try:
        # Assuming date is coming in 'YYYY-MM-DD' format and we want to set it to end of day
        new_expiry_date = datetime.strptime(new_expiry_date_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
        if new_expiry_date < datetime.now(timezone.utc):
             return jsonify(error="Expiry date cannot be in the past."), 400
        new_expiry_iso = new_expiry_date.isoformat()
    except ValueError:
        return jsonify(error="Invalid date format. Please use YYYY-MM-DD."), 400

    db = get_db()
    file = db.execute("SELECT 1 FROM files WHERE id = ? AND user_email = ?", (file_id, user_email)).fetchone()
    if not file:
        return jsonify(error="File not found or access denied."), 404

    db.execute("UPDATE files SET expiry_date = ? WHERE id = ?", (new_expiry_iso, file_id))
    db.commit()
    return jsonify(success=True, message="Expiry date updated successfully.")

@app.route("/api/file/<int:file_id>", methods=["DELETE"])
@user_login_required
def delete_file(file_id):
    user_email = session.get("email")
    db = get_db()

    # First, get the object_name to delete from OCI
    file_to_delete = db.execute(
        "SELECT object_name FROM files WHERE id = ? AND user_email = ?",
        (file_id, user_email)
    ).fetchone()

    if not file_to_delete:
        return jsonify(error="File not found or you do not have permission to delete it."), 404

    object_name = file_to_delete["object_name"]

    # Delete from OCI
    if not oci_delete_object(app, object_name):
        # Even if OCI fails, we might want to proceed with DB cleanup,
        # but for now, we'll report an error and stop.
        return jsonify(error="Failed to delete the file from cloud storage."), 500

    # Delete from database (share_links are deleted by cascade)
    try:
        db.execute("DELETE FROM files WHERE id = ?", (file_id,))
        db.commit()
        flash("File deleted successfully.", "success")
        return jsonify(success=True)
    except Exception as e:
        logging.exception(f"Failed to delete file record from database for file_id: {file_id}")
        db.rollback()
        # The file is deleted from OCI but not the DB. This is an inconsistent state.
        # The admin cleanup tool can find this as a 'missing' record.
        return jsonify(error="File deleted from storage, but failed to update the database."), 500

if __name__ == "__main__":
    # For local debugging only. In prod we use gunicorn (see systemd unit).
    app.run(host="0.0.0.0", port=6000, debug=True)
