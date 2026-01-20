#!/usr/bin/env python
"""
Script para exportar banco de dados PostgreSQL
Funciona quando o banco estiver ativo no Render
"""
import os
import sys
from datetime import datetime

# URL do banco de dados
DATABASE_URL = "postgresql://clinica_db_cxsq_user:1GJkXP0EOQYis7RA7bfY3PwmB5OtjUX2@dpg-d4s4dkeuk2gs73a52mug-a.oregon-postgres.render.com/clinica_db_cxsq"

def export_with_sqlalchemy():
    """Exporta usando SQLAlchemy (já instalado no projeto)"""
    try:
        from sqlalchemy import create_engine, text, inspect
        
        print("=" * 60)
        print("Exportador de Banco de Dados")
        print("=" * 60)
        print()
        
        # Converter para usar psycopg3
        if DATABASE_URL.startswith('postgresql://'):
            db_url = DATABASE_URL.replace('postgresql://', 'postgresql+psycopg://', 1)
        else:
            db_url = DATABASE_URL
        
        # Adicionar SSL
        if '?' not in db_url:
            db_url = f"{db_url}?sslmode=require"
        else:
            db_url = f"{db_url}&sslmode=require"
        
        print("[*] Conectando ao banco de dados...")
        print(f"    Host: dpg-d4s4dkeuk2gs73a52mug-a.oregon-postgres.render.com")
        print()
        
        engine = create_engine(db_url, echo=False, pool_pre_ping=True, 
                              connect_args={"sslmode": "require", "connect_timeout": 10})
        
        # Testar conexão
        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT current_database(), version();"))
                db_info = result.fetchone()
                print(f"[OK] Conectado ao banco: {db_info[0]}")
                print()
        except Exception as e:
            print(f"[ERRO] Nao foi possivel conectar ao banco de dados!")
            print(f"       Erro: {str(e)[:200]}")
            print()
            print("O banco pode estar suspenso no Render.")
            print("Para reativar:")
            print("1. Acesse https://dashboard.render.com")
            print("2. Vá para o serviço de banco de dados")
            print("3. Clique em 'Resume' para reativar")
            print("4. Aguarde alguns minutos e execute este script novamente")
            return False
        
        # Nome do arquivo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"database_export_{timestamp}.sql"
        
        print(f"[*] Exportando para: {output_file}")
        print()
        
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        print(f"[*] Encontradas {len(tables)} tabelas")
        print()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            # Cabeçalho
            f.write(f"-- Database Export\n")
            f.write(f"-- Database: {db_info[0]}\n")
            f.write(f"-- PostgreSQL Version: {db_info[1]}\n")
            f.write(f"-- Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"-- Tables: {len(tables)}\n")
            f.write(f"--\n\n")
            
            # Exportar cada tabela
            for i, table in enumerate(tables, 1):
                print(f"[{i}/{len(tables)}] Exportando: {table}")
                
                # Obter estrutura
                columns = inspector.get_columns(table)
                
                # CREATE TABLE
                f.write(f"\n-- Table: {table}\n")
                f.write(f"DROP TABLE IF EXISTS {table} CASCADE;\n")
                f.write(f"CREATE TABLE {table} (\n")
                
                col_defs = []
                for col in columns:
                    col_name = col['name']
                    col_type = str(col['type'])
                    nullable = "" if col.get('nullable', True) else "NOT NULL"
                    default = f" DEFAULT {col['default']}" if col.get('default') else ""
                    col_def = f"    {col_name} {col_type} {nullable} {default}".strip()
                    col_defs.append(col_def)
                
                f.write(",\n".join(col_defs))
                f.write("\n);\n\n")
                
                # Exportar dados
                with engine.connect() as conn:
                    result = conn.execute(text(f"SELECT * FROM {table};"))
                    rows = result.fetchall()
                    
                    if rows:
                        f.write(f"-- Data for table: {table} ({len(rows)} rows)\n")
                        col_names = [col['name'] for col in columns]
                        
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
        print()
        print("=" * 60)
        print("[OK] Exportacao concluida com sucesso!")
        print(f"Arquivo: {output_file}")
        print(f"Tamanho: {file_size:.2f} MB")
        print("=" * 60)
        return True
        
    except ImportError as e:
        print(f"[ERRO] Biblioteca nao encontrada: {e}")
        print("Execute: pip install -r requirements.txt")
        return False
    except Exception as e:
        print(f"[ERRO] Erro ao exportar: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = export_with_sqlalchemy()
    sys.exit(0 if success else 1)

