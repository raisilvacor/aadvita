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
            print(f"[{attempt}/{retries}] Tentando conectar ao banco para migração album/apoiador/configuracao...")
            conn = psycopg.connect(database_url)
            conn.autocommit = True
            cur = conn.cursor()

            print("Executando: CREATE TABLE IF NOT EXISTS album ...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS album (
                    id SERIAL PRIMARY KEY,
                    titulo_pt VARCHAR(200) NOT NULL,
                    titulo_es VARCHAR(200),
                    titulo_en VARCHAR(200),
                    descricao_pt TEXT,
                    descricao_es TEXT,
                    descricao_en TEXT,
                    capa VARCHAR(300),
                    ordem INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            print("Executando: CREATE TABLE IF NOT EXISTS album_foto ...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS album_foto (
                    id SERIAL PRIMARY KEY,
                    album_id INTEGER NOT NULL REFERENCES album(id) ON DELETE CASCADE,
                    caminho VARCHAR(300) NOT NULL,
                    titulo_pt VARCHAR(200),
                    titulo_es VARCHAR(200),
                    titulo_en VARCHAR(200),
                    descricao_pt TEXT,
                    descricao_es TEXT,
                    descricao_en TEXT,
                    ordem INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            print("Executando: CREATE TABLE IF NOT EXISTS apoiador ...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS apoiador (
                    id SERIAL PRIMARY KEY,
                    nome VARCHAR(200) NOT NULL,
                    tipo VARCHAR(100),
                    logo VARCHAR(300),
                    logo_base64 TEXT,
                    descricao_imagem TEXT,
                    website VARCHAR(500),
                    descricao TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Ensure columns for apoiador
            apoiador_cols = [
                ("logo_base64", "TEXT"),
                ("descricao_imagem", "TEXT"),
                ("tipo", "VARCHAR(100)"),
                ("website", "VARCHAR(500)"),
                ("descricao", "TEXT")
            ]
            for col_name, col_def in apoiador_cols:
                try:
                    cur.execute(f"ALTER TABLE apoiador ADD COLUMN IF NOT EXISTS {col_name} {col_def};")
                except Exception:
                    try:
                        cur.execute(f"ALTER TABLE apoiador ADD COLUMN {col_name} {col_def};")
                    except:
                        pass

            # Tabelas de associação
            print("Executando: CREATE TABLE IF NOT EXISTS evento_album ...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS evento_album (
                    evento_id INTEGER NOT NULL REFERENCES evento(id) ON DELETE CASCADE,
                    album_id INTEGER NOT NULL REFERENCES album(id) ON DELETE CASCADE,
                    PRIMARY KEY (evento_id, album_id)
                );
            """)

            print("Executando: CREATE TABLE IF NOT EXISTS acao_album ...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS acao_album (
                    acao_id INTEGER NOT NULL REFERENCES acao(id) ON DELETE CASCADE,
                    album_id INTEGER NOT NULL REFERENCES album(id) ON DELETE CASCADE,
                    PRIMARY KEY (acao_id, album_id)
                );
            """)

            print("Executando: CREATE TABLE IF NOT EXISTS configuracao ...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS configuracao (
                    id SERIAL PRIMARY KEY,
                    chave VARCHAR(100) NOT NULL UNIQUE,
                    valor TEXT,
                    tipo VARCHAR(50),
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            print("Migração album/apoiador/configuracao executada com sucesso (Postgres).")
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
