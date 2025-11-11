#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de migração para adicionar a coluna arquivo_pdf à tabela banner_conteudo
"""

import sqlite3
import os
import sys

def migrate():
    # Tentar diferentes caminhos possíveis
    possible_paths = [
        'instance/aadvita.db',
        'aadvita.db',
        'instance/database.db',
        'database.db'
    ]
    
    db_path = None
    for path in possible_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        print("Banco de dados não encontrado nos caminhos esperados:")
        for path in possible_paths:
            print(f"  - {path}")
        print("O banco será criado automaticamente quando o app iniciar.")
        return
    
    print(f"Usando banco de dados: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Verificar se a tabela 'banner_conteudo' existe
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='banner_conteudo'
        """)
        
        if not cursor.fetchone():
            print("Tabela 'banner_conteudo' não existe. Nenhuma migração necessária.")
            conn.close()
            return
        
        # Verificar se a coluna 'arquivo_pdf' já existe
        cursor.execute("PRAGMA table_info(banner_conteudo)")
        existing_columns = [column[1] for column in cursor.fetchall()]
        
        if 'arquivo_pdf' not in existing_columns:
            cursor.execute("ALTER TABLE banner_conteudo ADD COLUMN arquivo_pdf VARCHAR(300)")
            conn.commit()
            print("Coluna 'arquivo_pdf' adicionada com sucesso à tabela 'banner_conteudo'!")
        else:
            print("Coluna 'arquivo_pdf' já existe na tabela 'banner_conteudo'. Pulando...")
        
    except Exception as e:
        conn.rollback()
        print(f"Erro ao adicionar coluna 'arquivo_pdf': {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()

