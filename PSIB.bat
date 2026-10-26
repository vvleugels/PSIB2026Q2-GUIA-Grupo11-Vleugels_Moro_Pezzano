
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Primera ejecucion: instalando el programa. Puede tardar unos minutos...
    py -3.12 -m venv .venv
    if errorlevel 1 (
        echo.
        echo No se pudo crear el entorno. Instala Python 3.12 de 64 bits desde python.org
        echo con "py launcher" y "tcl/tk and IDLE" tildados.
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo Fallo la instalacion de las dependencias. Revisa tu conexion e intenta de nuevo.
        rmdir /s /q .venv
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" gui.py
if errorlevel 1 pause