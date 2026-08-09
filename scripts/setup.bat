@echo off
echo ============================================
echo  Social Media Bot - Setup Script
echo ============================================
echo.

if not exist .env (
    echo Creating .env from .env.example...
    copy .env.example .env
    echo.
    echo [!] IMPORTANT: Edit the .env file with your API keys before starting!
    echo     Open .env in any text editor and fill in your tokens.
    echo.
)

echo To run the project:
echo    docker-compose up
echo.
echo To stop:
echo    docker-compose down
echo.
echo After starting, check: http://localhost:8000/health
