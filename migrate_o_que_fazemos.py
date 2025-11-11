#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Migração para criar a tabela o_que_fazemos_servico
"""

import sqlite3
import os

# Verificar se o banco existe
db_paths = [
    'instance/aadvita.db',
    'instance/database.db',
    'aadvita.db'
]

db_path = None
for path in db_paths:
    if os.path.exists(path):
        db_path = path
        break

if not db_path:
    print("Banco de dados não encontrado!")
    exit(1)

print(f"Usando banco de dados: {db_path}")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Verificar se a tabela já existe
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='o_que_fazemos_servico'
    """)
    
    if cursor.fetchone():
        print("Tabela 'o_que_fazemos_servico' já existe. Nenhuma migração necessária.")
    else:
        # Criar tabela
        cursor.execute("""
            CREATE TABLE o_que_fazemos_servico (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                titulo VARCHAR(200) NOT NULL,
                descricao TEXT NOT NULL,
                cor_icone VARCHAR(7) NOT NULL DEFAULT '#3b82f6',
                icone_svg TEXT,
                ordem INTEGER DEFAULT 0,
                coluna INTEGER NOT NULL DEFAULT 1,
                ativo BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        print("Tabela 'o_que_fazemos_servico' criada com sucesso!")
    
    conn.close()
    
except Exception as e:
    print(f"Erro ao criar tabela: {str(e)}")
    exit(1)

