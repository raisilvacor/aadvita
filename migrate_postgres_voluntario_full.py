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
            print(f"[{attempt}/{retries}] Tentando conectar ao banco para migração voluntario/oferta/agendamento...")
            conn = psycopg.connect(database_url)
            conn.autocommit = True
            cur = conn.cursor()

            print("Executando: CREATE TABLE IF NOT EXISTS voluntario ...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS voluntario (
                    id SERIAL PRIMARY KEY,
                    nome_completo VARCHAR(200) NOT NULL,
                    email VARCHAR(200) NOT NULL,
                    telefone VARCHAR(50),
                    cpf VARCHAR(20),
                    password_hash VARCHAR(255),
                    endereco TEXT,
                    cidade VARCHAR(100),
                    estado VARCHAR(50),
                    cep VARCHAR(20),
                    data_nascimento DATE,
                    profissao VARCHAR(200),
                    habilidades TEXT,
                    disponibilidade TEXT,
                    area_interesse VARCHAR(200),
                    observacoes TEXT,
                    status VARCHAR(50) DEFAULT 'pendente',
                    ativo BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            print("Executando: CREATE TABLE IF NOT EXISTS oferta_horas ...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS oferta_horas (
                    id SERIAL PRIMARY KEY,
                    voluntario_id INTEGER NOT NULL REFERENCES voluntario(id) ON DELETE CASCADE,
                    data_inicio DATE NOT NULL,
                    data_fim DATE,
                    hora_inicio VARCHAR(10),
                    hora_fim VARCHAR(10),
                    dias_semana VARCHAR(100),
                    horas_totais FLOAT,
                    descricao TEXT,
                    area_atividade VARCHAR(200),
                    status VARCHAR(50) DEFAULT 'disponivel',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            print("Executando: CREATE TABLE IF NOT EXISTS agendamento_voluntario ...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS agendamento_voluntario (
                    id SERIAL PRIMARY KEY,
                    voluntario_id INTEGER NOT NULL REFERENCES voluntario(id) ON DELETE CASCADE,
                    oferta_horas_id INTEGER REFERENCES oferta_horas(id) ON DELETE CASCADE,
                    data_agendamento DATE NOT NULL,
                    hora_inicio VARCHAR(10) NOT NULL,
                    hora_fim VARCHAR(10) NOT NULL,
                    atividade VARCHAR(200) NOT NULL,
                    descricao TEXT,
                    responsavel VARCHAR(200),
                    contato_responsavel VARCHAR(100),
                    local VARCHAR(300),
                    observacoes TEXT,
                    status VARCHAR(50) DEFAULT 'agendado',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            print("Migração voluntario_full executada com sucesso (Postgres).")
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
