@echo off
echo ===================================================
echo   Menghentikan PostgreSQL Server
echo ===================================================
"C:\Users\airsu\pgsql\bin\pg_ctl.exe" -D "C:\Users\airsu\pgsql\data" stop
pause
