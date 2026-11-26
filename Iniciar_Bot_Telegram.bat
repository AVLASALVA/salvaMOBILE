@echo off
title Salva Web - Bot Telegram para iPhone
chcp 65001 >nul
cls
echo ==========================================================
echo    SISTEMA SALVA WEB - BOT TELEGRAM PARA IPHONE
echo ==========================================================
echo.
echo Iniciando conexion con Telegram y Supabase...
echo.

if exist "%TEMP%\python_build\python.exe" (
    "%TEMP%\python_build\python.exe" servidor\telegram_bot.py
) else (
    python servidor\telegram_bot.py
)

if errorlevel 1 (
    echo.
    echo Ocurrio un error al ejecutar el bot.
    echo Verifica tu token en servidor\config.py
)
pause

