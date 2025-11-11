#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de migração para adicionar a coluna foto à tabela associado.
"""

import sqlite3
import os
from pathlib import Path

def migrate_associado_foto():
    # Caminhos possíveis do banco de dados
    db_paths = [
        'aadvita.db',
        'instance/aadvita.db'
    ]
    
    db_path = None
    for path in db_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        print("ERRO: Banco de dados nao encontrado!")
        print("   Procurado em:")
        for path in db_paths:
            print(f"   - {path}")
        return False
    
    print(f"Banco de dados encontrado: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Verificar se a coluna já existe
        cursor.execute("PRAGMA table_info(associado)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'foto' in columns:
            print("OK: A coluna 'foto' ja existe na tabela 'associado'.")
            conn.close()
            return True
        
        print("Adicionando coluna 'foto' a tabela 'associado'...")
        
        # Adicionar a coluna foto
        cursor.execute("""
            ALTER TABLE associado 
            ADD COLUMN foto VARCHAR(300)
        """)
        
        conn.commit()
        print("OK: Coluna 'foto' adicionada com sucesso!")
        
        # Verificar se foi adicionada
        cursor.execute("PRAGMA table_info(associado)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'foto' in columns:
            print("OK: Verificacao: Coluna 'foto' confirmada na tabela 'associado'.")
        else:
            print("ERRO: Coluna nao foi adicionada corretamente!")
            conn.close()
            return False
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"ERRO ao migrar banco de dados: {str(e)}")
        if conn:
            conn.close()
        return False
    except Exception as e:
        print(f"ERRO inesperado: {str(e)}")
        if conn:
            conn.close()
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("Migração: Adicionar coluna foto à tabela associado")
    print("=" * 60)
    print()
    
    success = migrate_associado_foto()
    
    print()
    if success:
        print("=" * 60)
        print("OK: Migracao concluida com sucesso!")
        print("=" * 60)
    else:
        print("=" * 60)
        print("ERRO: Migracao falhou!")
        print("=" * 60)

