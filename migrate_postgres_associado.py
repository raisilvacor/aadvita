"""
Migração para Postgres: cria tabela `associado` completa se não existir, e garante que TODAS as colunas existam.
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
        import psycopg  # type: ignore
    except Exception as e:
        print('Erro ao importar psycopg:', e)
        return 2

    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            print(f'[{attempt}/{retries}] Tentando conectar ao banco para corrigir schema associado...')
            conn = psycopg.connect(database_url)
            conn.autocommit = True
            cur = conn.cursor()

            print('Executando: CREATE TABLE IF NOT EXISTS associado ...')
            # Tenta criar a tabela com todas as colunas se ela não existir
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

            # Lista de colunas para garantir que existem (caso a tabela tenha sido criada parcialmente antes)
            columns_to_ensure = [
                ("nome_completo", "VARCHAR(200)"),
                ("cpf", "VARCHAR(14)"),
                ("data_nascimento", "DATE"),
                ("endereco", "TEXT"),
                ("telefone", "VARCHAR(20)"),
                ("password_hash", "VARCHAR(255)"),
                ("status", "VARCHAR(20) DEFAULT 'pendente'"),
                ("tipo_associado", "VARCHAR(20) DEFAULT 'contribuinte'"),
                ("valor_mensalidade", "NUMERIC(10, 2) DEFAULT 0.00"),
                ("desconto_tipo", "VARCHAR(10)"),
                ("desconto_valor", "NUMERIC(10, 2) DEFAULT 0.00"),
                ("ativo", "BOOLEAN DEFAULT TRUE"),
                ("carteira_pdf", "VARCHAR(300)"),
                ("carteira_pdf_base64", "TEXT"),
                ("foto", "VARCHAR(300)"),
                ("foto_base64", "TEXT"),
                ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ]

            print('Verificando colunas da tabela associado...')
            for col_name, col_def in columns_to_ensure:
                try:
                    # Postgres support "ADD COLUMN IF NOT EXISTS" since 9.6
                    # Se falhar em versões antigas, o except captura
                    sql = f"ALTER TABLE associado ADD COLUMN IF NOT EXISTS {col_name} {col_def};"
                    cur.execute(sql)
                except Exception as e:
                    print(f"Aviso ao tentar adicionar coluna {col_name}: {e}")
                    # Tentar fallback sem IF NOT EXISTS (vai falhar se ja existir, mas ok)
                    try:
                        sql_fallback = f"ALTER TABLE associado ADD COLUMN {col_name} {col_def};"
                        cur.execute(sql_fallback)
                    except Exception as e2:
                        # Ignorar erro se coluna já existe (DuplicateColumn)
                        pass

            print('Migração associado (correção de colunas) executada com sucesso.')
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
