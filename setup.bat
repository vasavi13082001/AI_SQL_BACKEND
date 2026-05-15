@echo off
REM Setup script for AI SQL Backend (Windows)

echo Setting up AI SQL Backend...

REM Check Python version
python --version

REM Create virtual environment
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Copy .env file if not exists
if not exist ".env" (
    echo Copying .env.example to .env...
    copy .env.example .env
    echo Please update .env with your configuration
)

REM Create logs directory
if not exist "logs" mkdir logs

echo Setup complete!
echo.
echo Next steps:
echo 1. Update .env with your database configuration
echo 2. Run: python main.py
echo 3. Visit: http://localhost:8000/docs
