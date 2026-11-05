@echo off
setlocal

cd /d "%~dp0"
if errorlevel 1 goto error

set "VENV_DIR=%~dp0.venv"
set "PYTHON=%VENV_DIR%\Scripts\python.exe"

:menu
echo.
echo ===============================
echo           Clipstream
echo ===============================
echo 1. Crear instalador y version portable
echo 2. Iniciar la aplicacion de Flet
echo 3. Instalar o actualizar dependencias
echo 4. Salir
echo.
choice /c 1234 /n /m "Selecciona una opcion [1-4]: "
if errorlevel 4 goto end
if errorlevel 3 goto install
if errorlevel 2 goto launch
if errorlevel 1 goto build
goto menu

:build
call :install_dependencies
if errorlevel 1 goto error

call :build_packages
if errorlevel 1 goto error

echo.
echo Instalador y version portable creados en la carpeta dist.
pause
goto menu

:launch
call :install_dependencies
if errorlevel 1 goto error

if not exist "%~dp0main.py" (
    echo Error: no se encontro main.py.
    goto error
)

echo.
echo Iniciando la aplicacion de Flet...
"%PYTHON%" "%~dp0main.py"
if errorlevel 1 goto error
goto menu

:install
call :install_dependencies
if errorlevel 1 goto error
echo.
echo Dependencias instaladas correctamente.
pause
goto menu

:install_dependencies
if not exist "%~dp0requirements.txt" (
    echo Error: no se encontro requirements.txt.
    exit /b 1
)

call :ensure_venv
if errorlevel 1 exit /b 1

echo Comprobando e instalando dependencias si hace falta...
"%PYTHON%" -m pip install --disable-pip-version-check -r "%~dp0requirements.txt"
if errorlevel 1 exit /b 1
exit /b 0

:build_packages
if not exist "%~dp0requirements-build.txt" (
    echo Error: no se encontro requirements-build.txt.
    exit /b 1
)
if not exist "%~dp0installer.iss" (
    echo Error: no se encontro installer.iss.
    exit /b 1
)

call :find_inno_setup
if not defined ISCC (
    where winget >nul 2>nul
    if errorlevel 1 (
        echo Error: instala Inno Setup 6 para crear el instalador.
        echo Descarga: https://jrsoftware.org/isdl.php
        exit /b 1
    )
    echo Se requiere Inno Setup 6 para crear el instalador.
    choice /c SN /n /m "Deseas instalarlo con winget [S/N]? "
    if errorlevel 2 exit /b 1
    winget install --id JRSoftware.InnoSetup --exact --scope user --accept-package-agreements --accept-source-agreements
    if errorlevel 1 exit /b 1
    call :find_inno_setup
    if not defined ISCC (
        echo Error: no se encontro ISCC.exe despues de instalar Inno Setup.
        exit /b 1
    )
)

echo Instalando herramientas de empaquetado...
"%PYTHON%" -m pip install --disable-pip-version-check -r "%~dp0requirements-build.txt"
if errorlevel 1 exit /b 1

if not exist "%~dp0dist\portable" mkdir "%~dp0dist\portable"
if errorlevel 1 exit /b 1
if not exist "%~dp0dist\installer" mkdir "%~dp0dist\installer"
if errorlevel 1 exit /b 1

echo Creando ejecutable portable...
"%VENV_DIR%\Scripts\flet.exe" pack "%~dp0main.py" --name "Clipstream" --product-name "Clipstream" --product-version "1.0.0" --file-version "1.0.0.0" --file-description "Descarga y organiza tus videos" --distpath "%~dp0dist\portable" -y
if errorlevel 1 exit /b 1
if not exist "%~dp0dist\portable\Clipstream.exe" (
    echo Error: no se genero el ejecutable portable.
    exit /b 1
)

echo Creando instalador...
"%ISCC%" /Qp "%~dp0installer.iss"
if errorlevel 1 exit /b 1
if not exist "%~dp0dist\installer\Clipstream-Setup.exe" (
    echo Error: no se genero el instalador.
    exit /b 1
)
exit /b 0

