#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de migração para criar a tabela banner_conteudo
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
        # Verificar se a tabela 'banner_conteudo' já existe
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='banner_conteudo'
        """)
        
        if cursor.fetchone():
            print("Tabela 'banner_conteudo' já existe. Nenhuma migração necessária.")
            conn.close()
            return
        
        # Criar a tabela banner_conteudo
        cursor.execute("""
            CREATE TABLE banner_conteudo (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                banner_id INTEGER NOT NULL,
                titulo VARCHAR(200) NOT NULL,
                conteudo TEXT,
                imagem VARCHAR(300),
                ordem INTEGER DEFAULT 0,
                ativo BOOLEAN DEFAULT 1,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY(banner_id) REFERENCES banner (id)
            )
        """)
        
        conn.commit()
        print("Tabela 'banner_conteudo' criada com sucesso!")
        
    except Exception as e:
        conn.rollback()
        print(f"Erro ao criar tabela 'banner_conteudo': {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()

