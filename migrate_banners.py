#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de migração para adicionar a tabela Banner
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
        # Verificar se a tabela 'banner' já existe
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='banner'
        """)
        
        if cursor.fetchone():
            print("Tabela 'banner' já existe. Nenhuma migração necessária.")
            conn.close()
            return
        
        # Criar a tabela banner
        cursor.execute("""
            CREATE TABLE banner (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                tipo VARCHAR(50) NOT NULL UNIQUE,
                titulo VARCHAR(200) NOT NULL,
                descricao VARCHAR(300),
                url VARCHAR(500),
                imagem VARCHAR(300),
                cor_gradiente_inicio VARCHAR(7) DEFAULT '#667eea',
                cor_gradiente_fim VARCHAR(7) DEFAULT '#764ba2',
                ativo BOOLEAN DEFAULT 1,
                ordem INTEGER DEFAULT 0,
                created_at DATETIME,
                updated_at DATETIME
            )
        """)
        
        # Inserir banners padrão
        banners_padrao = [
            ('Campanhas', 'Campanhas', 'Conheça nossas campanhas e participe', '', '#667eea', '#764ba2', 0),
            ('Apoie-nos', 'Apoie-nos', 'Apoie nossa causa e faça a diferença', '', '#f093fb', '#f5576c', 1),
            ('Editais', 'Editais', 'Confira nossos editais e oportunidades', '', '#4facfe', '#00f2fe', 2)
        ]
        
        for tipo, titulo, descricao, url, cor_inicio, cor_fim, ordem in banners_padrao:
            cursor.execute("""
                INSERT INTO banner (tipo, titulo, descricao, url, cor_gradiente_inicio, cor_gradiente_fim, ativo, ordem, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, datetime('now'), datetime('now'))
            """, (tipo, titulo, descricao, url, cor_inicio, cor_fim, ordem))
        
        conn.commit()
        print("Tabela 'banner' criada com sucesso!")
        print("Banners padrão inseridos: Campanhas, Apoie-nos, Editais")
        
    except Exception as e:
        conn.rollback()
        print(f"Erro ao criar tabela: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()

