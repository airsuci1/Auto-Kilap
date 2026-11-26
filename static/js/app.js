// AutoKilap PWA & Global App Scripts

let deferredPrompt = null;

// 1. Service Worker Registration
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/sw.js')
      .then((reg) => {
        console.log('[PWA] Service Worker registered successfully:', reg.scope);
      })
      .catch((err) => {
        console.warn('[PWA] Service Worker registration failed:', err);
      });
  });
}

// 2. PWA Install Prompt Listener
window.addEventListener('beforeinstallprompt', (e) => {
  // Prevent Chrome 67 and earlier from automatically showing the prompt
  e.preventDefault();
  // Stash the event so it can be triggered later.
  deferredPrompt = e;
  console.log('[PWA] beforeinstallprompt event captured');

  // Check if user previously dismissed in this session
  if (!sessionStorage.getItem('pwa_dismissed')) {
    showInstallBanner();
  }
  
  // Also show any in-page manual install buttons
  document.querySelectorAll('.btn-install-pwa').forEach(el => {
    el.classList.remove('hidden');
    el.style.display = 'inline-flex';
  });
});

window.addEventListener('appinstalled', () => {
  console.log('[PWA] App successfully installed!');
  hideInstallBanner();
  deferredPrompt = null;
  showToast('Aplikasi berhasil dipasang di layar utama Anda!', 'success');
});

function showInstallBanner() {
  const banner = document.getElementById('pwaInstallBanner');
  if (banner) {
    banner.classList.remove('hidden');
    banner.style.display = 'flex';
  }
}

function hideInstallBanner() {
  const banner = document.getElementById('pwaInstallBanner');
  if (banner) {
    banner.style.display = 'none';
  }
  sessionStorage.setItem('pwa_dismissed', 'true');
}

function triggerPWAInstall() {
  if (deferredPrompt) {
    deferredPrompt.prompt();
    deferredPrompt.userChoice.then((choiceResult) => {
      if (choiceResult.outcome === 'accepted') {
        console.log('[PWA] User accepted the install prompt');
      } else {
        console.log('[PWA] User dismissed the install prompt');
      }
      deferredPrompt = null;
      hideInstallBanner();
    });
  } else {
    // If iOS Safari or prompt not available
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    if (isIOS) {
      alert('Untuk memasang di iPhone/iPad:\n1. Ketuk ikon "Bagikan" (Share kotak panah ke atas) di menu bawah Safari.\n2. Gulir dan pilih "Tambahkan ke Layar Utama" (Add to Home Screen).');
    } else {
      alert('Untuk memasang aplikasi:\nBuka menu browser (titik 3 di kanan atas) dan pilih "Tambahkan ke Layar Utama" atau "Pasang Aplikasi".');
    }
  }
}

// Global Toast Utility
function showToast(message, type = 'info') {
  const toastContainer = document.getElementById('toastContainer');
  if (!toastContainer) return;

  const toast = document.createElement('div');
  const bgColors = {
    info: 'bg-slate-800 text-white',
    success: 'bg-emerald-600 text-white',
    warning: 'bg-amber-600 text-white',
    error: 'bg-red-600 text-white'
  };

  toast.className = `px-4 py-3 rounded-xl shadow-lg text-sm font-medium transition-all transform duration-300 flex items-center gap-2 ${bgColors[type] || bgColors.info}`;
  toast.innerHTML = `<span>${message}</span>`;
  
  toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(-10px)';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}
