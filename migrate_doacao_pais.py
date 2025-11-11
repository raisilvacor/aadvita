#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para adicionar coluna pais à tabela doacao
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
        
        if 'pais' in columns:
            print("✅ A coluna pais já existe na tabela doacao.")
        else:
            print("📝 Adicionando coluna pais à tabela doacao...")
            cursor.execute("ALTER TABLE doacao ADD COLUMN pais VARCHAR(100)")
            print("   ✓ Coluna pais adicionada")
        
        # Verificar se precisa atualizar telefone e tipo_documento
        cursor.execute("PRAGMA table_info(doacao)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Atualizar tamanho de telefone se necessário
        if 'telefone' in columns:
            try:
                cursor.execute("ALTER TABLE doacao ADD COLUMN telefone_temp VARCHAR(30)")
                cursor.execute("UPDATE doacao SET telefone_temp = telefone")
                cursor.execute("ALTER TABLE doacao DROP COLUMN telefone")
                cursor.execute("ALTER TABLE doacao RENAME COLUMN telefone_temp TO telefone")
                print("   ✓ Coluna telefone atualizada para VARCHAR(30)")
            except:
                pass  # Já pode estar no tamanho correto
        
        # Atualizar tamanho de tipo_documento se necessário
        if 'tipo_documento' in columns:
            try:
                cursor.execute("ALTER TABLE doacao ADD COLUMN tipo_documento_temp VARCHAR(20)")
                cursor.execute("UPDATE doacao SET tipo_documento_temp = tipo_documento")
                cursor.execute("ALTER TABLE doacao DROP COLUMN tipo_documento")
                cursor.execute("ALTER TABLE doacao RENAME COLUMN tipo_documento_temp TO tipo_documento")
                print("   ✓ Coluna tipo_documento atualizada para VARCHAR(20)")
            except:
                pass  # Já pode estar no tamanho correto
        
        # Atualizar tamanho de documento se necessário
        if 'documento' in columns:
            try:
                cursor.execute("ALTER TABLE doacao ADD COLUMN documento_temp VARCHAR(30)")
                cursor.execute("UPDATE doacao SET documento_temp = documento")
                cursor.execute("ALTER TABLE doacao DROP COLUMN documento")
                cursor.execute("ALTER TABLE doacao RENAME COLUMN documento_temp TO documento")
                print("   ✓ Coluna documento atualizada para VARCHAR(30)")
            except:
                pass  # Já pode estar no tamanho correto
        
        conn.commit()
        conn.close()
        
        print("✅ Migração concluída com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao executar migração: {str(e)}")
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("Migração: Adicionar país à tabela doacao")
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

