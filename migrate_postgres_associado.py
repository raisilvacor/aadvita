"""
Migração para Postgres: cria tabela `associado` completa se não existir, ou adiciona coluna `foto_base64` caso contrário.
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
        # Import optional Postgres driver (psycopg v3). Use type ignore so static
        # analyzers don't raise import errors in environments without the package.
        import psycopg  # type: ignore
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

            print('Executando: CREATE TABLE IF NOT EXISTS associado ...')
            # Create table with all fields from app.py
            cur.execute('''
                CREATE TABLE IF NOT EXISTS associado (
                    id SERIAL PRIMARY KEY,
                    nome_completo VARCHAR(200) NOT NULL,
                    cpf VARCHAR(14) NOT NULL UNIQUE,
                    data_nascimento DATE NOT NULL,
                    endereco TEXT NOT NULL,
                    telefone VARCHAR(20) NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    status VARCHAR(20) DEFAULT 'pendente',
                    tipo_associado VARCHAR(20) DEFAULT 'contribuinte',
                    valor_mensalidade NUMERIC(10, 2) DEFAULT 0.00,
                    desconto_tipo VARCHAR(10),
                    desconto_valor NUMERIC(10, 2) DEFAULT 0.00,
                    ativo BOOLEAN DEFAULT TRUE,
                    carteira_pdf VARCHAR(300),
                    carteira_pdf_base64 TEXT,
                    foto VARCHAR(300),
                    foto_base64 TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            ''')

            # Ensure columns exist even if table existed before
            alters = [
                "ALTER TABLE associado ADD COLUMN IF NOT EXISTS foto_base64 TEXT;",
                "ALTER TABLE associado ADD COLUMN IF NOT EXISTS carteira_pdf_base64 TEXT;",
                "ALTER TABLE associado ADD COLUMN IF NOT EXISTS ativo BOOLEAN DEFAULT TRUE;",
                "ALTER TABLE associado ADD COLUMN IF NOT EXISTS valor_mensalidade NUMERIC(10, 2) DEFAULT 0.00;",
            ]
            for stmt in alters:
                try:
                    cur.execute(stmt)
                except Exception as e:
                    print(f'Aviso ao aplicar {stmt}: {e}')

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
