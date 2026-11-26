@echo off
echo ===================================================
echo   AutoKilap - Menjalankan Aplikasi PWA
echo ===================================================

tasklist /fi "imagename eq postgres.exe" 2>nul | find /i "postgres.exe" >nul
if %ERRORLEVEL% NEQ 0 (
    echo [*] Menyiapkan server PostgreSQL...
    if exist "C:\Users\airsu\pgsql\data\postmaster.pid" (
        del /f /q "C:\Users\airsu\pgsql\data\postmaster.pid" >nul 2>&1
    )
    "C:\Users\airsu\pgsql\bin\pg_ctl.exe" -D "C:\Users\airsu\pgsql\data" -l "C:\Users\airsu\pgsql\server.log" start
    timeout /t 2 /nobreak >nul
)

echo [*] Menjalankan server web AutoKilap di http://localhost:5000 ...
python run.py
pause
