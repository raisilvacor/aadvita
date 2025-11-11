#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de migração para adicionar a tabela membro_coordenacao_social
"""

import sqlite3
import os
import sys

def migrate():
    db_path = 'instance/database.db'
    
    if not os.path.exists(db_path):
        print(f"Banco de dados não encontrado em {db_path}")
        print("O banco será criado automaticamente quando o app iniciar.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Verificar se a tabela já existe
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='membro_coordenacao_social'
        """)
        
        if cursor.fetchone():
            print("Tabela 'membro_coordenacao_social' já existe. Nenhuma migração necessária.")
            conn.close()
            return
        
        # Criar a tabela
        cursor.execute("""
            CREATE TABLE membro_coordenacao_social (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                nome_pt VARCHAR(200) NOT NULL,
                nome_es VARCHAR(200),
                nome_en VARCHAR(200),
                foto VARCHAR(500),
                ordem INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        print("Tabela 'membro_coordenacao_social' criada com sucesso!")
        
    except Exception as e:
        conn.rollback()
        print(f"Erro ao criar tabela: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()

