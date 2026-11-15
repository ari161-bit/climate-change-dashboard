@echo off
rem Horizontal scaling: start N identical EarthScape app instances (Waitress WSGI server)
rem on ports 8001..800N. Apache (deploy\apache-earthscape.conf) load-balances across them.
rem Usage:  deploy\run_instances.cmd 3
setlocal
set N=%1
if "%N%"=="" set N=3
cd /d "%~dp0.."
set EARTHSCAPE_DEBUG=0
set EARTHSCAPE_HTTPS=1
set EARTHSCAPE_ALLOWED_HOSTS=127.0.0.1,localhost,earthscape.local
python manage.py collectstatic --noinput >nul
for /L %%i in (1,1,%N%) do (
  start "EarthScape instance 800%%i" cmd /k waitress-serve --listen=127.0.0.1:800%%i --threads=8 mysite.wsgi:application
)
echo Started %N% instances on ports 8001-800%N%. Health check: http://127.0.0.1:8001/climatechanges/api/health/
endlocal
