# ShareNest: Effortless & Secure File Sharing

ShareNest is a secure, open-source file sharing platform built with Python/Flask and Oracle Cloud Infrastructure (OCI). It allows users to upload files, protect them with a security phrase, and share them via a unique, time-sensitive link with a limited number of downloads.

## ✨ Key Features

*   **Secure File Uploads:** Files are uploaded directly to OCI Object Storage, bypassing the application server for enhanced performance and scalability.
*   **PIN Protection:** Protect your shared files with a security phrase.
*   **Granular Access Control:** Set expiration dates and download limits for each shared link.
*   **Google OAuth Integration:** Authenticate users with their Google accounts for a seamless login experience.
*   **Admin Dashboard:** Manage users and files through a simple admin interface.
*   **Automated Cleanup:** A script is provided to automatically clean up expired files, optimizing storage usage.
*   **Modern, Responsive Interface:** A clean and intuitive user interface that works on all devices.

## 🛠️ Technology Stack

*   **Backend:** Python, Flask
*   **Frontend:** HTML, CSS, JavaScript
*   **WSGI Server:** Gunicorn
*   **Database:** SQLite
*   **File Storage:** Oracle Cloud Infrastructure (OCI) Object Storage
*   **Authentication:** Google OAuth

## 🚀 Getting Started

### Prerequisites

*   Python 3.8+
*   An Oracle Cloud Infrastructure (OCI) account with an Object Storage bucket.
*   A Google Cloud Platform (GCP) account.

### Installation & Configuration

1.  **Clone the repository:**
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
    Now, open `.env` and fill in the required values.

### OCI Configuration

Add your OCI credentials to the `.env` file:

```
OCI_TENANCY_OCID="your_tenancy_ocid"
OCI_USER_OCID="your_user_ocid"
OCI_FINGERPRINT="your_api_key_fingerprint"
OCI_PRIVATE_KEY_PATH="/path/to/your/oci_api_key.pem"
OCI_REGION="your_oci_region"
OCI_NAMESPACE="your_oci_namespace"
OCI_BUCKET_NAME="your_bucket_name"
```

### Google OAuth Configuration

You'll need to create a Google Cloud project and an OAuth 2.0 Client ID to get a `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.

<details>
<summary>Click here for a step-by-step guide to setting up Google OAuth.</summary>

1.  **Create a New Google Cloud Project**
    *   Go to the [Google Cloud Console](https://console.cloud.google.com/).
    *   Click the project selector dropdown and then click **"New Project"**.
    *   Enter a **Project name** (e.g., "ShareNest OAuth") and click **"CREATE"**.

2.  **Configure the OAuth Consent Screen**
    *   Go to **APIs & Services > OAuth consent screen**.
    *   Choose **"External"** as the User Type and click **"CREATE"**.
    *   Fill in the required information (App name, User support email, etc.).
    *   Add the necessary scopes: `.../auth/userinfo.email` and `.../auth/userinfo.profile`.
    *   Add test users if your app is not yet verified.

3.  **Create OAuth Client ID Credentials**
    *   Go to **APIs & Services > Credentials**.
    *   Click **"+ CREATE CREDENTIALS"** and select **"OAuth client ID"**.
    *   Select **"Web application"** as the application type.
    *   Add your application's authorized JavaScript origins and redirect URIs.
        *   For local development, use:
            *   Authorized JavaScript origins: `http://localhost:6000`
            *   Authorized redirect URIs: `http://localhost:6000/login/google/authorized`
        *   For production, replace `http://localhost:6000` with your domain.
    *   Click **"CREATE"** and copy your **Client ID** and **Client Secret**.

</details>

Add your Google OAuth credentials to the `.env` file:
```
GOOGLE_CLIENT_ID="your_google_client_id"
GOOGLE_CLIENT_SECRET="your_google_client_secret"
```

### Admin User

Set the admin username and password in the `.env` file:
```
ADMIN_USER="admin"
ADMIN_PASSWORD="your_secure_password"
```

### Secret Key and PIN Salt

Generate a `SECRET_KEY` and `PIN_SALT` and add them to your `.env` file. You can use the provided script to generate them:
```bash
sh scripts/setting_secret-key_and_pin-salt.sh
```

### Database Initialization

The SQLite database (`sharenest.db`) and its tables will be created automatically when you first run the application.

### Running the Application

#### For Development

You can run the Flask development server for testing and development:
```bash
python3 app.py
```
The application will be available at `http://0.0.0.0:6000`.

#### For Production

For production, it is recommended to use a production-ready WSGI server like Gunicorn:
```bash
gunicorn --workers 3 --bind 0.0.0.0:6000 app:app
```

## ⚙️ Administration & Operations

### Automated Cleanup

The `cleanup_expired.py` script handles the removal of expired files, optimizing storage and database performance. It is recommended to run this as a cron job.
```bash
python3 cleanup_expired.py
```

## 🤝 Contributing

We welcome contributions from the community! Please feel free to submit a pull request or open an issue.

## 📝 License

ShareNest is released under the MIT License.
