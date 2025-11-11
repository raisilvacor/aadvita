"""
Script de migração para adicionar coluna status à tabela associado
Execute este script uma vez para atualizar o banco de dados existente
"""
import sqlite3
import os

DB_PATH = 'instance/aadvita.db'

def migrate_database():
    """Adiciona a coluna status à tabela associado"""
    if not os.path.exists(DB_PATH):
        print("Banco de dados não encontrado. Execute app.py primeiro para criar o banco.")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Verificar se a coluna já existe
        cursor.execute("PRAGMA table_info(associado)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'status' in columns:
            print("A coluna status já existe. Migração não necessária.")
            conn.close()
            return
        
        print("Adicionando coluna status...")
        
        # Adicionar coluna permitindo NULL temporariamente
        cursor.execute("ALTER TABLE associado ADD COLUMN status VARCHAR(20) DEFAULT 'pendente'")
        
        # Definir status padrão para associados existentes
        # Associados existentes serão marcados como 'aprovado' (já estavam funcionando)
        cursor.execute("""
            UPDATE associado 
            SET status = 'aprovado' 
            WHERE status IS NULL
        """)
        
        # Tornar a coluna NOT NULL
        # SQLite não suporta ALTER COLUMN diretamente, então precisamos recriar a tabela
        print("Atualizando estrutura da tabela...")
        
        # Criar tabela temporária
        cursor.execute("""
            CREATE TABLE associado_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome_completo VARCHAR(200) NOT NULL,
                cpf VARCHAR(14) NOT NULL UNIQUE,
                data_nascimento DATE NOT NULL,
                endereco TEXT NOT NULL,
                telefone VARCHAR(20) NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'pendente',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Copiar dados
        cursor.execute("""
            INSERT INTO associado_new 
            (id, nome_completo, cpf, data_nascimento, endereco, telefone, password_hash, status, created_at)
            SELECT id, nome_completo, cpf, data_nascimento, endereco, telefone, password_hash, 
                   COALESCE(status, 'aprovado'), created_at
            FROM associado
        """)
        
        # Remover tabela antiga
        cursor.execute("DROP TABLE associado")
        
        # Renomear tabela nova
        cursor.execute("ALTER TABLE associado_new RENAME TO associado")
        
        conn.commit()
        print("Migração concluída com sucesso!")
        print("NOTA: Associados existentes foram marcados como 'aprovado'")
        
    except Exception as e:
        conn.rollback()
        print(f"Erro durante a migração: {e}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_database()

