"""
Script de migração para adicionar coluna password_hash à tabela associado
Execute este script uma vez para atualizar o banco de dados existente
"""
import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = 'instance/aadvita.db'

def migrate_database():
    """Adiciona a coluna password_hash à tabela associado"""
    if not os.path.exists(DB_PATH):
        print("Banco de dados não encontrado. Execute app.py primeiro para criar o banco.")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Verificar se a coluna já existe
        cursor.execute("PRAGMA table_info(associado)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'password_hash' in columns:
            print("A coluna password_hash já existe. Migração não necessária.")
            conn.close()
            return
        
        print("Adicionando coluna password_hash...")
        
        # Adicionar coluna permitindo NULL temporariamente
        cursor.execute("ALTER TABLE associado ADD COLUMN password_hash VARCHAR(255)")
        
        # Definir senha padrão para associados existentes
        # Senha padrão: "123456" (os associados devem alterar depois)
        default_password_hash = generate_password_hash('123456')
        
        cursor.execute("""
            UPDATE associado 
            SET password_hash = ? 
            WHERE password_hash IS NULL
        """, (default_password_hash,))
        
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
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Copiar dados
        cursor.execute("""
            INSERT INTO associado_new 
            (id, nome_completo, cpf, data_nascimento, endereco, telefone, password_hash, created_at)
            SELECT id, nome_completo, cpf, data_nascimento, endereco, telefone, password_hash, created_at
            FROM associado
        """)
        
        # Remover tabela antiga
        cursor.execute("DROP TABLE associado")
        
        # Renomear tabela nova
        cursor.execute("ALTER TABLE associado_new RENAME TO associado")
        
        conn.commit()
        print("Migração concluída com sucesso!")
        print("NOTA: Todos os associados existentes têm a senha padrão '123456'")
        print("      Recomenda-se que eles alterem a senha no primeiro login.")
        
    except Exception as e:
        conn.rollback()
        print(f"Erro durante a migração: {e}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_database()

