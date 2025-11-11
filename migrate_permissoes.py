"""
Script de migração para adicionar sistema de permissões
Execute este script uma vez para atualizar o banco de dados existente
"""
import sqlite3
import os

DB_PATH = 'aadvita.db'
# Também verificar no diretório instance/
DB_PATHS = ['aadvita.db', 'instance/aadvita.db']

def migrate_permissoes():
    """Adiciona coluna is_super_admin e cria tabelas de permissões"""
    # Encontrar o banco de dados
    db_path = None
    for path in DB_PATHS:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        print("Banco de dados não encontrado. Execute app.py primeiro para criar o banco.")
        return
    
    print(f"Usando banco de dados: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Verificar se a coluna is_super_admin já existe
        cursor.execute("PRAGMA table_info(usuario)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'is_super_admin' not in columns:
            print("Adicionando coluna is_super_admin...")
            cursor.execute("ALTER TABLE usuario ADD COLUMN is_super_admin BOOLEAN DEFAULT 0")
            
            # Marcar o primeiro usuário como super admin
            cursor.execute("UPDATE usuario SET is_super_admin = 1 WHERE id = (SELECT MIN(id) FROM usuario)")
            print("Primeiro usuário marcado como super admin.")
        
        # Criar tabela de permissões se não existir
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS permissao (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo VARCHAR(50) UNIQUE NOT NULL,
                nome VARCHAR(100) NOT NULL,
                descricao VARCHAR(255),
                categoria VARCHAR(50)
            )
        """)
        
        # Criar tabela de associação usuario_permissao se não existir
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuario_permissao (
                usuario_id INTEGER NOT NULL,
                permissao_id INTEGER NOT NULL,
                PRIMARY KEY (usuario_id, permissao_id),
                FOREIGN KEY (usuario_id) REFERENCES usuario (id),
                FOREIGN KEY (permissao_id) REFERENCES permissao (id)
            )
        """)
        
        conn.commit()
        print("Migração concluída com sucesso!")
        
    except Exception as e:
        print(f"Erro durante a migração: {str(e)}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_permissoes()

