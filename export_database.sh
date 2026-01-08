#!/bin/bash
# Script para exportar banco de dados PostgreSQL do Render
# Usa pg_dump (requer PostgreSQL client instalado)

export PGPASSWORD=1GJkXP0EOQYis7RA7bfY3PwmB5OtjUX2
HOST=dpg-d4s4dkeuk2gs73a52mug-a.oregon-postgres.render.com
PORT=5432
USER=clinica_db_cxsq_user
DATABASE=clinica_db_cxsq
OUTPUT=database_export_$(date +%Y%m%d_%H%M%S).sql

echo "============================================================"
echo "Exportador de Banco de Dados PostgreSQL"
echo "============================================================"
echo ""
echo "Host: $HOST"
echo "Database: $DATABASE"
echo "Output: $OUTPUT"
echo ""

# Verificar se pg_dump está disponível
if ! command -v pg_dump &> /dev/null; then
    echo "[ERRO] pg_dump não encontrado!"
    echo ""
    echo "Instale o PostgreSQL Client:"
    echo "  Ubuntu/Debian: sudo apt-get install postgresql-client"
    echo "  macOS: brew install postgresql"
    echo "  CentOS/RHEL: sudo yum install postgresql"
    exit 1
fi

echo "[*] Exportando banco de dados..."
echo ""

pg_dump -h "$HOST" -p "$PORT" -U "$USER" -d "$DATABASE" -F p -f "$OUTPUT" --verbose

if [ $? -eq 0 ]; then
    echo ""
    echo "[OK] Exportação concluída com sucesso!"
    echo "Arquivo: $OUTPUT"
    echo "Tamanho: $(du -h "$OUTPUT" | cut -f1)"
else
    echo ""
    echo "[ERRO] Falha na exportação!"
    exit 1
fi

