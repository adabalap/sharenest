# ShareNest

ShareNest is a simple and secure web application for sharing files. It allows users to upload files, protect them with a security phrase (PIN), and share them via a unique link. Each shared file has a configurable expiration date and a maximum number of downloads.

The application is built with Python and Flask, and it uses Oracle Cloud Infrastructure (OCI) Object Storage for robust and scalable file storage.

## Features

-   **Secure File Upload:** Upload files to be shared.
-   **PIN Protection:** Secure each file with a security phrase.
-   **Time-Limited Shares:** Set an expiration date for each shared link.
-   **Download Limits:** Limit the number of times a file can be downloaded.
-   **OCI Object Storage Integration:** Files are stored securely in an OCI bucket.
-   **Short-Lived Download Links:** Generates secure, short-lived Pre-Authenticated Request (PAR) URLs for downloads.
-   **Large File Support:** Handles both small (streamed) and large (direct-to-OCI) file uploads.
-   **Simple Web Interface:** A clean and simple UI for uploading and downloading files.

## Technology Stack

-   **Backend:** Python, Flask
-   **WSGI Server:** Gunicorn
-   **Database:** SQLite
-   **File Storage:** Oracle Cloud Infrastructure (OCI) Object Storage
-   **Dependencies:** See `requirements.txt`

## Prerequisites

-   Python 3.8+
-   An Oracle Cloud Infrastructure (OCI) account with an Object Storage bucket.
-   OCI API credentials configured on the machine where the app is running.

## Installation and Setup

1.  **Clone the repository (if you haven't already):**
    ```bash
    git clone <repository-url>
    cd sharenest
    ```

2.  **Create a Python virtual environment and activate it:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install the required Python packages:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure the application:**
    Copy the example environment file and edit it with your specific configuration.
    ```bash
    cp .env.example .env
    ```
    Now, open `.env` and fill in the required values, especially the OCI configuration details and a strong `SECRET_KEY` and `PIN_SALT`.

    **OCI Configuration in `.env`:**
    -   `OCI_TENANCY_OCID`: The OCID of your OCI tenancy.
    -   `OCI_USER_OCID`: The OCID of the user that has permissions to access the bucket.
    -   `OCI_FINGERPRINT`: The fingerprint of the API key.
    -   `OCI_PRIVATE_KEY_PATH`: The absolute path to the OCI private key file (e.g., `~/.oci/oci_api_key.pem`).
    -   `OCI_REGION`: The OCI region where your bucket is located (e.g., `us-ashburn-1`).
    -   `OCI_NAMESPACE`: Your OCI object storage namespace.
    -   `OCI_BUCKET_NAME`: The name of the OCI bucket to store files in.

5.  **Database Initialization:**
    The SQLite database (`sharenest.db`) and its tables will be created automatically when you first run the application.

## Running the Application

### For Development

You can run the Flask development server for testing and development:
```bash
python app.py
```
The application will be available at `http://0.0.0.0:6000`.

### For Production

For production, it is recommended to use a production-ready WSGI server like Gunicorn:
```bash
gunicorn --workers 3 --bind 0.0.0.0:6000 app:app
```

## Scripts

The project includes several utility scripts:

-   `cleanup_expired.py`: A script to periodically clean up expired files from the database. This should be run as a cron job.
-   `db_setup.py`: Can be used to manually initialize the database.
-   `scripts/setting_secret-key_and_pin-salt.sh`: A helper script to generate and set the `SECRET_KEY` and `PIN_SALT` in your `.env` file.

## API Endpoints

-   `GET /api/health`: A health check endpoint that returns the status of the application.
