#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para adicionar colunas tipo_documento e documento à tabela doacao
"""

import sqlite3
import sys
import os

# Configurar encoding UTF-8 para output
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def migrate():
    # Tentar encontrar o banco de dados em diferentes locais
    possible_paths = ['aadvita.db', 'instance/aadvita.db', os.path.join('instance', 'aadvita.db')]
    db_path = None
    
    for path in possible_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        print(f"❌ Banco de dados não encontrado! Procurado em: {', '.join(possible_paths)}")
        return False
    
    print(f"📁 Banco de dados encontrado: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Verificar se as colunas já existem
        cursor.execute("PRAGMA table_info(doacao)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'tipo_documento' in columns and 'documento' in columns:
            print("✅ As colunas tipo_documento e documento já existem na tabela doacao.")
            conn.close()
            return True
        
        print("📝 Adicionando colunas tipo_documento e documento à tabela doacao...")
        
        # Adicionar coluna tipo_documento se não existir
        if 'tipo_documento' not in columns:
            cursor.execute("ALTER TABLE doacao ADD COLUMN tipo_documento VARCHAR(10)")
            print("   ✓ Coluna tipo_documento adicionada")
        else:
            print("   ℹ Coluna tipo_documento já existe")
        
        # Adicionar coluna documento se não existir
        if 'documento' not in columns:
            cursor.execute("ALTER TABLE doacao ADD COLUMN documento VARCHAR(20)")
            print("   ✓ Coluna documento adicionada")
        else:
            print("   ℹ Coluna documento já existe")
        
        conn.commit()
        conn.close()
        
        print("✅ Migração concluída com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao executar migração: {str(e)}")
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("Migração: Adicionar tipo_documento e documento à tabela doacao")
    print("=" * 60)
    print()
    
    success = migrate()
    
    print()
    if success:
        print("✅ Migração executada com sucesso!")
        sys.exit(0)
    else:
        print("❌ Erro ao executar migração!")
        sys.exit(1)

