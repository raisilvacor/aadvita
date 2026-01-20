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
            print(f"[{attempt}/{retries}] Tentando conectar ao banco para migração projetos...")
            conn = psycopg.connect(database_url)
            conn.autocommit = True
            cur = conn.cursor()

            print("Executando: CREATE TABLE IF NOT EXISTS projeto ...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS projeto (
                    id SERIAL PRIMARY KEY,
                    titulo VARCHAR(200) NOT NULL,
                    slug VARCHAR(250) UNIQUE,
                    descripcion TEXT NOT NULL,
                    identificacao TEXT,
                    contexto_justificativa TEXT,
                    objetivos TEXT,
                    publico_alvo TEXT,
                    metodologia TEXT,
                    recursos_necessarios TEXT,
                    parcerias TEXT,
                    resultados_esperados TEXT,
                    monitoramento_avaliacao TEXT,
                    cronograma_execucao TEXT,
                    orcamento TEXT,
                    consideracoes_finais TEXT,
                    imagen VARCHAR(300),
                    imagen_base64 TEXT,
                    descricao_imagem TEXT,
                    arquivo_pdf VARCHAR(300),
                    arquivo_pdf_base64 TEXT,
                    estado VARCHAR(50) DEFAULT 'Ativo',
                    data_inicio DATE,
                    data_fim DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            print("Migração projetos executada com sucesso (Postgres).")
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
