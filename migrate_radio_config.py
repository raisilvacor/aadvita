#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de migração para adicionar a tabela RadioConfig
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
        # Verificar se a tabela 'radio_config' já existe
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='radio_config'
        """)
        
        if cursor.fetchone():
            print("Tabela 'radio_config' já existe. Nenhuma migração necessária.")
            # Verificar se já existe uma configuração
            cursor.execute("SELECT COUNT(*) FROM radio_config")
            count = cursor.fetchone()[0]
            if count == 0:
                # Inserir configuração padrão
                cursor.execute("""
                    INSERT INTO radio_config (url_streaming_principal, created_at, updated_at)
                    VALUES (?, datetime('now'), datetime('now'))
                """, ('https://stream.zeno.fm/tngw1dzf8zquv',))
                conn.commit()
                print("Configuração padrão da rádio inserida.")
            conn.close()
            return
        
        # Criar a tabela radio_config
        cursor.execute("""
            CREATE TABLE radio_config (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                url_streaming_principal VARCHAR(500),
                created_at DATETIME,
                updated_at DATETIME
            )
        """)
        
        # Inserir configuração padrão
        cursor.execute("""
            INSERT INTO radio_config (url_streaming_principal, created_at, updated_at)
            VALUES (?, datetime('now'), datetime('now'))
        """, ('https://stream.zeno.fm/tngw1dzf8zquv',))
        
        conn.commit()
        print("Tabela 'radio_config' criada com sucesso!")
        print("Configuração padrão da rádio inserida.")
        
    except Exception as e:
        conn.rollback()
        print(f"Erro ao criar tabela: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()

