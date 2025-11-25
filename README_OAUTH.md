# Google OAuth Configuration for ShareNest

This document provides step-by-step instructions on how to set up Google OAuth for the ShareNest application. This involves configuring a new project in the Google Cloud Console to obtain the necessary Client ID and Client Secret, and setting up authorized redirect URIs.

## Prerequisites

*   A Google Cloud Platform (GCP) account.
*   Access to the Google Cloud Console.
*   Your ShareNest application's accessible URL (e.g., `http://localhost:6000` for local development, or your deployed domain).

## Step-by-Step Configuration

### 1. Create a New Google Cloud Project (if you don't have one)

1.  Go to the [Google Cloud Console](https://console.cloud.google.com/).
2.  In the top-left corner, click the project selector dropdown and then click **"New Project"**.
3.  Enter a **Project name** (e.g., "ShareNest OAuth Project") and click **"CREATE"**.

### 2. Configure the OAuth Consent Screen

The OAuth consent screen is what users see when they are asked to authorize your application.

1.  From the Google Cloud Console, navigate to **APIs & Services > OAuth consent screen**.
2.  Choose the **"User Type"**:
    *   **External:** For applications accessible to any Google user (requires verification by Google).
    *   **Internal:** If your application is only for users within your Google Workspace organization.
    Select **"External"** for a public ShareNest application and click **"CREATE"**.
3.  **OAuth consent screen setup:**
    *   **App name:** Enter a user-facing name for your application (e.g., "ShareNest").
    *   **User support email:** Select your email address.
    *   **Application home page:** Enter your application's home page URL (e.g., `https://your-sharenest-domain.com`).
    *   **Application privacy policy link:** (Required for External) Provide a link to your privacy policy.
    *   **Application terms of service link:** (Optional) Provide a link to your terms of service.
    *   **Authorized domains:** Add your application's domain (e.g., `your-sharenest-domain.com`). For local development, this might not be strictly necessary here, but good practice for deployment.
    *   **Developer contact information:** Enter an email address.
    *   Click **"SAVE AND CONTINUE"**.
4.  **Scopes:** For ShareNest, we primarily need access to the user's email and basic profile information.
    *   Click **"ADD OR REMOVE SCOPES"**.
    *   Select `.../auth/userinfo.email` and `.../auth/userinfo.profile`.
    *   Click **"UPDATE"**.
    *   Click **"SAVE AND CONTINUE"**.
5.  **Test users:** (Only for External user type while in testing phase) Add the Google accounts you will use for testing your OAuth integration. These users will be able to log in to your app without it being verified.
    *   Click **"ADD USERS"** and enter the email addresses.
    *   Click **"SAVE AND CONTINUE"**.
6.  **Summary:** Review your settings and click **"BACK TO DASHBOARD"**.
7.  **Publishing status:** If using "External" user type, you will eventually need to submit your app for verification if you want it to be generally available. For testing, "In production" status with "Test users" is sufficient.

### 3. Create OAuth Client ID Credentials

1.  From the Google Cloud Console, navigate to **APIs & Services > Credentials**.
2.  Click **"+ CREATE CREDENTIALS"** at the top and select **"OAuth client ID"**.
3.  **Application type:** Select **"Web application"**.
4.  **Name:** Give your OAuth client a descriptive name (e.g., "ShareNest Web Client").
5.  **Authorized JavaScript origins:**
    *   Click **"+ ADD URI"**.
    *   Add the origin of your application.
        *   For local development: `http://localhost:6000` (or whatever port your Flask app runs on).
        *   For deployment: `https://your-sharenest-domain.com`
6.  **Authorized redirect URIs:**
    *   This is the URL that Google will redirect to after a user grants or denies permissions. It must match exactly what your application expects.
    *   Click **"+ ADD URI"**.
    *   For local development: `http://localhost:6000/login/google/authorized`
    *   For deployment: `https://your-sharenest-domain.com/login/google/authorized`
    *   **Note:** The `/login/google/authorized` path is specifically what the ShareNest Flask application uses.
7.  Click **"CREATE"**.
8.  A dialog box will appear showing your **Client ID** and **Client Secret**. **Copy these values immediately** as the Client Secret is only shown once.

### 4. Configure ShareNest Environment Variables

Once you have your Client ID and Client Secret, you need to add them to your ShareNest application's `.env` file.

Open or create the `.env` file in your ShareNest project's root directory and add the following:

```
# Google OAuth Credentials
GOOGLE_CLIENT_ID="YOUR_GOOGLE_CLIENT_ID"
GOOGLE_CLIENT_SECRET="YOUR_GOOGLE_CLIENT_SECRET"

# Flask Secret Key for session management (if not already present)
SECRET_KEY="A_VERY_LONG_RANDOM_STRING_FOR_FLASK_SESSION_SECURITY" 
```

*   Replace `"YOUR_GOOGLE_CLIENT_ID"` with the Client ID you obtained from Google Cloud Console.
*   Replace `"YOUR_GOOGLE_CLIENT_SECRET"` with the Client Secret you obtained.
*   Ensure `SECRET_KEY` is a strong, randomly generated string for session security. If you already have one, keep it.

### 5. Restart Your ShareNest Application

After updating the `.env` file, restart your ShareNest Flask application for the changes to take effect.

You should now be able to use Google OAuth for authentication in your ShareNest application.
