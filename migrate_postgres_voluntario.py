"""
Migração para Postgres: adiciona a coluna `password_hash` na tabela `voluntario` se ela não existir.
Este script lê `DATABASE_URL` das variáveis de ambiente (configurado pelo Render quando o serviço Postgres está ligado).

Uso: (no servidor ou shell com `DATABASE_URL` disponível)
    python migrate_postgres_voluntario.py

Observação: o script tenta normalizar URLs como 'postgres://' e 'postgresql+psycopg://' para um formato aceito pelo driver `psycopg`.
"""
import os
import sys

def normalize_url(url: str) -> str:
    if not url:
        return url
    # Render/GitHub sometimes provide 'postgres://' which psycopg accepts as 'postgresql://'
    if url.startswith('postgres://'):
        return url.replace('postgres://', 'postgresql://', 1)
    if url.startswith('postgresql+psycopg://'):
        return url.replace('postgresql+psycopg://', 'postgresql://', 1)
    return url


def migrate():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print('DATABASE_URL não encontrada nas variáveis de ambiente. Abortando.')
        return 1

    database_url = normalize_url(database_url)

    try:
        import psycopg
    except Exception as e:
        print('Erro ao importar psycopg:', e)
        return 2

    try:
        print('Conectando em', database_url)
        conn = psycopg.connect(database_url)
        conn.autocommit = True
        cur = conn.cursor()

        # Adiciona coluna password_hash se não existir
        print('Executando: ALTER TABLE voluntario ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);')
        cur.execute("ALTER TABLE voluntario ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);")

        print('Migração executada com sucesso (Postgres).')
        cur.close()
        conn.close()
        return 0
    except Exception as e:
        print('Erro durante migração Postgres:', str(e))
        return 3


if __name__ == '__main__':
    sys.exit(migrate())
