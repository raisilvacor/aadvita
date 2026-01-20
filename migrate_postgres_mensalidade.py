import os
import time
import psycopg # type: ignore
from urllib.parse import urlparse

def normalize_url(url):
    if url and url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url

def migrate(retries=8, delay=3.0):
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("DATABASE_URL não encontrada nas variáveis de ambiente. Abortando.")
        return 1
    
    database_url = normalize_url(database_url)
    
    try:
        import psycopg
    except ImportError:
        print("Erro ao importar psycopg. Certifique-se de que está instalado.")
        return 2

    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            print(f"[{attempt}/{retries}] Tentando conectar ao banco para migração mensalidade...")
            conn = psycopg.connect(database_url)
            conn.autocommit = True
            cur = conn.cursor()

            print("Executando: CREATE TABLE IF NOT EXISTS mensalidade ...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS mensalidade (
                    id SERIAL PRIMARY KEY,
                    associado_id INTEGER NOT NULL REFERENCES associado(id) ON DELETE CASCADE,
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            print("Migração mensalidade executada com sucesso (Postgres).")
            cur.close()
            conn.close()
            return 0
            
        except Exception as e:
            last_exc = e
            print(f"Falha na tentativa {attempt}: {e}")
            if attempt < retries:
                sleep_time = delay * attempt
                print(f"Aguardando {sleep_time}s antes de nova tentativa...")
                time.sleep(sleep_time)

    print("Todas as tentativas falharam. Último erro:", last_exc)
    return 3

if __name__ == "__main__":
    migrate()
