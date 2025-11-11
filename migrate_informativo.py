#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de migração para adicionar a tabela Informativo
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
        # Verificar se a tabela 'informativo' já existe
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='informativo'
        """)
        
        if cursor.fetchone():
            print("Tabela 'informativo' já existe. Nenhuma migração necessária.")
            conn.close()
            return
        
        # Criar a tabela informativo
        cursor.execute("""
            CREATE TABLE informativo (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                tipo VARCHAR(50) NOT NULL,
                titulo VARCHAR(200) NOT NULL,
                conteudo TEXT,
                url_soundcloud VARCHAR(500),
                imagem VARCHAR(300),
                data_publicacao DATE NOT NULL,
                created_at DATETIME,
                updated_at DATETIME
            )
        """)
        
        conn.commit()
        print("Tabela 'informativo' criada com sucesso!")
        
    except Exception as e:
        conn.rollback()
        print(f"Erro ao criar tabela: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()

