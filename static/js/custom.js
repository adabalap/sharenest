

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

    // Auto-hide Navbar (Burger Menu)
    const navbarCollapse = document.getElementById('navbarNav');
    const navbarToggler = document.querySelector('.navbar-toggler');
    let autoHideTimer;
    const AUTO_HIDE_DELAY = 5000; // 5 seconds

    function startAutoHideTimer() {
        clearTimeout(autoHideTimer); // Clear any existing timer
        // Check if the navbar is actually shown (Bootstrap adds 'show' class)
        if (navbarCollapse && navbarCollapse.classList.contains('show')) { 
            autoHideTimer = setTimeout(() => {
                const bsCollapse = bootstrap.Collapse.getInstance(navbarCollapse) || new bootstrap.Collapse(navbarCollapse, { toggle: false });
                bsCollapse.hide();
            }, AUTO_HIDE_DELAY);
        }
    }

    function resetAutoHideTimer() {
        clearTimeout(autoHideTimer);
        if (navbarCollapse && navbarCollapse.classList.contains('show')) {
            startAutoHideTimer();
        }
    }

    if (navbarToggler) {
        navbarToggler.addEventListener('click', () => {
            // Use setTimeout to allow Bootstrap to toggle the 'show' class first
            setTimeout(() => {
                if (navbarCollapse.classList.contains('show')) {
                    startAutoHideTimer();
                } else {
                    clearTimeout(autoHideTimer);
                }
            }, 100); 
        });
    }

    if (navbarCollapse) {
        // Reset timer on mouse movement, touch, or keyboard interaction within the open menu
        navbarCollapse.addEventListener('mousemove', resetAutoHideTimer);
        navbarCollapse.addEventListener('touchstart', resetAutoHideTimer);
        navbarCollapse.addEventListener('keydown', resetAutoHideTimer);
        
        // Ensure timer stops if a link is clicked, allowing navigation/menu closing to proceed
        navbarCollapse.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', () => {
                clearTimeout(autoHideTimer);
            });
        });

        // Clear timer if the collapse is hidden by other means (e.g., clicking outside)
        navbarCollapse.addEventListener('hidden.bs.collapse', () => {
            clearTimeout(autoHideTimer);
        });
        // Start timer if the collapse is shown by other means (e.g., keyboard)
        navbarCollapse.addEventListener('shown.bs.collapse', () => {
            startAutoHideTimer();
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
