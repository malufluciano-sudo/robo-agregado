@echo off
echo.
echo ============================================
echo   ROBO AGREGADO - Metodologia Luciano
echo ============================================
echo.

REM Detectar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERRO: Python nao encontrado. Instale em python.org
    pause
    exit /b 1
)

echo [1/3] Instalando dependencias...
pip install -r requirements.txt --quiet

if errorlevel 1 (
    echo ERRO na instalacao. Verifique a conexao.
    pause
    exit /b 1
)

echo [2/3] Dependencias instaladas com sucesso!
echo [3/3] Iniciando Robo Agregado...
echo.
echo Acesse: http://localhost:8501
echo Pressione CTRL+C para encerrar.
echo.

python -m streamlit run app.py --server.port 8501 --server.headless false

pause
