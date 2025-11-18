"""
Migração para Postgres: adiciona coluna `foto_base64` à tabela `associado` caso não exista.
Uso: python migrate_postgres_associado.py
"""
import os
import sys
import time


def normalize_url(url: str) -> str:
    if not url:
        return url
    if url.startswith('postgres://'):
        return url.replace('postgres://', 'postgresql://', 1)
    if url.startswith('postgresql+psycopg://'):
        return url.replace('postgresql+psycopg://', 'postgresql://', 1)
    return url


def migrate(retries: int = 8, delay: float = 3.0) -> int:
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

    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            print(f'[{attempt}/{retries}] Tentando conectar ao banco...')
            conn = psycopg.connect(database_url)
            conn.autocommit = True
            cur = conn.cursor()

            print('Executando: garantir coluna foto_base64 em associado ...')
            # Criar coluna caso não exista
            cur.execute('''
                CREATE TABLE IF NOT EXISTS associado (
                    id SERIAL PRIMARY KEY
                );
            ''')

            alters = [
                "ALTER TABLE associado ADD COLUMN IF NOT EXISTS foto_base64 TEXT;",
            ]
            for stmt in alters:
                try:
                    cur.execute(stmt)
                except Exception as e:
                    print('Aviso ao aplicar ALTER TABLE:', e)

            print('Migração associado executada com sucesso (Postgres).')
            cur.close()
            conn.close()
            return 0

        except Exception as e:
            last_exc = e
            print(f'Falha na tentativa {attempt}: {e}')
            if attempt < retries:
                sleep_time = delay * attempt
                print(f'Aguardando {sleep_time}s antes de nova tentativa...')
                time.sleep(sleep_time)

    print('Todas as tentativas falharam. Último erro:', last_exc)
    return 3


if __name__ == '__main__':
    sys.exit(migrate())
