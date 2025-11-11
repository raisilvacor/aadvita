#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de migração para atualizar os nomes dos cargos na Diretoria
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
            WHERE type='table' AND name='membro_diretoria'
        """)
        
        if not cursor.fetchone():
            print("Tabela 'membro_diretoria' não existe. Nenhuma migração necessária.")
            conn.close()
            return
        
        # Atualizar os cargos
        updates = [
            ("Primeiro(a) Secretário(a)", "Primeiro Secretário(a)"),
            ("Segundo(a) Secretário(a)", "Segundo Secretário(a)"),
            ("Tesoureiro(a)", "Primeiro Tesoureiro(a)")
        ]
        
        for old_cargo, new_cargo in updates:
            cursor.execute("""
                UPDATE membro_diretoria 
                SET cargo = ? 
                WHERE cargo = ?
            """, (new_cargo, old_cargo))
            affected = cursor.rowcount
            if affected > 0:
                print(f"Atualizado {affected} registro(s): '{old_cargo}' -> '{new_cargo}'")
        
        conn.commit()
        print("Migração de cargos concluída com sucesso!")
        
    except Exception as e:
        conn.rollback()
        print(f"Erro ao atualizar cargos: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()

