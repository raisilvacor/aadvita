#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de migração para adicionar o campo subtitulo à tabela Informativo
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
        # Verificar se a tabela 'informativo' existe
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='informativo'
        """)
        
        if not cursor.fetchone():
            print("Tabela 'informativo' não existe. Nenhuma migração necessária.")
            conn.close()
            return
        
        # Verificar se a coluna 'subtitulo' já existe
        cursor.execute("PRAGMA table_info(informativo)")
        existing_columns = [column[1] for column in cursor.fetchall()]
        
        if 'subtitulo' in existing_columns:
            print("Coluna 'subtitulo' já existe. Nenhuma migração necessária.")
            conn.close()
            return
        
        # Adicionar a coluna subtitulo
        cursor.execute("ALTER TABLE informativo ADD COLUMN subtitulo VARCHAR(300)")
        
        conn.commit()
        print("Coluna 'subtitulo' adicionada com sucesso à tabela 'informativo'!")
        
    except Exception as e:
        conn.rollback()
        print(f"Erro ao adicionar coluna: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()

