@echo off
REM Script para exportar banco de dados PostgreSQL do Render
REM Usa pg_dump (requer PostgreSQL client instalado)

set PGPASSWORD=1GJkXP0EOQYis7RA7bfY3PwmB5OtjUX2
set HOST=dpg-d4s4dkeuk2gs73a52mug-a.oregon-postgres.render.com
set PORT=5432
set USER=clinica_db_cxsq_user
set DATABASE=clinica_db_cxsq
set OUTPUT=database_export_%date:~-4,4%%date:~-7,2%%date:~-10,2%_%time:~0,2%%time:~3,2%%time:~6,2%.sql
set OUTPUT=%OUTPUT: =0%

echo ============================================================
echo Exportador de Banco de Dados PostgreSQL
echo ============================================================
echo.
echo Host: %HOST%
echo Database: %DATABASE%
echo Output: %OUTPUT%
echo.

REM Verificar se pg_dump esta disponivel
where pg_dump >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERRO] pg_dump nao encontrado!
    echo.
    echo Instale o PostgreSQL Client:
    echo https://www.postgresql.org/download/windows/
    echo.
    pause
    exit /b 1
)

echo [*] Exportando banco de dados...
echo.

pg_dump -h %HOST% -p %PORT% -U %USER% -d %DATABASE% -F p -f "%OUTPUT%" --verbose

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [OK] Exportacao concluida com sucesso!
    echo Arquivo: %OUTPUT%
    for %%A in ("%OUTPUT%") do echo Tamanho: %%~zA bytes
) else (
    echo.
    echo [ERRO] Falha na exportacao!
)

echo.
pause

