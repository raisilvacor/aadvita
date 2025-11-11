#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migração para atualizar banners de 'Apoie' para 'Apoie-nos'
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
            WHERE type='table' AND name='banner'
        """)
        
        if not cursor.fetchone():
            print("Tabela 'banner' não existe. Nenhuma migração necessária.")
            conn.close()
            return
        
        # Verificar se há banners com tipo 'Apoie'
        cursor.execute("SELECT COUNT(*) FROM banner WHERE tipo = 'Apoie'")
        count = cursor.fetchone()[0]
        
        if count == 0:
            print("Nenhum banner com tipo 'Apoie' encontrado. Nenhuma migração necessária.")
            conn.close()
            return
        
        print(f"Encontrados {count} banner(s) com tipo 'Apoie'. Atualizando para 'Apoie-nos'...")
        
        # Atualizar banners de 'Apoie' para 'Apoie-nos'
        cursor.execute("""
            UPDATE banner 
            SET tipo = 'Apoie-nos' 
            WHERE tipo = 'Apoie'
        """)
        
        conn.commit()
        
        print(f"{count} banner(s) atualizado(s) com sucesso de 'Apoie' para 'Apoie-nos'!")
        print("Migração concluída com sucesso!")
        
    except Exception as e:
        conn.rollback()
        print(f"Erro durante a migração: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()

