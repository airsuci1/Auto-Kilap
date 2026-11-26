#!/usr/bin/env python
import os
import sys
import subprocess
from app import app
from config import Config

def ensure_postgres_active():
    """Memastikan server PostgreSQL native aktif tanpa memblokir thread aplikasi."""
    pg_ctl = r"C:\Users\airsu\pgsql\bin\pg_ctl.exe"
    data_dir = r"C:\Users\airsu\pgsql\data"
    log_file = r"C:\Users\airsu\pgsql\server.log"
    pid_file = os.path.join(data_dir, "postmaster.pid")

    if not (os.path.exists(pg_ctl) and os.path.exists(data_dir)):
        return

    # Check via fast socket probe first (takes < 5ms)
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.2)
    try:
        s.connect(('127.0.0.1', 5432))
        s.close()
        print("[✓] Server PostgreSQL aktif di port 5432.")
        return
    except Exception:
        pass

    # Clean orphaned pid file if server is not actually listening
    if os.path.exists(pid_file):
        try:
            os.remove(pid_file)
        except Exception:
            pass

    print("[*] Memulai server PostgreSQL AutoKilap di latar belakang...")
    try:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        subprocess.Popen(
            [pg_ctl, "-D", data_dir, "-l", log_file, "start"],
            creationflags=flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            close_fds=True
        )
        print("[✓] Perintah start PostgreSQL selesai diproses.")
    except Exception as e:
        print(f"[i] Info startup PostgreSQL: {e}")

if __name__ == '__main__':
    ensure_postgres_active()
    port = int(os.environ.get('PORT', 5000))
    print(f"============================================================")
    print(f"🚗 {Config.APP_NAME} - Sistem Cuci Mobil & Motor Panggilan (PWA)")
    print(f"🌐 Server berjalan di: http://localhost:{port}")
    print(f"👑 Login Admin Default: admin@autokilap.com / password: admin123")
    print(f"👤 Login Customer Demo: customer@example.com / password: user123")
    print(f"📱 Mendukung PWA: Tambah ke Layar Utama di HP Android & iOS")
    print(f"============================================================")
    app.run(host='0.0.0.0', port=port, debug=False)
