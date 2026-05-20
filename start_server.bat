@echo off
echo ========================================
echo   Iniciando servidor ItsComing...
echo ========================================
echo.

cd /d "%~dp0"

:: Activar venv e iniciar Django con Gunicorn
start "Django Backend (Puerto 8001)" cmd /k "call venv\Scripts\activate && gunicorn core.wsgi:application --bind 0.0.0.0:8001 --workers 3 --timeout 120"

timeout /t 3 /nobreak >nul

:: Iniciar Cloudflare Tunnel
echo Iniciando Cloudflare Tunnel...
start "Cloudflare Tunnel" cmd /k "cloudflared tunnel --url http://localhost:8001"

echo.
echo ========================================
echo   Servidor iniciado!
echo   - Backend: http://localhost:8001
echo   - Tunnel: Ver ventana de Cloudflare para la URL publica
echo.
echo   IMPORTANTE: Copia la URL del tunnel (ej: https://abc123.trycloudflare.com)
echo   y usala como VITE_API_URL en Vercel
echo ========================================
pause
