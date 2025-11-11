#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migração para atualizar apoiadores sem tipo
Define 'Instituição' como padrão para apoiadores que não têm tipo definido
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
        # Verificar se a tabela existe
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='apoiador'
        """)
        
        if not cursor.fetchone():
            print("Tabela 'apoiador' não existe. Nenhuma migração necessária.")
            conn.close()
            return
        
        # Verificar se a coluna tipo existe
        cursor.execute("PRAGMA table_info(apoiador)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'tipo' not in columns:
            print("Coluna 'tipo' não existe na tabela 'apoiador'. Adicionando...")
            cursor.execute("ALTER TABLE apoiador ADD COLUMN tipo VARCHAR(100)")
            conn.commit()
            print("Coluna 'tipo' adicionada com sucesso!")
        
        # Atualizar apoiadores sem tipo
        cursor.execute("""
            UPDATE apoiador 
            SET tipo = 'Instituição' 
            WHERE tipo IS NULL OR tipo = ''
        """)
        
        updated = cursor.rowcount
        conn.commit()
        
        if updated > 0:
            print(f"{updated} apoiador(es) atualizado(s) com tipo padrão 'Instituição'.")
        else:
            print("Todos os apoiadores já possuem tipo definido.")
        
        print("Migração concluída com sucesso!")
        
    except Exception as e:
        conn.rollback()
        print(f"Erro durante a migração: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()

