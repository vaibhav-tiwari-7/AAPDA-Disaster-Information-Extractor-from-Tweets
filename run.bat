@echo off
title AAPDA - Disaster Information Extractor
color 0A

echo.
echo =====================================================
echo        AAPDA - Disaster Information Extractor
echo =====================================================
echo.

:: -------------------------------
:: Check if Python is installed
:: -------------------------------
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or is not added to PATH.
    echo Please install Python 3.10 or later and try again.
    pause
    exit /b
)

:: -------------------------------
:: Create virtual environment
:: -------------------------------
if not exist ".venv" (
    echo [INFO] Creating virtual environment...
    python -m venv .venv

    echo [INFO] Activating virtual environment...
    call .venv\Scripts\activate.bat

    echo [INFO] Installing required packages...
    pip install --upgrade pip
    pip install -r requirements.txt
) else (
    echo [INFO] Using existing virtual environment...
    call .venv\Scripts\activate.bat
)

:: -------------------------------
:: Check Streamlit installation
:: -------------------------------
python -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Streamlit not found. Installing dependencies...
    pip install -r requirements.txt
)

echo.
echo =====================================================
echo Launching Dashboard...
echo =====================================================
echo.
echo Dashboard URL:
echo http://localhost:8501
echo.



streamlit run local_dashboard.py

pause