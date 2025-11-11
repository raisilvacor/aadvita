#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de migração para adicionar novos campos ao modelo Projeto
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
        # Verificar se a tabela 'projeto' existe
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='projeto'
        """)
        
        if not cursor.fetchone():
            print("Tabela 'projeto' não existe. Nenhuma migração necessária.")
            conn.close()
            return
        
        # Lista de campos a adicionar
        campos = [
            ('identificacao', 'TEXT'),
            ('contexto_justificativa', 'TEXT'),
            ('objetivos', 'TEXT'),
            ('publico_alvo', 'TEXT'),
            ('metodologia', 'TEXT'),
            ('recursos_necessarios', 'TEXT'),
            ('parcerias', 'TEXT'),
            ('resultados_esperados', 'TEXT'),
            ('monitoramento_avaliacao', 'TEXT'),
            ('cronograma_execucao', 'TEXT'),
            ('orcamento', 'TEXT'),
            ('consideracoes_finais', 'TEXT')
        ]
        
        # Verificar colunas existentes
        cursor.execute("PRAGMA table_info(projeto)")
        existing_columns = [column[1] for column in cursor.fetchall()]
        
        # Adicionar campos que não existem
        for campo, tipo in campos:
            if campo not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE projeto ADD COLUMN {campo} {tipo}")
                    print(f"Campo '{campo}' adicionado com sucesso.")
                except Exception as e:
                    print(f"Erro ao adicionar campo '{campo}': {e}")
            else:
                print(f"Campo '{campo}' já existe. Pulando...")
        
        conn.commit()
        print("Migração concluída com sucesso!")
        
    except Exception as e:
        conn.rollback()
        print(f"Erro ao migrar campos: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()

