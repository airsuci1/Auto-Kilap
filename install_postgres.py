import os
import sys
import time
import zipfile
import urllib.request
import subprocess

PG_DIR = r"C:\Users\airsu\pgsql"
ZIP_PATH = r"C:\Users\airsu\pgsql_binaries.zip"
DATA_DIR = os.path.join(PG_DIR, "data")
BIN_DIR = os.path.join(PG_DIR, "bin")
DOWNLOAD_URL = "https://get.enterprisedb.com/postgresql/postgresql-16.16-2-windows-x64-binaries.zip"
EXPECTED_SIZE = 378075555

def download_file_resumable(url, dest_path, expected_size=EXPECTED_SIZE):
    print(f"[*] Mengunduh paket resmi PostgreSQL dari:\n    {url}")
    print(f"[*] Menyimpan ke: {dest_path}")

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    for attempt in range(1, 20):
        current_size = os.path.getsize(dest_path) if os.path.exists(dest_path) else 0
        if current_size >= expected_size:
            if zipfile.is_zipfile(dest_path):
                print(f"[✓] File sudah terunduh lengkap dan valid ({current_size / (1024*1024):.1f} MB)!")
                return
            else:
                print("[!] Ukuran file tercapai tapi format zip belum valid, mengulang...")
                os.remove(dest_path)
                current_size = 0

        req_headers = headers.copy()
        if current_size > 0:
            req_headers['Range'] = f"bytes={current_size}-"
            print(f"[*] Melanjutkan unduhan dari byte {current_size} ({current_size / (1024*1024):.1f} MB)... (Percobaan #{attempt})")
        else:
            print(f"[*] Memulai unduhan baru... (Percobaan #{attempt})")

        try:
            req = urllib.request.Request(url, headers=req_headers)
            with urllib.request.urlopen(req, timeout=30) as response:
                mode = 'ab' if current_size > 0 else 'wb'
                chunk_size = 1024 * 512
                downloaded = current_size
                last_print = 0

                with open(dest_path, mode) as out_file:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        out_file.write(chunk)
                        downloaded += len(chunk)

                        if time.time() - last_print > 3:
                            last_print = time.time()
                            percent = (downloaded / expected_size * 100)
                            print(f"    Progress: {downloaded / (1024*1024):.1f} MB / {expected_size / (1024*1024):.1f} MB ({percent:.1f}%)")

            # Check if complete
            if os.path.exists(dest_path) and os.path.getsize(dest_path) >= expected_size:
                if zipfile.is_zipfile(dest_path):
                    print("[✓] Unduhan paket PostgreSQL selesai dan terverifikasi!")
                    return
        except Exception as e:
            print(f"[!] Gangguan koneksi sementara: {e}. Melanjutkan dalam 3 detik...")
            time.sleep(3)

    if not zipfile.is_zipfile(dest_path):
        raise RuntimeError("Gagal mengunduh PostgreSQL secara lengkap.")

