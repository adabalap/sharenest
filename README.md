# ShareNest: Secure & Scalable File Sharing

## ✨ Overview

ShareNest is an innovative, open-source web application designed for secure and efficient file sharing. Leveraging the power of modern cloud infrastructure, it offers users a reliable platform to upload, protect, and distribute files with complete control over access and longevity. Whether for personal use, collaborative projects, or business needs, ShareNest redefines digital sharing with a focus on security, performance, and user experience.

## 🚀 Key Features

*   **Secure File Uploads:** Easily upload any file type, protected by robust backend security measures.
*   **PIN Protection:** Add an extra layer of security with a unique security phrase (PIN) for each shared file.
*   **Time-Limited Shares:** Grant temporary access by setting an expiration date for your shared links.
*   **Download Limits:** Control usage by specifying the maximum number of times a file can be downloaded.
*   **Modern, Responsive UI:** Enjoy a seamless and intuitive experience across all devices, from desktops to smartphones.
*   **Automated Cleanup:** Our intelligent system automatically removes expired or fully downloaded files, ensuring data hygiene and efficient storage.
*   **Blazing Fast Downloads:** Powered by OCI's global network, experience rapid and reliable file retrieval.

## 💡 Our Vision & Open Source Philosophy

ShareNest is built on the principles of open collaboration and transparency. We believe in providing powerful, secure tools that are accessible and auditable by everyone. Our open-source model fosters innovation, allowing developers worldwide to inspect, improve, and extend ShareNest, ensuring its continuous evolution and adaptation to emerging needs. Join us in building a more secure and open digital ecosystem.

## 👥 For Users

Getting started with ShareNest is straightforward:

1.  **Upload Your File:** Select the file you wish to share.
2.  **Set Your Terms:** Optionally, add a PIN, set an expiration date, or limit the number of downloads.
3.  **Share the Link:** Receive a unique, secure link to distribute to your recipients.

**What to Expect:**
*   **Privacy First:** Your files are protected with robust security features and strict access controls.
*   **Full Control:** You decide who accesses your files, when, and how often.
*   **Performance:** Enjoy fast uploads and downloads, backed by Oracle Cloud Infrastructure.

## 🛠️ For Developers

ShareNest offers a fascinating case study in modern web application development and cloud integration. Dive into its architecture, contribute to its evolution, or adapt it for your own specific needs.

### Technology Stack

*   **Backend:** Python, Flask (lightweight, powerful micro-framework)
*   **Frontend:** HTML, CSS, JavaScript (modern, responsive web standards)
*   **WSGI Server:** Gunicorn (production-ready Python WSGI HTTP server)
*   **Database:** SQLite (lightweight and efficient for local storage, easily adaptable to PostgreSQL/MySQL)
*   **File Storage:** Oracle Cloud Infrastructure (OCI) Object Storage (scalable, secure, cost-effective cloud storage)
*   **Dependencies:** Managed via `pip` and `requirements.txt`

### Architecture Highlights

ShareNest's architecture prioritizes performance, scalability, and security, especially concerning file handling:

*   **Direct-to-OCI Uploads (PAR & SDK Flows):**
    *   **Reduced Server Load:** Files are uploaded directly from the client to OCI Object Storage, completely bypassing the ShareNest application server. This significantly reduces server resource consumption and boosts performance.
    *   **Enhanced Scalability:** Our server-less upload mechanism ensures that the application scales effortlessly, regardless of the number or size of concurrent uploads.
    *   **PAR Flow:** Utilizes OCI Pre-Authenticated Requests for direct, secure, and temporary write access for all file sizes. Simple and highly efficient.
    *   **SDK Flow (Multipart Uploads):** For very large files, this robust flow enables client-side chunking, parallel uploads, and retries, enhancing reliability and speed for enterprise-grade transfers.
*   **Secure Download Links:** Files are retrieved via secure, short-lived Pre-Authenticated Request (PAR) URLs, ensuring that access is tightly controlled and temporary.
*   **Modular Design:** A clean separation between frontend, backend APIs, and storage logic facilitates easy maintenance and future enhancements.

### Getting Started

Refer to the **Installation and Setup** and **Running the Application** sections below for detailed instructions on how to get ShareNest up and running in your development environment or production setup.

### Contributing

We welcome contributions from the community! Whether it's bug reports, feature requests, documentation improvements, or code contributions, every effort helps make ShareNest better. Please refer to our `CONTRIBUTING.md` (to be created) for guidelines.

## 💰 For Sponsors

ShareNest represents an opportunity to support an innovative open-source project with tangible real-world utility. Your sponsorship directly contributes to:

*   **Continued Innovation:** Funding for new features, security enhancements, and architectural improvements.
*   **Community Growth:** Resources for developer outreach, documentation, and support.
*   **Infrastructure:** Covering the costs associated with cloud services, testing, and deployment.

**Why Sponsor ShareNest?**
*   **Visibility:** Align your brand with a cutting-edge, open-source solution trusted for secure file sharing.
*   **Impact:** Directly influence the development roadmap and address critical needs in digital privacy and data control.
*   **Talent:** Engage with a vibrant community of developers and enthusiasts.

Join us in empowering secure and open digital interactions. Contact us at [your-contact-email@example.com] to discuss sponsorship opportunities.

## ⚙️ Administration & Operations

For administrators, ShareNest is designed for low-maintenance operation:

