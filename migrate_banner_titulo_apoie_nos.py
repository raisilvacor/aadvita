#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migração para atualizar o título do banner de 'Apoie' para 'Apoie-nos'
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
        
        # Verificar se há banner com tipo 'Apoie-nos' e título 'Apoie'
        cursor.execute("""
            SELECT id, titulo FROM banner 
            WHERE tipo = 'Apoie-nos' AND titulo = 'Apoie'
        """)
        banners = cursor.fetchall()
        
        if not banners:
            print("Nenhum banner com tipo 'Apoie-nos' e título 'Apoie' encontrado.")
            # Verificar se há algum banner com tipo 'Apoie-nos'
            cursor.execute("SELECT id, titulo FROM banner WHERE tipo = 'Apoie-nos'")
            banners_apoie_nos = cursor.fetchall()
            if banners_apoie_nos:
                print(f"Banner(s) encontrado(s) com tipo 'Apoie-nos':")
                for banner_id, titulo in banners_apoie_nos:
                    print(f"  - ID: {banner_id}, Título: {titulo}")
            conn.close()
            return
        
        print(f"Encontrados {len(banners)} banner(s) com título 'Apoie'. Atualizando para 'Apoie-nos'...")
        
        # Atualizar título dos banners
        cursor.execute("""
            UPDATE banner 
            SET titulo = 'Apoie-nos' 
            WHERE tipo = 'Apoie-nos' AND titulo = 'Apoie'
        """)
        
        conn.commit()
        
        print(f"{len(banners)} banner(s) atualizado(s) com sucesso! Título alterado de 'Apoie' para 'Apoie-nos'.")
        print("Migração concluída com sucesso!")
        
    except Exception as e:
        conn.rollback()
        print(f"Erro durante a migração: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()

