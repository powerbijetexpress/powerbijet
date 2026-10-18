@echo off
title Servidor DC Bauru - Controle de PDAs
color 0A
cd /d "%~dp0\.."
echo ===================================================
echo     INICIANDO SERVIDOR DO CONTROLE DE PDAs
echo ===================================================
echo.
echo IP do Computador na rede Wi-Fi: 192.168.0.150
echo.
echo Links de Acesso:
echo   - No Computador:    http://localhost:5000/pda/
echo   - No Tablet/Celular: http://192.168.0.150:5000/pda/
echo.
echo ===================================================
echo.
start "" "http://localhost:5000/pda/"
python app.py
pause

