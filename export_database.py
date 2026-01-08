#!/usr/bin/env python
"""
Script para exportar o banco de dados PostgreSQL do Render
"""
import os
import sys
import subprocess
from datetime import datetime

# URL do banco de dados
DATABASE_URL = "postgresql://clinica_db_cxsq_user:1GJkXP0EOQYis7RA7bfY3PwmB5OtjUX2@dpg-d4s4dkeuk2gs73a52mug-a.oregon-postgres.render.com/clinica_db_cxsq"

def export_with_pg_dump():
    """Tenta exportar usando pg_dump (método mais rápido)"""
    try:
        # Parse da URL
        # postgresql://user:password@host:port/database
        url_parts = DATABASE_URL.replace("postgresql://", "").split("@")
        user_pass = url_parts[0].split(":")
        host_db = url_parts[1].split("/")
        
        username = user_pass[0]
        password = user_pass[1]
        host_port = host_db[0].split(":")
        host = host_port[0]
        port = host_port[1] if len(host_port) > 1 else "5432"
        database = host_db[1]
        
        # Nome do arquivo de saída
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"database_export_{timestamp}.sql"
        
        print(f"[*] Exportando banco de dados...")
        print(f"   Host: {host}")
        print(f"   Database: {database}")
        print(f"   Output: {output_file}")
        
        # Configurar variável de ambiente para senha
        env = os.environ.copy()
        env['PGPASSWORD'] = password
        
        # Comando pg_dump
        cmd = [
            'pg_dump',
            f'--host={host}',
            f'--port={port}',
            f'--username={username}',
            '--no-password',  # Usa PGPASSWORD da env
            '--verbose',
            '--clean',  # Inclui comandos DROP
            '--if-exists',  # IF EXISTS nos DROP
            '--create',  # Inclui CREATE DATABASE
            '--format=plain',  # Formato SQL texto
            '--encoding=UTF8',
            database
        ]
        
        # Executar pg_dump
        with open(output_file, 'w', encoding='utf-8') as f:
            result = subprocess.run(
                cmd,
                env=env,
                stdout=f,
                stderr=subprocess.PIPE,
                text=True
            )
        
        if result.returncode == 0:
            file_size = os.path.getsize(output_file) / (1024 * 1024)  # MB
            print(f"[OK] Exportacao concluida com sucesso!")
            print(f"   Arquivo: {output_file}")
            print(f"   Tamanho: {file_size:.2f} MB")
            return True
        else:
            print(f"[ERRO] Erro ao executar pg_dump:")
            print(result.stderr)
            return False
            
    except FileNotFoundError:
        print("[AVISO] pg_dump nao encontrado. Tentando metodo alternativo...")
        return False
    except Exception as e:
        print(f"[ERRO] Erro: {e}")
        return False

