#!/usr/bin/env python
"""
Script para exportar banco via endpoint da aplicação
Execute este script e depois acesse /admin/export-database no navegador
"""
print("=" * 60)
print("Exportacao via Aplicacao Web")
print("=" * 60)
print()
print("Para exportar o banco de dados:")
print()
print("1. Acesse sua aplicacao no Render")
print("2. Va para: https://seu-site.com/admin/export-database")
print("3. O arquivo SQL sera baixado automaticamente")
print()
print("OU")
print()
print("Execute o script abaixo no servidor Render via console:")
print()
print("python -c \"")
print("from app import app, db;")
print("from sqlalchemy import text;")
print("import sys;")
print("tables = db.engine.table_names();")
print("for t in tables:")
print("    print(f'SELECT * FROM {t};')")
print("\"")
print()
print("=" * 60)

