"""
Script para adicionar campos de mensalidade ao banco de dados
"""
# -*- coding: utf-8 -*-
import sqlite3
from datetime import datetime
import sys
import io

# Configurar encoding para Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Conectar ao banco de dados
conn = sqlite3.connect('instance/aadvita.db')
cursor = conn.cursor()

try:
    # Adicionar campos ao associado
    print("Adicionando campos de mensalidade à tabela associado...")
    
    # Verificar se os campos já existem
    cursor.execute("PRAGMA table_info(associado)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'valor_mensalidade' not in columns:
        cursor.execute("ALTER TABLE associado ADD COLUMN valor_mensalidade NUMERIC(10, 2) DEFAULT 0.00")
        print("[OK] Campo valor_mensalidade adicionado")
    else:
        print("[--] Campo valor_mensalidade ja existe")
    
    if 'desconto_tipo' not in columns:
        cursor.execute("ALTER TABLE associado ADD COLUMN desconto_tipo VARCHAR(10) DEFAULT NULL")
        print("[OK] Campo desconto_tipo adicionado")
    else:
        print("[--] Campo desconto_tipo ja existe")
    
    if 'desconto_valor' not in columns:
        cursor.execute("ALTER TABLE associado ADD COLUMN desconto_valor NUMERIC(10, 2) DEFAULT 0.00")
        print("[OK] Campo desconto_valor adicionado")
    else:
        print("[--] Campo desconto_valor ja existe")
    
    if 'ativo' not in columns:
        cursor.execute("ALTER TABLE associado ADD COLUMN ativo BOOLEAN DEFAULT 1")
        print("[OK] Campo ativo adicionado")
    else:
        print("[--] Campo ativo ja existe")
    
    # Criar tabela mensalidade se não existir
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mensalidade (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            associado_id INTEGER NOT NULL,
            valor_base NUMERIC(10, 2) NOT NULL,
            desconto_tipo VARCHAR(10),
            desconto_valor NUMERIC(10, 2) DEFAULT 0.00,
            valor_final NUMERIC(10, 2) NOT NULL,
            mes_referencia INTEGER NOT NULL,
            ano_referencia INTEGER NOT NULL,
            data_vencimento DATE NOT NULL,
            status VARCHAR(20) DEFAULT 'pendente',
            data_pagamento DATE,
            observacoes TEXT,
            created_at DATETIME,
            FOREIGN KEY (associado_id) REFERENCES associado (id)
        )
    """)
    print("[OK] Tabela mensalidade criada/verificada")
    
    conn.commit()
    print("\n[SUCESSO] Migracao concluida com sucesso!")
    
except Exception as e:
    conn.rollback()
    print(f"\n[ERRO] Erro na migracao: {str(e)}")
    raise
finally:
    conn.close()

