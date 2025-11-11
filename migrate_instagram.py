#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migração para criar a tabela instagram_post
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
            WHERE type='table' AND name='instagram_post'
        """)
        
        if cursor.fetchone():
            print("Tabela 'instagram_post' já existe. Nenhuma migração necessária.")
        else:
            # Criar tabela
            cursor.execute("""
                CREATE TABLE instagram_post (
                    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                    url_instagram VARCHAR(500),
                    imagem_url VARCHAR(500) NOT NULL,
                    legenda TEXT,
                    data_post DATETIME NOT NULL,
                    ordem INTEGER DEFAULT 0,
                    ativo BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
            print("Tabela 'instagram_post' criada com sucesso!")
        
    except Exception as e:
        conn.rollback()
        print(f"Erro ao criar tabela 'instagram_post': {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()

