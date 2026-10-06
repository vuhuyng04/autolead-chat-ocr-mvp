@echo off
rem Chạy MVP: tạo venv + cài thư viện nếu chưa có, rồi mở giao diện ở http://127.0.0.1:7860
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3.13 -m venv .venv || python -m venv .venv
  .venv\Scripts\python -m pip install --upgrade pip
  .venv\Scripts\python -m pip install -r requirements.txt
)
set PYTHONIOENCODING=utf-8
.venv\Scripts\python app.py
