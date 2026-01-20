#!/usr/bin/env python
"""
Script URGENTE para tentar salvar dados de banco suspenso/deletado
Tenta múltiplas formas de conexão
"""
import os
import sys
from datetime import datetime

DATABASE_URL = "postgresql://clinica_db_cxsq_user:1GJkXP0EOQYis7RA7bfY3PwmB5OtjUX2@dpg-d4s4dkeuk2gs73a52mug-a.oregon-postgres.render.com/clinica_db_cxsq"

def tentar_conexao_psycopg():
    """Tenta conectar usando psycopg diretamente"""
    try:
        import psycopg
        
        print("[*] Tentativa 1: Conexao direta com psycopg...")
        
        url_parts = DATABASE_URL.replace("postgresql://", "").split("@")
        user_pass = url_parts[0].split(":")
        host_db = url_parts[1].split("/")
        
        username = user_pass[0]
        password = user_pass[1]
        host_port = host_db[0].split(":")
        host = host_port[0]
        port = int(host_port[1]) if len(host_port) > 1 else 5432
        database = host_db[1].split("?")[0]
        
        # Tentar diferentes modos SSL
        ssl_modes = ['require', 'prefer', 'allow', 'disable']
        
        for ssl_mode in ssl_modes:
            try:
                print(f"    Tentando SSL mode: {ssl_mode}...")
                conn = psycopg.connect(
                    host=host,
                    port=port,
                    dbname=database,
                    user=username,
                    password=password,
                    sslmode=ssl_mode,
                    connect_timeout=5
                )
                print(f"[OK] Conectado com SSL mode: {ssl_mode}!")
                return conn
            except Exception as e:
                if ssl_mode == ssl_modes[-1]:
                    print(f"    [X] Falhou: {str(e)[:100]}")
                continue
        
        return None
    except ImportError:
        print("[X] psycopg nao encontrado")
        return None
    except Exception as e:
        print(f"[X] Erro: {e}")
        return None

def tentar_conexao_sqlalchemy():
    """Tenta conectar usando SQLAlchemy"""
    try:
        from sqlalchemy import create_engine, text
        
        print("[*] Tentativa 2: Conexao com SQLAlchemy...")
        
        # Tentar com psycopg3
        db_url = DATABASE_URL.replace('postgresql://', 'postgresql+psycopg://', 1)
        
        for ssl_mode in ['require', 'prefer', 'allow']:
            try:
                url_with_ssl = f"{db_url}?sslmode={ssl_mode}"
                print(f"    Tentando SSL mode: {ssl_mode}...")
                engine = create_engine(url_with_ssl, echo=False, pool_pre_ping=True, 
                                      connect_args={"connect_timeout": 5})
                
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                    print(f"[OK] Conectado com SQLAlchemy (SSL: {ssl_mode})!")
                    return engine
            except:
                continue
        
        return None
    except Exception as e:
        print(f"[X] Erro SQLAlchemy: {e}")
        return None

