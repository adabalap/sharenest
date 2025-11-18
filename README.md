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
-   **Automated File Cleanup:** A script (`cleanup_expired.py`) runs periodically to remove files that have expired or reached their download limit, freeing up storage and keeping the database clean.

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

## Large File Upload Architecture

To efficiently handle files of all sizes, ShareNest uses a dual-path upload strategy. The path taken is determined by the `LARGE_FILE_THRESHOLD_BYTES` setting in the configuration.

### Small File Path (Streaming Upload)

-   **How it works:** Files smaller than the threshold are streamed through the Flask web server directly to OCI Object Storage. The server acts as a proxy, reading the file from the user's request and writing it to OCI in a single operation.
-   **Use Case:** Ideal for small to medium-sized files where the overhead of the server handling the data stream is negligible.

### Large File Path (Direct-to-OCI Upload)

This application is designed to handle very large files (e.g., up to 20GB) with ease. This is achieved by offloading the upload process from the application server directly to OCI.

-   **How it works:**
    1.  When a user initiates an upload for a file larger than the threshold, the web client first sends a request to the ShareNest API (`/api/initiate-upload`).
    2.  The application server does **not** receive the file. Instead, it communicates with OCI to generate a secure, short-lived **Pre-Authenticated Request (PAR)**. This PAR grants temporary write-only permission for a specific, unique object name in the OCI bucket.
    3.  The API returns this PAR URL to the client.
    4.  The client then uploads the large file **directly to the PAR URL**, completely bypassing the ShareNest server.
    5.  Once the upload to OCI is complete, the client sends a final request to the ShareNest API (`/api/finalize-upload`) to register the file's metadata (original name, PIN, size, etc.) in the application database and create the share link.

#### Advantages

-   **Extreme Scalability:** The application server's resources (memory, CPU, network bandwidth) are not consumed by the file transfer. This means the server can handle many concurrent user requests without being bogged down by huge data streams. The upload performance is primarily between the user and OCI's highly optimized infrastructure.
-   **Reduced Server Load:** Memory usage on the server remains low and stable, regardless of whether a user is uploading a 10MB file or a 20GB file. This leads to a more reliable and cost-effective service.
-   **Enhanced Security:** The use of short-lived PARs ensures that the client only has temporary, restricted access to the storage bucket. The main application credentials are never exposed to the client.

#### Bottlenecks and Considerations

-   **Client-Side Network:** The primary bottleneck for large uploads is the user's own internet connection speed and reliability. A slow or unstable connection will result in a slow upload, and a dropped connection may cause the upload to fail.
-   **No Resumable Uploads (Currently):** The current implementation relies on the client's ability to perform the upload in a single, continuous HTTP request. If the connection is interrupted, the user will likely have to restart the upload from the beginning. Implementing a client-side chunking and resumable upload strategy would be a significant improvement for multi-gigabyte files.
-   **Finalization Step:** The final API call to finalize the upload is critical. If the direct upload to OCI succeeds but this final call fails, the file will exist in OCI but will not be accessible through the application (an "orphan" file).

## Scripts

The project includes several utility scripts:

-   `cleanup_expired.py`: A script to periodically clean up expired files from the database. This should be run as a cron job.
-   `db_setup.py`: Can be used to manually initialize the database.
-   `scripts/setting_secret-key_and_pin-salt.sh`: A helper script to generate and set the `SECRET_KEY` and `PIN_SALT` in your `.env` file.

## Testing

To run the test suite, execute the following command:
```bash
python test_app.py
```

## API Endpoints

-   `GET /api/health`: A health check endpoint that returns the status of the application.
