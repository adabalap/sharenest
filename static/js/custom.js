// --- Mobile Menu ---
document.addEventListener('DOMContentLoaded', function () {
    const burgerMenu = document.getElementById('burger-menu');
    const navLinks = document.getElementById('nav-links');

    if (burgerMenu) {
        burgerMenu.addEventListener('click', function () {
            if (navLinks) {
                navLinks.classList.toggle('show');
            }
            this.classList.toggle('active');
        });
    }

    // --- PWA Installation ---
    let deferredPrompt;
    const installPrompt = document.getElementById('install-prompt');
    const installBtn = document.getElementById('install-btn');
    const dismissBtn = document.getElementById('install-dismiss-btn');

    window.addEventListener('beforeinstallprompt', (e) => {
        e.preventDefault();
        deferredPrompt = e;
        if (installPrompt) {
            installPrompt.style.display = 'flex';
        }
    });

    if (installBtn) {
        installBtn.addEventListener('click', async () => {
            if (installPrompt) {
                installPrompt.style.display = 'none';
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
            if (installPrompt) {
                installPrompt.style.display = 'none';
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
