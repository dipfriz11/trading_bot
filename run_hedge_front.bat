@echo off
cd /d "%~dp0"
start "" python -m streamlit run hedge_front.py --server.headless true
timeout /t 3 >nul
start http://localhost:8501
exit