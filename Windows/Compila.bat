@echo off
rem Crea dist\LTC.exe su un PC Windows (serve Python 3.13 installato e nel PATH).
rem Lanciare dalla cartella principale del progetto: Windows\Compila.bat
rem Gli stessi comandi li esegue GitHub Actions (.github/workflows/windows.yml).

python -m pip install --upgrade pip || exit /b 1
python -m pip install -r requirements.txt pyinstaller || exit /b 1
python -m PyInstaller --noconfirm Windows\LTC.spec || exit /b 1
echo.
echo Fatto: dist\LTC.exe
