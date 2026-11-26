@echo off
echo ===================================================
echo   Inisialisasi Database AutoKilap di PostgreSQL
echo ===================================================
echo [*] Membuat database autokilap...
"C:\Users\airsu\pgsql\bin\createdb.exe" -U postgres -p 5432 autokilap 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [OK] Database autokilap berhasil dibuat.
) else (
    echo [INFO] Database autokilap sudah ada atau siap digunakan.
)

echo [*] Menyiapkan tabel dan data awal melalui database.py...
python -c "from database import init_db; init_db(); print('[OK] Skema tabel dan seed data berhasil diinisialisasi!')"

echo.
echo [SELESAI] Database PostgreSQL AutoKilap siap digunakan!
pause
