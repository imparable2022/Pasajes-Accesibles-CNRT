@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Instalador de Pasajes Accesibles CNRT

echo.
echo ============================================
echo        INSTALADOR DE PASAJES ACCESIBLES CNRT
echo ============================================
echo.

rem Si el entorno virtual ya existe y funciona, reutilizarlo.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import sys; print(sys.version)" >nul 2>nul
    if not errorlevel 1 (
        echo Se encontro un entorno Python existente.
        goto :install_deps
    )
    echo El entorno virtual existente esta dañado. Se recreara.
    rmdir /s /q ".venv" >nul 2>nul
)

set "PYMODE="
set "PYARG="
set "PYPATH="

rem Preferir versiones con ruedas binarias estables para wxPython.
py -3.12 -c "import struct,sys; sys.exit(0 if struct.calcsize('P') == 8 else 1)" >nul 2>nul
if not errorlevel 1 (
    set "PYMODE=py"
    set "PYARG=-3.12"
    goto :python_found
)

py -3.11 -c "import struct,sys; sys.exit(0 if struct.calcsize('P') == 8 else 1)" >nul 2>nul
if not errorlevel 1 (
    set "PYMODE=py"
    set "PYARG=-3.11"
    goto :python_found
)

py -3.10 -c "import struct,sys; sys.exit(0 if struct.calcsize('P') == 8 else 1)" >nul 2>nul
if not errorlevel 1 (
    set "PYMODE=py"
    set "PYARG=-3.10"
    goto :python_found
)

rem Probar instalaciones habituales por ruta, incluso si py.exe no las registra.
for %%V in (312 311 310) do (
    if exist "%LocalAppData%\Programs\Python\Python%%V\python.exe" (
        "%LocalAppData%\Programs\Python\Python%%V\python.exe" -c "import struct,sys; sys.exit(0 if struct.calcsize('P') == 8 else 1)" >nul 2>nul
        if not errorlevel 1 (
            set "PYPATH=%LocalAppData%\Programs\Python\Python%%V\python.exe"
            goto :python_found
        )
    )
)

rem Probar python.exe del PATH, pero solo si es Python 3.10, 3.11 o 3.12 de 64 bits.
python -c "import struct,sys; sys.exit(0 if (sys.version_info[:2] in ((3,10),(3,11),(3,12)) and struct.calcsize('P') == 8) else 1)" >nul 2>nul
if not errorlevel 1 (
    set "PYMODE=python"
    goto :python_found
)

python3 -c "import struct,sys; sys.exit(0 if (sys.version_info[:2] in ((3,10),(3,11),(3,12)) and struct.calcsize('P') == 8) else 1)" >nul 2>nul
if not errorlevel 1 (
    set "PYMODE=python3"
    goto :python_found
)

echo No se encontro Python 3.10, 3.11 o 3.12 de 64 bits.
echo.

where winget >nul 2>nul
if errorlevel 1 goto :manual_python

echo Se intentara instalar Python 3.11 de 64 bits para el usuario actual mediante winget.
echo No se requieren credenciales de CNRT para esta instalacion.
echo.
winget install --id Python.Python.3.11 -e --scope user --accept-package-agreements --accept-source-agreements --silent
if errorlevel 1 goto :manual_python

rem Tras winget, comprobar tanto el lanzador como la ruta habitual.
py -3.11 -c "import struct,sys; sys.exit(0 if struct.calcsize('P') == 8 else 1)" >nul 2>nul
if not errorlevel 1 (
    set "PYMODE=py"
    set "PYARG=-3.11"
    goto :python_found
)

if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
    "%LocalAppData%\Programs\Python\Python311\python.exe" -c "import struct,sys; sys.exit(0 if struct.calcsize('P') == 8 else 1)" >nul 2>nul
    if not errorlevel 1 (
        set "PYPATH=%LocalAppData%\Programs\Python\Python311\python.exe"
        goto :python_found
    )
)

goto :manual_python

:python_found
echo Python compatible encontrado.
echo Creando entorno virtual...
if defined PYPATH (
    "%PYPATH%" -m venv .venv
) else (
    %PYMODE% %PYARG% -m venv .venv
)
if errorlevel 1 goto :error

goto :install_deps

:install_deps
echo.
echo Instalando dependencias de Python...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :error
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo.
echo Instalando Chromium para Playwright...
".venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 goto :error

echo.
echo ============================================
echo        INSTALACION COMPLETADA
echo ============================================
echo.
echo Ejecute ejecutar.bat para abrir Pasajes Accesibles CNRT.
pause
exit /b 0

:manual_python
echo.
echo No fue posible instalar Python automaticamente.
echo Instale Python 3.11 de 64 bits y vuelva a ejecutar instalar.bat.
echo Se abrira la pagina oficial de descargas de Python.
start "" "https://www.python.org/downloads/windows/"
pause
exit /b 1

:error
echo.
echo La instalacion no pudo completarse. Revise los mensajes anteriores.
echo Si el error menciona wxPython, pip o Playwright, copie ese mensaje completo.
pause
exit /b 1
