#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de migração para criar a tabela dados_associacao.
"""

import sqlite3
import os
from pathlib import Path

def migrate_dados_associacao():
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
        
        # Verificar se a tabela já existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dados_associacao'")
        if cursor.fetchone():
            print("OK: A tabela 'dados_associacao' ja existe.")
            
            # Verificar se há dados
            cursor.execute("SELECT COUNT(*) FROM dados_associacao")
            count = cursor.fetchone()[0]
            if count == 0:
                print("Criando registro padrao...")
                cursor.execute("""
                    INSERT INTO dados_associacao (nome, cnpj, endereco, updated_at)
                    VALUES ('Associação AADVITA', '00.000.000/0001-00', 'Endereço não informado', datetime('now'))
                """)
                conn.commit()
                print("OK: Registro padrao criado!")
            else:
                print("OK: Tabela ja possui dados.")
            
            conn.close()
            return True
        
        print("Criando tabela 'dados_associacao'...")
        
        # Criar a tabela
        cursor.execute("""
            CREATE TABLE dados_associacao (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                nome VARCHAR(200) NOT NULL,
                cnpj VARCHAR(18) NOT NULL,
                endereco TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Criar registro padrão
        cursor.execute("""
            INSERT INTO dados_associacao (nome, cnpj, endereco, updated_at)
            VALUES ('Associação AADVITA', '00.000.000/0001-00', 'Endereço não informado', datetime('now'))
        """)
        
        conn.commit()
        print("OK: Tabela 'dados_associacao' criada com sucesso!")
        print("OK: Registro padrao criado!")
        
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
    print("Migração: Criar tabela dados_associacao")
    print("=" * 60)
    print()
    
    success = migrate_dados_associacao()
    
    print()
    if success:
        print("=" * 60)
        print("OK: Migracao concluida com sucesso!")
        print("=" * 60)
    else:
        print("=" * 60)
        print("ERRO: Migracao falhou!")
        print("=" * 60)