def export_with_psycopg():
    """Exporta usando psycopg (método alternativo)"""
    try:
        import psycopg
        from psycopg.types.json import Json
        
        print(f"[*] Exportando banco de dados usando psycopg...")
        
        # Parse da URL para conexão explícita
        url_parts = DATABASE_URL.replace("postgresql://", "").split("@")
        user_pass = url_parts[0].split(":")
        host_db = url_parts[1].split("/")
        
        username = user_pass[0]
        password = user_pass[1]
        host_port = host_db[0].split(":")
        host = host_port[0]
        port = int(host_port[1]) if len(host_port) > 1 else 5432
        database = host_db[1].split("?")[0]  # Remover query params se houver
        
        # Conectar ao banco com SSL explícito
        # Tentar diferentes modos SSL
        print(f"   Conectando a {host}:{port}...")
        
        ssl_modes = ['require', 'prefer', 'allow']
        conn = None
        
        for ssl_mode in ssl_modes:
            try:
                print(f"   Tentando SSL mode: {ssl_mode}...")
                conn = psycopg.connect(
                    host=host,
                    port=port,
                    dbname=database,
                    user=username,
                    password=password,
                    sslmode=ssl_mode,
                    connect_timeout=10
                )
                print(f"   Conexao estabelecida com SSL mode: {ssl_mode}")
                break
            except Exception as e:
                if ssl_mode == ssl_modes[-1]:  # Última tentativa
                    raise e
                continue
        
        if not conn:
            raise Exception("Nao foi possivel estabelecer conexao com nenhum modo SSL")
        cur = conn.cursor()
        
        # Nome do arquivo de saída
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"database_export_{timestamp}.sql"
        
        print(f"   Output: {output_file}")
        
        # Obter informações do banco
        cur.execute("SELECT current_database(), version();")
        db_info = cur.fetchone()
        print(f"   Database: {db_info[0]}")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            # Cabeçalho
            f.write(f"-- Database Export\n")
            f.write(f"-- Database: {db_info[0]}\n")
            f.write(f"-- PostgreSQL Version: {db_info[1]}\n")
            f.write(f"-- Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"--\n\n")
            
            # Obter todas as tabelas
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
                ORDER BY table_name;
            """)
            tables = [row[0] for row in cur.fetchall()]
            
            print(f"   Encontradas {len(tables)} tabelas")
            
            # Exportar estrutura e dados de cada tabela
            for table in tables:
                print(f"   Exportando tabela: {table}")
                
                # Obter estrutura da tabela
                cur.execute(f"""
                    SELECT column_name, data_type, character_maximum_length, 
                           is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_name = %s AND table_schema = 'public'
                    ORDER BY ordinal_position;
                """, (table,))
                
                columns = cur.fetchall()
                
                # Criar CREATE TABLE
                f.write(f"\n-- Table: {table}\n")
                f.write(f"DROP TABLE IF EXISTS {table} CASCADE;\n")
                f.write(f"CREATE TABLE {table} (\n")
                
                col_defs = []
                for col in columns:
                    col_name, data_type, max_length, is_nullable, default = col
                    col_def = f"    {col_name} {data_type}"
                    if max_length:
                        col_def += f"({max_length})"
                    if is_nullable == 'NO':
                        col_def += " NOT NULL"
                    if default:
                        col_def += f" DEFAULT {default}"
                    col_defs.append(col_def)
                
                f.write(",\n".join(col_defs))
                f.write("\n);\n\n")
                
                # Exportar dados
                cur.execute(f"SELECT * FROM {table};")
                rows = cur.fetchall()
                
                if rows:
                    f.write(f"-- Data for table: {table}\n")
                    col_names = [col[0] for col in columns]
                    
                    for row in rows:
                        values = []
                        for i, val in enumerate(row):
                            if val is None:
                                values.append("NULL")
                            elif isinstance(val, str):
                                # Escapar aspas simples
                                val_escaped = val.replace("'", "''")
                                values.append(f"'{val_escaped}'")
                            elif isinstance(val, (int, float)):
                                values.append(str(val))
                            elif isinstance(val, bool):
                                values.append("TRUE" if val else "FALSE")
                            elif isinstance(val, (bytes, bytearray)):
                                # Para dados binários, usar hex
                                values.append(f"'\\x{val.hex()}'")
                            else:
                                val_str = str(val).replace("'", "''")
                                values.append(f"'{val_str}'")
                        
                        f.write(f"INSERT INTO {table} ({', '.join(col_names)}) VALUES ({', '.join(values)});\n")
                    f.write("\n")
        
        cur.close()
        conn.close()
        
        file_size = os.path.getsize(output_file) / (1024 * 1024)  # MB
        print(f"[OK] Exportacao concluida com sucesso!")
        print(f"   Arquivo: {output_file}")
        print(f"   Tamanho: {file_size:.2f} MB")
        return True
        
    except ImportError:
        print("[ERRO] psycopg nao esta instalado. Instale com: pip install psycopg[binary]")
        return False
    except Exception as e:
        print(f"[ERRO] Erro ao exportar: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Função principal"""
    print("=" * 60)
    print("Exportador de Banco de Dados PostgreSQL")
    print("=" * 60)
    print()
    
    # Tentar primeiro com pg_dump (mais rápido e completo)
    if not export_with_pg_dump():
        # Se falhar, tentar com psycopg
        if not export_with_psycopg():
            print()
            print("[ERRO] Nao foi possivel exportar o banco de dados.")
            print()
            print("Opções:")
            print("1. Instale pg_dump (parte do PostgreSQL):")
            print("   - Windows: https://www.postgresql.org/download/windows/")
            print("   - Linux: sudo apt-get install postgresql-client")
            print("   - macOS: brew install postgresql")
            print()
            print("2. Ou instale psycopg:")
            print("   pip install psycopg[binary]")
            sys.exit(1)
    
    print()
    print("=" * 60)

if __name__ == '__main__':
    main()

