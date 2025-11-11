#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de migração para adicionar a coluna cargo na tabela membro_coordenacao_social
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
        # Verificar se a coluna já existe
        cursor.execute("PRAGMA table_info(membro_coordenacao_social)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'cargo' in columns:
            print("Coluna 'cargo' já existe na tabela 'membro_coordenacao_social'. Nenhuma migração necessária.")
            conn.close()
            return
        
        # Adicionar a coluna cargo
        cursor.execute("""
            ALTER TABLE membro_coordenacao_social 
            ADD COLUMN cargo VARCHAR(100) NOT NULL DEFAULT 'Membro da Coordenação Social'
        """)
        
        # Atualizar registros existentes para ter o cargo padrão
        cursor.execute("""
            UPDATE membro_coordenacao_social 
            SET cargo = 'Membro da Coordenação Social' 
            WHERE cargo IS NULL OR cargo = ''
        """)
        
        conn.commit()
        print("Coluna 'cargo' adicionada com sucesso na tabela 'membro_coordenacao_social'!")
        print("Registros existentes foram atualizados com o cargo padrão 'Membro da Coordenação Social'.")
        
    except Exception as e:
        conn.rollback()
        print(f"Erro ao adicionar coluna: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()

