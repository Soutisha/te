@echo off
REM AUTONEXUS AI 2.0 - Windows launcher. Run from this folder.
if not exist .venv ( py -m venv .venv )
call .venv\Scripts\activate
pip install -r requirements.txt
if not exist .env ( copy .env.example .env & echo Edit .env: set JWT_SECRET ^(32+ chars^), OWNER_EMAIL, OWNER_PASSWORD_HASH & pause & exit /b 1 )
python -m uvicorn autonexus.api:app --host 127.0.0.1 --port 8765 --reload
REM Open http://127.0.0.1:8765/