:find_inno_setup
set "ISCC="
where ISCC.exe >nul 2>nul
if not errorlevel 1 set "ISCC=ISCC.exe"
if defined ISCC exit /b 0
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if defined ProgramFiles if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC if defined LOCALAPPDATA if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
exit /b 0

:ensure_venv
if exist "%PYTHON%" (
    "%PYTHON%" -c "import struct,sys; sys.exit(0 if sys.version_info[:2] in ((3,13),(3,12),(3,11),(3,10)) and struct.calcsize('P') == 8 else 1)" >nul 2>nul
    if not errorlevel 1 exit /b 0
    echo El entorno virtual existente no es compatible; se conservara sin cambios.
)

where py >nul 2>nul
if not errorlevel 1 (
    for %%V in (3.13 3.12 3.11 3.10) do (
        py -%%V -c "import struct,sys; sys.exit(0 if sys.version_info[:2] == tuple(map(int,'%%V'.split('.'))) and struct.calcsize('P') == 8 else 1)" >nul 2>nul
        if not errorlevel 1 (
            set "SELECTED_PYTHON=%%V"
            set "PYTHON_CREATOR=py -%%V"
            goto python_selected
        )
    )
)
if defined SELECTED_PYTHON goto python_selected

where python >nul 2>nul
if not errorlevel 1 (
    for /f %%V in ('python -c "import struct,sys; print(f'{sys.version_info.major}.{sys.version_info.minor}') if sys.version_info[:2] in ((3,13),(3,12),(3,11),(3,10)) and struct.calcsize('P') == 8 else sys.exit(1)" 2^>nul') do (
        set "SELECTED_PYTHON=%%V"
        set "PYTHON_CREATOR=python"
    )
)
if defined SELECTED_PYTHON goto python_selected

:install_python
where winget >nul 2>nul
if errorlevel 1 (
    echo Error: se requiere Python 3.10-3.13 de 64 bits para libtorrent.
    echo Instala Python 3.13 y vuelve a iniciar la aplicacion.
    exit /b 1
)
echo No se encontro una version compatible de Python de 64 bits.
choice /c SN /n /m "Deseas instalar Python 3.13 con winget [S/N]? "
if errorlevel 2 exit /b 1
winget install --id Python.Python.3.13 --exact --scope user --accept-package-agreements --accept-source-agreements
if errorlevel 1 exit /b 1
echo Python 3.13 se instalo. Vuelve a abrir run_app.bat para crear el entorno virtual.
exit /b 1

:python_selected
set "PY_TAG=%SELECTED_PYTHON:.=%"
set "VENV_DIR=%~dp0.venv-py%PY_TAG%"
set "PYTHON=%VENV_DIR%\Scripts\python.exe"
set "VENV_SUFFIX=1"

:find_compatible_venv
if not exist "%PYTHON%" goto create_venv
"%PYTHON%" -c "import struct,sys; sys.exit(0 if sys.version_info[:2] == tuple(map(int,'%SELECTED_PYTHON%'.split('.'))) and struct.calcsize('P') == 8 else 1)" >nul 2>nul
if not errorlevel 1 exit /b 0
echo El entorno "%VENV_DIR%" usa otra version; se conservara sin cambios.
set "VENV_DIR=%~dp0.venv-py%PY_TAG%-%VENV_SUFFIX%"
set /a VENV_SUFFIX+=1
set "PYTHON=%VENV_DIR%\Scripts\python.exe"
goto find_compatible_venv

:create_venv
echo Creando entorno virtual con Python %SELECTED_PYTHON%...
%PYTHON_CREATOR% -m venv "%VENV_DIR%"
if errorlevel 1 exit /b 1
if not exist "%PYTHON%" (
    echo Error: no se pudo crear el entorno virtual.
    exit /b 1
)
"%PYTHON%" -c "import struct,sys; sys.exit(0 if sys.version_info[:2] == tuple(map(int,'%SELECTED_PYTHON%'.split('.'))) and struct.calcsize('P') == 8 else 1)" >nul 2>nul
if errorlevel 1 (
    echo Error: el entorno creado no coincide con Python %SELECTED_PYTHON%.
    exit /b 1
)
exit /b 0

:error
echo.
echo No se pudo completar la operacion. Revisa el mensaje anterior.
pause
exit /b 1

:end
exit /b 0
