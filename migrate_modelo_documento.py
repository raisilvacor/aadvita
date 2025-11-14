#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migração para criar tabela modelo_documento
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
        # Verificar se a tabela já existe
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='modelo_documento'
        """)
        
        if cursor.fetchone():
            print("Tabela 'modelo_documento' já existe. Nenhuma migração necessária.")
            conn.close()
            return
        
        # Criar tabela modelo_documento
        cursor.execute("""
            CREATE TABLE modelo_documento (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome VARCHAR(200) NOT NULL,
                descricao TEXT,
                arquivo VARCHAR(500) NOT NULL,
                nome_arquivo_original VARCHAR(300),
                tamanho_arquivo INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        print("✅ Tabela 'modelo_documento' criada com sucesso!")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro durante a migração: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()

