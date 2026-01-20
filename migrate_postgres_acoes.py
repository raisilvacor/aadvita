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
            print(f"[{attempt}/{retries}] Tentando conectar ao banco para migração acoes...")
            conn = psycopg.connect(database_url)
            conn.autocommit = True
            cur = conn.cursor()

            print("Executando: CREATE TABLE IF NOT EXISTS acao ...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS acao (
                    id SERIAL PRIMARY KEY,
                    titulo VARCHAR(200) NOT NULL,
                    slug VARCHAR(250) UNIQUE,
                    descricao TEXT NOT NULL,
                    data DATE NOT NULL,
                    categoria VARCHAR(100),
                    imagem VARCHAR(300),
                    imagem_base64 TEXT,
                    descricao_imagem TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            print("Executando: CREATE TABLE IF NOT EXISTS acao_foto ...")
            # Note: ForeignKey might fail if table doesn't exist, but we just created it.
            # If table already exists, this is fine.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS acao_foto (
                    id SERIAL PRIMARY KEY,
                    acao_id INTEGER NOT NULL REFERENCES acao(id) ON DELETE CASCADE,
                    caminho VARCHAR(300) NOT NULL,
                    titulo VARCHAR(200),
                    descricao TEXT,
                    descricao_imagem TEXT,
                    ordem INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            print("Migração acoes executada com sucesso (Postgres).")
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