*   **Automated Cleanup:** The `cleanup_expired.py` script (recommended to run as a cron job) handles the removal of expired files, optimizing storage and database performance.
*   **OCI Lifecycle Policies:** Configure OCI Object Storage lifecycle policies to automatically manage uncommitted multipart uploads, preventing orphaned data and controlling costs.

## 🤝 Community & Support

*   **Issues:** Report bugs or suggest features on our [GitHub Issues page](link-to-github-issues).
*   **Discussions:** Join the conversation on our [GitHub Discussions page](link-to-github-discussions) (if applicable).

## 📝 License

ShareNest is released under the [MIT License](link-to-license-file). See the `LICENSE` file for more details.

---

## Technology Stack (Detailed)

-   **Backend:** Python, Flask
-   **Frontend:** HTML, CSS, JavaScript
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
python3 app.py
```
The application will be available at `http://0.0.0.0:6000`.

### For Production

For production, it is recommended to use a production-ready WSGI server like Gunicorn:
```bash
gunicorn --workers 3 --bind 0.0.0.0:6000 app:app
```

## Upload Architecture (Detailed)

ShareNest supports two primary upload flows, controlled by the `UPLOAD_FLOW` environment variable on the server:

1.  **`par` (default):** Direct-to-OCI uploads using Pre-Authenticated Requests (PARs).
2.  **`sdk`:** A hybrid approach where large files are uploaded in parts using the OCI SDK, while smaller files still use the `par` flow.

### `par` Flow (Default)

This is the simplest and most direct method. It offloads the entire upload process from the application server directly to OCI Object Storage.

-   **How it works:**
    1.  When a user initiates an upload, the web client sends a request to the ShareNest API (`/api/initiate-upload`).
    2.  The application server does **not** receive the file. Instead, it communicates with OCI to generate a secure, short-lived **Pre-Authenticated Request (PAR)**. This PAR grants temporary write-only permission for a specific, unique object name in the OCI bucket.
    3.  The API returns this PAR URL to the client.
    4.  The client then uploads the file **directly to the PAR URL**, completely bypassing the ShareNest server. This applies to all files, regardless of size.
    5.  Once the upload to OCI is complete, the client sends a final request to the ShareNest API (`/api/finalize-upload`) to register the file's metadata (original name, PIN, size, etc.) in the application database and create the share link.

### `sdk` Flow

This flow is designed for more robust handling of large files by breaking them into smaller chunks and uploading them in parallel.

-   **How it works:**
    1.  The client initiates an upload by calling `/api/initiate-upload`.
    2.  The server checks the file size:
        -   **If the file is small** (below `MULTIPART_THRESHOLD_MB`), it behaves exactly like the `par` flow, returning a direct upload PAR URL.
        -   **If the file is large,** the server uses the OCI SDK to create a **multipart upload session** and returns a unique `upload_id` to the client.
    3.  The client is now responsible for:
        -   Splitting the file into parts of size `MULTIPART_PART_SIZE_MB`.
        -   Making a `PUT` request for each part to the OCI object storage endpoint, including the `upload_id` and part number. These requests can be made concurrently to improve speed.
        -   Collecting the `ETag` header from the response of each successful part upload.
    4.  After all parts are uploaded, the client calls `/api/finalize-upload` with the `upload_id` and a list of all part numbers and their corresponding `ETag`s.
    5.  The server then uses the OCI SDK to send a "commit" command, which tells OCI to assemble the parts into a single object.
    6.  Finally, the server registers the file in the database and returns the share link.

#### Advantages of `sdk` Flow

-   **Resilience:** Failed parts can be retried individually without re-uploading the entire file.
-   **Parallelism:** Multiple parts can be uploaded concurrently, significantly speeding up the transfer of large files.
-   **No PAR Management:** The client does not need to handle PAR URLs for multipart uploads.

#### Advantages of `par` Flow

-   **Simplicity:** The client-side implementation is simpler, as it only needs to perform a single `PUT` request.
-   **Efficiency for Small Files:** For small files, the overhead of creating a multipart upload session is unnecessary.

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

## Client-Side Implementation (Detailed)

The client-side implementation is responsible for handling the file upload process, including chunking, concurrency, and error handling.

### Upload Flow

The application supports two upload flows, controlled by the `UPLOAD_FLOW` environment variable on the server:

-   `par` (default): The client uses Pre-Authenticated Requests (PARs) for all uploads.
-   `sdk`: The client uses the OCI SDK for multipart uploads.

The client should be designed to handle both flows based on the response from the `/api/initiate-upload` endpoint.

### Concurrency

For multipart uploads, the client should use a promise-pool to manage concurrent part uploads. A recommended concurrency level is between 6 and 8.

### Retries

The client should implement a retry mechanism with exponential backoff and jitter for failed part uploads (i.e., HTTP status codes 429 or 5xx). A recommended number of retries is between 3 and 5.

### Structured Logging

The client should log the following information for each upload:

```json
{
  "upload_flow": "par" | "sdk",
  "object_name": "...",
  "upload_id": "...",
  "part_count": 123,
  "part_size_bytes": 123456,
  "concurrency": 8,
  "elapsed_ms": 123456,
  "mbps": 123.45,
  "commit_status": "success" | "failure",
  "abort_reason": "..."
}
```

## Lifecycle Policy

It is recommended to configure an Object Lifecycle Policy on your OCI bucket to automatically purge uncommitted multipart uploads after a certain number of days. This will help to keep your bucket clean and reduce storage costs.

Note that there may be a lag between when the lifecycle rule is triggered and when the object is actually deleted from the bucket.