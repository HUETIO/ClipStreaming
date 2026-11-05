@echo off
REM Script para exportar cookies del navegador para yt-dlp
REM Uso: export_cookies.bat [navegador]
REM Navegadores soportados: chrome, firefox, edge, brave, opera, chromium, vivaldi, safari

set BROWSER=%1
if "%BROWSER%"=="" set BROWSER=chrome

echo Exportando cookies de %BROWSER%...
yt-dlp --cookies-from-browser %BROWSER% --cookies cookies.txt "https://vimeo.com"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Cookies exportados exitosamente a cookies.txt
) else (
    echo.
    echo Error al exportar cookies. Verifica que el navegador esté instalado.
)

pause
