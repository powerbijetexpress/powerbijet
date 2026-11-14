@echo off
title Servidor DC Bauru - Controle de PDAs e BI
color 0A
cd /d "%~dp0"

:loop
cls
echo ===================================================
echo   INICIANDO SERVIDOR DO CONTROLE DE PDAS & B.I.
echo ===================================================
echo.
echo IP do seu computador na rede: 192.168.0.150
echo.
echo Links para acesso:
echo  - Painel Geral / B.I.:  http://localhost:5000/
echo  - Controle de PDAs:    http://localhost:5000/pda/
echo  - No Tablet / Celular:  http://192.168.0.150:5000/
echo.
echo ===================================================
echo Servidor monitorado com Auto-Recuperacao (Watchdog)
echo Pressione CTRL+C para parar o servidor se necessario.
echo ===================================================
echo.

python app.py

echo.
echo [AVISO] Servidor encerrou ou reiniciou. Reiniciando em 3 segundos...
timeout /t 3 /nobreak >nul
goto loop
