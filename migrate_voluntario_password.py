"""
Script de migração para adicionar a coluna `password_hash` na tabela `voluntario` (SQLite local).
Execute este script localmente antes de aceitar senhas no cadastro de voluntários.

Uso:
    python migrate_voluntario_password.py

Observações:
- Este script altera apenas o banco SQLite em `instance/aadvita.db`.
- Se você usar Postgres em produção (Render), crie a migration equivalente e aplique no banco remoto.
"""
import sqlite3
import os

DB_PATH = 'instance/aadvita.db'


def migrate():
    if not os.path.exists(DB_PATH):
        print("Banco de dados não encontrado em 'instance/aadvita.db'. Execute a criação do banco local antes.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA table_info(voluntario)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'password_hash' in columns:
            print("A coluna 'password_hash' já existe em 'voluntario'. Migração não necessária.")
            return

        print("Adicionando coluna 'password_hash' na tabela 'voluntario'...")
        cursor.execute("ALTER TABLE voluntario ADD COLUMN password_hash VARCHAR(255)")
        conn.commit()
        print("Coluna adicionada com sucesso. Agora você pode salvar senhas para voluntários localmente.")
        print("NOTA: Em produção (Postgres), crie e aplique uma migration equivalente no banco remoto.")

    except Exception as e:
        conn.rollback()
        print(f"Erro durante a migração: {e}")
        raise

    finally:
        conn.close()


if __name__ == '__main__':
    migrate()
