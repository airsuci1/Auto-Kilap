#!/usr/bin/env bash
# ==============================================================
# Script Setup & Jalankan PostgreSQL AutoKilap (Git Bash / WSL)
# ==============================================================

PG_BIN="/c/Users/airsu/pgsql/bin"
PG_DATA="/c/Users/airsu/pgsql/data"
PG_LOG="/c/Users/airsu/pgsql/server.log"

echo "=== 1. Memulai PostgreSQL Server ==="
"$PG_BIN/pg_ctl.exe" -D "$PG_DATA" -l "$PG_LOG" start
sleep 2

echo "=== 2. Status Server ==="
"$PG_BIN/pg_ctl.exe" -D "$PG_DATA" status

echo "=== 3. Membuat Database 'autokilap' ==="
"$PG_BIN/createdb.exe" -U postgres -p 5432 autokilap 2>/dev/null || true

echo "=== 4. Inisialisasi Skema Tabel & Data Awal ==="
python -c "from database import init_db; init_db(); print('[OK] Database dan tabel berhasil diinisialisasi!')"

echo ""
echo "=== SELESAI ==="
echo "Untuk menjalankan web app, ketik: python run.py"
