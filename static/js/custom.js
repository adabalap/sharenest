

    // --- PWA Installation ---
    let deferredPrompt;
    const installPromptElement = document.getElementById('install-prompt');
    let installToast; // Declare a variable for the Bootstrap Toast instance

    // Initialize the Bootstrap Toast if the element exists
    if (installPromptElement) {
        installToast = new bootstrap.Toast(installPromptElement, { autohide: false });
    }

    const installBtn = document.getElementById('install-btn');
    const dismissBtn = document.getElementById('install-dismiss-btn');

    window.addEventListener('beforeinstallprompt', (e) => {
        e.preventDefault();
        deferredPrompt = e;
        // Show the custom install prompt UI
        if (installToast) {
            installToast.show(); // Use Bootstrap's show method
        }
    });

    if (installBtn) {
        installBtn.addEventListener('click', async () => {
            if (installToast) {
                installToast.hide(); // Hide the toast
            }
            if (deferredPrompt) {
                deferredPrompt.prompt();
                const { outcome } = await deferredPrompt.userChoice;
                if (outcome === 'accepted') {
                    console.log('User accepted the install prompt');
                    fetch('/api/track-install', { method: 'POST' });
                } else {
                    console.log('User dismissed the install prompt');
                }
                deferredPrompt = null;
            }
        });
    }

    if (dismissBtn) {
        dismissBtn.addEventListener('click', () => {
            if (installToast) {
                installToast.hide(); // Hide the toast
            }
            deferredPrompt = null;
        });
    }

    // Register Service Worker
    if ('serviceWorker' in navigator) {
        window.addEventListener('load', () => {
            navigator.serviceWorker.register('/sw.js')
                .then(registration => console.log('Service Worker registered!'))
                .catch(err => console.error('Service Worker registration failed: ', err));
        });
    }
});

// --- Generic Copy to Clipboard ---
function copyToClipboard(text, successMessage) {
    navigator.clipboard.writeText(text).then(() => {
        const btn = document.getElementById('copy-btn');
        if (btn) {
            const originalText = btn.textContent;
            btn.textContent = 'Copied!';
            setTimeout(() => { btn.textContent = originalText; }, 2000);
        }
    }).catch(err => {
        console.error('Failed to copy: ', err);
        alert('Failed to copy to clipboard.');
    });
}
