"""
Migração para Postgres: cria a tabela `sos_pedido` se não existir.
Uso: python migrate_postgres_sos.py
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

            print('Executando: CREATE TABLE IF NOT EXISTS sos_pedido ...')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS sos_pedido (
                    id SERIAL PRIMARY KEY,
                    associado_id INTEGER REFERENCES associado(id),
                    descricao TEXT NOT NULL,
                    anexos TEXT,
                    status VARCHAR(50) DEFAULT 'novo',
                    contato_nome VARCHAR(200),
                    contato_telefone VARCHAR(100),
                    contato_email VARCHAR(200),
                    contato_endereco VARCHAR(400),
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                );
            ''')

            # Garantir colunas adicionais caso a tabela já exista em versões antigas
            # Verificar quais colunas já existem
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'sos_pedido'
            """)
            existing_columns = [row[0] for row in cur.fetchall()]
            print(f'Colunas existentes na tabela sos_pedido: {existing_columns}')
            
            # Colunas que devem existir
            required_columns = {
                'contato_nome': 'VARCHAR(200)',
                'contato_telefone': 'VARCHAR(100)',
                'contato_email': 'VARCHAR(200)',
                'contato_endereco': 'VARCHAR(400)'
            }
            
            # Adicionar colunas que não existem
            for col_name, col_type in required_columns.items():
                if col_name not in existing_columns:
                    print(f'Adicionando coluna {col_name}...')
                    try:
                        cur.execute(f'ALTER TABLE sos_pedido ADD COLUMN {col_name} {col_type}')
                        print(f'Coluna {col_name} adicionada com sucesso')
                    except Exception as e:
                        error_str = str(e).lower()
                        if 'duplicate' in error_str or 'already exists' in error_str:
                            print(f'Coluna {col_name} já existe (ignorando)')
                        else:
                            print(f'Erro ao adicionar coluna {col_name}: {e}')
                            raise
                else:
                    print(f'Coluna {col_name} já existe')

            print('Migração SOS executada com sucesso (Postgres).')
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
