#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para adicionar coluna telefone à tabela doacao
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
        
        # Verificar se a coluna já existe
        cursor.execute("PRAGMA table_info(doacao)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'telefone' in columns:
            print("✅ A coluna telefone já existe na tabela doacao.")
            conn.close()
            return True
        
        print("📝 Adicionando coluna telefone à tabela doacao...")
        
        # Adicionar coluna telefone
        cursor.execute("ALTER TABLE doacao ADD COLUMN telefone VARCHAR(20)")
        print("   ✓ Coluna telefone adicionada")
        
        conn.commit()
        conn.close()
        
        print("✅ Migração concluída com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao executar migração: {str(e)}")
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("Migração: Adicionar telefone à tabela doacao")
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

