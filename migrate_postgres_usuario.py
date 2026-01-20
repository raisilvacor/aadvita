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
            print(f"[{attempt}/{retries}] Tentando conectar ao banco para migração usuario/permissao...")
            conn = psycopg.connect(database_url)
            conn.autocommit = True
            cur = conn.cursor()

            print("Executando: CREATE TABLE IF NOT EXISTS usuario ...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS usuario (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(80) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    nome VARCHAR(200) NOT NULL,
                    is_super_admin BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Ensure columns exist for usuario
            usuario_cols = [
                ("username", "VARCHAR(80)"),
                ("password_hash", "VARCHAR(255)"),
                ("nome", "VARCHAR(200)"),
                ("is_super_admin", "BOOLEAN DEFAULT FALSE"),
                ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            ]
            
            for col_name, col_def in usuario_cols:
                try:
                    sql = f"ALTER TABLE usuario ADD COLUMN IF NOT EXISTS {col_name} {col_def};"
                    cur.execute(sql)
                except Exception as e:
                    print(f"Aviso: erro ao adicionar coluna {col_name} em usuario: {e}")
                    try:
                        cur.execute(f"ALTER TABLE usuario ADD COLUMN {col_name} {col_def};")
                    except:
                        pass

            print("Executando: CREATE TABLE IF NOT EXISTS permissao ...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS permissao (
                    id SERIAL PRIMARY KEY,
                    nome VARCHAR(100) NOT NULL UNIQUE,
                    codigo VARCHAR(100) NOT NULL UNIQUE,
                    descricao VARCHAR(255)
                );
            """)

            print("Executando: CREATE TABLE IF NOT EXISTS usuario_permissao ...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS usuario_permissao (
                    usuario_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
                    permissao_id INTEGER NOT NULL REFERENCES permissao(id) ON DELETE CASCADE,
                    PRIMARY KEY (usuario_id, permissao_id)
                );
            """)
            
            print("Migração usuario/permissao executada com sucesso (Postgres).")
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