def exportar_dados(conn_or_engine):
    """Exporta dados usando conexão estabelecida"""
    try:
        from sqlalchemy import create_engine, text, inspect
        
        # Se for conexão psycopg direta, converter para engine
        if hasattr(conn_or_engine, 'cursor'):
            # É uma conexão psycopg direta
            print("[*] Exportando via conexao psycopg direta...")
            return exportar_via_psycopg_direto(conn_or_engine)
        else:
            # É um engine SQLAlchemy
            print("[*] Exportando via SQLAlchemy...")
            engine = conn_or_engine
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"database_export_{timestamp}.sql"
        
        print(f"[*] Encontradas {len(tables)} tabelas")
        print(f"[*] Exportando para: {output_file}\n")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"-- Database Export\n")
            f.write(f"-- Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"-- Tables: {len(tables)}\n")
            f.write(f"--\n\n")
            
            for i, table in enumerate(tables, 1):
                print(f"[{i}/{len(tables)}] {table}")
                
                columns = inspector.get_columns(table)
                col_names = [col['name'] for col in columns]
                
                # CREATE TABLE
                f.write(f"\n-- Table: {table}\n")
                f.write(f"DROP TABLE IF EXISTS {table} CASCADE;\n")
                f.write(f"CREATE TABLE {table} (\n")
                
                col_defs = []
                for col in columns:
                    col_name = col['name']
                    col_type = str(col['type'])
                    nullable = "" if col.get('nullable', True) else "NOT NULL"
                    col_def = f"    {col_name} {col_type} {nullable}".strip()
                    col_defs.append(col_def)
                
                f.write(",\n".join(col_defs))
                f.write("\n);\n\n")
                
                # Dados
                with engine.connect() as conn:
                    result = conn.execute(text(f"SELECT * FROM {table};"))
                    rows = result.fetchall()
                    
                    if rows:
                        f.write(f"-- Data: {table} ({len(rows)} rows)\n")
                        for row in rows:
                            values = []
                            for val in row:
                                if val is None:
                                    values.append("NULL")
                                elif isinstance(val, str):
                                    val_escaped = val.replace("'", "''").replace("\\", "\\\\")
                                    values.append(f"'{val_escaped}'")
                                elif isinstance(val, (int, float)):
                                    values.append(str(val))
                                elif isinstance(val, bool):
                                    values.append("TRUE" if val else "FALSE")
                                elif hasattr(val, 'isoformat'):
                                    values.append(f"'{val.isoformat()}'")
                                else:
                                    val_str = str(val).replace("'", "''")
                                    values.append(f"'{val_str}'")
                            
                            f.write(f"INSERT INTO {table} ({', '.join(col_names)}) VALUES ({', '.join(values)});\n")
                        f.write("\n")
        
        file_size = os.path.getsize(output_file) / (1024 * 1024)
        print(f"\n[OK] Exportacao concluida!")
        print(f"Arquivo: {output_file} ({file_size:.2f} MB)")
        return True
        
    except Exception as e:
        print(f"[ERRO] Erro ao exportar: {e}")
        import traceback
        traceback.print_exc()
        return False

def exportar_via_psycopg_direto(conn):
    """Exporta usando conexão psycopg direta"""
    try:
        cur = conn.cursor()
        
        # Listar tabelas
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)
        tables = [row[0] for row in cur.fetchall()]
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"database_export_{timestamp}.sql"
        
        print(f"[*] Encontradas {len(tables)} tabelas")
        print(f"[*] Exportando para: {output_file}\n")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"-- Database Export\n")
            f.write(f"-- Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"-- Tables: {len(tables)}\n")
            f.write(f"--\n\n")
            
            for i, table in enumerate(tables, 1):
                print(f"[{i}/{len(tables)}] {table}")
                
                # Obter colunas
                cur.execute(f"""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = %s
                    ORDER BY ordinal_position;
                """, (table,))
                columns = cur.fetchall()
                col_names = [col[0] for col in columns]
                
                # CREATE TABLE
                f.write(f"\n-- Table: {table}\n")
                f.write(f"DROP TABLE IF EXISTS {table} CASCADE;\n")
                f.write(f"CREATE TABLE {table} (\n")
                
                col_defs = []
                for col_name, data_type, is_nullable in columns:
                    nullable = "" if is_nullable == 'YES' else "NOT NULL"
                    col_def = f"    {col_name} {data_type} {nullable}".strip()
                    col_defs.append(col_def)
                
                f.write(",\n".join(col_defs))
                f.write("\n);\n\n")
                
                # Dados
                cur.execute(f"SELECT * FROM {table};")
                rows = cur.fetchall()
                
                if rows:
                    f.write(f"-- Data: {table} ({len(rows)} rows)\n")
                    for row in rows:
                        values = []
                        for val in row:
                            if val is None:
                                values.append("NULL")
                            elif isinstance(val, str):
                                val_escaped = val.replace("'", "''").replace("\\", "\\\\")
                                values.append(f"'{val_escaped}'")
                            elif isinstance(val, (int, float)):
                                values.append(str(val))
                            elif isinstance(val, bool):
                                values.append("TRUE" if val else "FALSE")
                            elif hasattr(val, 'isoformat'):
                                values.append(f"'{val.isoformat()}'")
                            else:
                                val_str = str(val).replace("'", "''")
                                values.append(f"'{val_str}'")
                        
                        f.write(f"INSERT INTO {table} ({', '.join(col_names)}) VALUES ({', '.join(values)});\n")
                    f.write("\n")
        
        cur.close()
        conn.close()
        
        file_size = os.path.getsize(output_file) / (1024 * 1024)
        print(f"\n[OK] Exportacao concluida!")
        print(f"Arquivo: {output_file} ({file_size:.2f} MB)")
        return True
        
    except Exception as e:
        print(f"[ERRO] Erro: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("=" * 60)
    print("SALVADOR DE DADOS - Banco Suspenso")
    print("=" * 60)
    print()
    print("Tentando conectar ao banco de dados...")
    print("(Pode levar alguns segundos)\n")
    
    # Tentar múltiplas formas
    conn = tentar_conexao_psycopg()
    if conn:
        print()
        success = exportar_dados(conn)
        sys.exit(0 if success else 1)
    
    engine = tentar_conexao_sqlalchemy()
    if engine:
        print()
        success = exportar_dados(engine)
        sys.exit(0 if success else 1)
    
    # Se chegou aqui, não conseguiu conectar
    print()
    print("=" * 60)
    print("[ERRO] Nao foi possivel conectar ao banco de dados!")
    print("=" * 60)
    print()
    print("O banco pode ter sido deletado ou estar completamente inacessivel.")
    print()
    print("OPCOES ULTIMAS:")
    print()
    print("1. Verificar backups no Render Dashboard:")
    print("   - Acesse https://dashboard.render.com")
    print("   - Vá para o serviço PostgreSQL")
    print("   - Procure por 'Backups' ou 'Snapshots'")
    print("   - Baixe qualquer backup disponível")
    print()
    print("2. Verificar se há backup local:")
    print("   - Procure por arquivos .sql ou .dump na pasta do projeto")
    print("   - Verifique pasta 'backups' se existir")
    print()
    print("3. Contatar suporte do Render:")
    print("   - Pode haver backups que não aparecem no dashboard")
    print("   - Render mantém dados por 90 dias mesmo se suspenso")
    print()
    print("4. Verificar logs da aplicação:")
    print("   - Os logs podem ter informações sobre últimas conexões")
    print("   - Pode indicar quando o banco foi desativado")
    print()
    
    sys.exit(1)

if __name__ == '__main__':
    main()