def extract_zip(zip_path, extract_dir):
    print(f"[*] Mengekstrak paket zip ke: {extract_dir}")
    os.makedirs(extract_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(r"C:\Users\airsu")
    print("[✓] Ekstraksi selesai!")

def init_postgres_cluster():
    print("[*] Menginisialisasi cluster database PostgreSQL...")
    initdb_exe = os.path.join(BIN_DIR, "initdb.exe")
    if not os.path.exists(initdb_exe):
        raise FileNotFoundError(f"initdb.exe tidak ditemukan di {initdb_exe}")

    if not os.path.exists(DATA_DIR):
        cmd = [
            initdb_exe,
            "-U", "postgres",
            "-E", "UTF8",
            "-D", DATA_DIR,
            "--locale=C",
            "-A", "trust"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print("[!] Initdb error:", res.stderr)
            raise RuntimeError(res.stderr)
        print("[✓] Cluster database berhasil dibuat di:", DATA_DIR)
    else:
        print("[ℹ] Direktori data sudah ada, melewati initdb.")

def start_postgres_server():
    print("[*] Menjalankan server PostgreSQL...")
    pg_ctl_exe = os.path.join(BIN_DIR, "pg_ctl.exe")
    log_file = os.path.join(PG_DIR, "server.log")

    # Check status
    res = subprocess.run([pg_ctl_exe, "-D", DATA_DIR, "status"], capture_output=True, text=True)
    if "is running" in res.stdout:
        print("[✓] Server PostgreSQL sudah aktif berjalan.")
        return

    # Start server
    cmd = [pg_ctl_exe, "-D", DATA_DIR, "-l", log_file, "start"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print(res.stdout)
    time.sleep(3)

    # Verify running
    res = subprocess.run([pg_ctl_exe, "-D", DATA_DIR, "status"], capture_output=True, text=True)
    print(res.stdout)
    if "is running" not in res.stdout:
        raise RuntimeError("Gagal menjalankan server PostgreSQL.")
    print("[✓] Server PostgreSQL sukses berjalan di port 5432!")

def create_autokilap_db_and_schema():
    print("[*] Membuat database 'autokilap'...")
    createdb_exe = os.path.join(BIN_DIR, "createdb.exe")
    psql_exe = os.path.join(BIN_DIR, "psql.exe")

    # Try createdb
    res = subprocess.run([createdb_exe, "-U", "postgres", "-p", "5432", "autokilap"], capture_output=True, text=True)
    if res.returncode == 0:
        print("[✓] Database 'autokilap' berhasil dibuat!")
    else:
        print("[ℹ] Database autokilap:", res.stderr.strip() or "Sudah ada.")

    schema_file = r"D:\PROJECT\Cuci Mobil Panggilan\schema_postgres.sql"
    if os.path.exists(schema_file):
        print("[*] Mengimpor tabel dari schema_postgres.sql...")
        res_psql = subprocess.run([psql_exe, "-U", "postgres", "-d", "autokilap", "-p", "5432", "-f", schema_file], capture_output=True, text=True)
        if res_psql.returncode == 0:
            print("[✓] Skema tabel PostgreSQL berhasil dimuat ke database 'autokilap'!")
        else:
            print("[!] Psql output:", res_psql.stdout or res_psql.stderr)

def add_to_user_path():
    print("[*] Menambahkan binary PostgreSQL ke PATH pengguna...")
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_ALL_ACCESS)
        current_path, _ = winreg.QueryValueEx(key, "Path")
        if BIN_DIR.lower() not in current_path.lower():
            new_path = current_path.rstrip(";") + ";" + BIN_DIR
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
            print("[✓] Path berhasil ditambahkan ke Environment PATH:", BIN_DIR)
        else:
            print("[ℹ] Path sudah terdaftar sebelumnya.")
        winreg.CloseKey(key)
    except Exception as e:
        print("[!] Gagal update PATH registry:", e)

def create_helper_scripts():
    print("[*] Membuat skrip shortcut kontrol server di folder project...")
    proj_dir = r"D:\PROJECT\Cuci Mobil Panggilan"

    start_bat = f"""@echo off
echo [*] Memulai server PostgreSQL AutoKilap...
"{os.path.join(BIN_DIR, 'pg_ctl.exe')}" -D "{DATA_DIR}" -l "{os.path.join(PG_DIR, 'server.log')}" start
echo [✓] PostgreSQL aktif di port 5432.
pause
"""
    with open(os.path.join(proj_dir, "start_postgres.bat"), "w") as f:
        f.write(start_bat)

    stop_bat = f"""@echo off
echo [*] Menghentikan server PostgreSQL...
"{os.path.join(BIN_DIR, 'pg_ctl.exe')}" -D "{DATA_DIR}" stop
echo [✓] PostgreSQL telah dihentikan.
pause
"""
    with open(os.path.join(proj_dir, "stop_postgres.bat"), "w") as f:
        f.write(stop_bat)

    status_bat = f"""@echo off
"{os.path.join(BIN_DIR, 'pg_ctl.exe')}" -D "{DATA_DIR}" status
pause
"""
    with open(os.path.join(proj_dir, "status_postgres.bat"), "w") as f:
        f.write(status_bat)

    print("[✓] Shortcut start_postgres.bat, stop_postgres.bat, dan status_postgres.bat berhasil dibuat.")

if __name__ == "__main__":
    if not os.path.exists(os.path.join(BIN_DIR, "postgres.exe")):
        download_file_resumable(DOWNLOAD_URL, ZIP_PATH, EXPECTED_SIZE)
        extract_zip(ZIP_PATH, r"C:\Users\airsu")

    init_postgres_cluster()
    start_postgres_server()
    create_autokilap_db_and_schema()
    add_to_user_path()
    create_helper_scripts()
    print("\n" + "="*60)
    print("🎉 INSTALASI POSTGRESQL NATIVE BERHASIL 100%!")
    print("="*60)
