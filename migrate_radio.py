#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de migração para adicionar a tabela RadioPrograma
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
        # Verificar se a tabela 'radio_programa' já existe
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='radio_programa'
        """)
        
        if cursor.fetchone():
            print("Tabela 'radio_programa' já existe. Nenhuma migração necessária.")
            conn.close()
            return
        
        # Criar a tabela radio_programa
        cursor.execute("""
            CREATE TABLE radio_programa (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                nome VARCHAR(200) NOT NULL,
                descricao TEXT,
                apresentador VARCHAR(200),
                horario VARCHAR(100),
                url_streaming VARCHAR(500),
                url_arquivo VARCHAR(500),
                imagem VARCHAR(300),
                ativo BOOLEAN DEFAULT 1,
                ordem INTEGER DEFAULT 0,
                created_at DATETIME,
                updated_at DATETIME
            )
        """)
        
        conn.commit()
        print("Tabela 'radio_programa' criada com sucesso!")
        
    except Exception as e:
        conn.rollback()
        print(f"Erro ao criar tabela: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()

