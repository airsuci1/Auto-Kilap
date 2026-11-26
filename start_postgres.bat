@echo off
echo ===================================================
echo   Memulai PostgreSQL Portable (AutoKilap Server)
echo ===================================================

REM Cek apakah proses postgres sedang berjalan
tasklist /fi "imagename eq postgres.exe" 2>nul | find /i "postgres.exe" >nul
if %ERRORLEVEL% NEQ 0 (
    if exist "C:\Users\airsu\pgsql\data\postmaster.pid" (
        echo [*] Membersihkan postmaster.pid lama...
        del /f /q "C:\Users\airsu\pgsql\data\postmaster.pid" >nul 2>&1
    )
    "C:\Users\airsu\pgsql\bin\pg_ctl.exe" -D "C:\Users\airsu\pgsql\data" -l "C:\Users\airsu\pgsql\server.log" start
    timeout /t 2 /nobreak >nul
)

"C:\Users\airsu\pgsql\bin\pg_ctl.exe" -D "C:\Users\airsu\pgsql\data" status
echo.
echo Server PostgreSQL aktif pada port 5432.
pause
