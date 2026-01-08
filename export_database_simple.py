#!/usr/bin/env python
"""
Script simples para exportar banco de dados usando apenas bibliotecas já instaladas
"""
import os
from datetime import datetime
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import URL

# URL do banco de dados
DATABASE_URL = "postgresql://clinica_db_cxsq_user:1GJkXP0EOQYis7RA7bfY3PwmB5OtjUX2@dpg-d4s4dkeuk2gs73a52mug-a.oregon-postgres.render.com/clinica_db_cxsq"

def export_database():
    """Exporta o banco de dados usando SQLAlchemy"""
    try:
        print("=" * 60)
        print("Exportador de Banco de Dados")
        print("=" * 60)
        print()
        
        # Converter para usar psycopg3 (já instalado)
        if DATABASE_URL.startswith('postgresql://'):
            db_url = DATABASE_URL.replace('postgresql://', 'postgresql+psycopg://', 1)
        else:
            db_url = DATABASE_URL
        
        # Adicionar parâmetros SSL à URL
        if '?' not in db_url:
            db_url = f"{db_url}?sslmode=require"
        else:
            db_url = f"{db_url}&sslmode=require"
        
        print("[*] Conectando ao banco de dados...")
        engine = create_engine(db_url, echo=False, pool_pre_ping=True, connect_args={"sslmode": "require"})
        
        # Testar conexão
        with engine.connect() as conn:
            result = conn.execute(text("SELECT current_database(), version();"))
            db_info = result.fetchone()
            print(f"[OK] Conectado ao banco: {db_info[0]}")
            print()
        
        # Nome do arquivo de saída
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"database_export_{timestamp}.sql"
        
        print(f"[*] Exportando para: {output_file}")
        print()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            # Cabeçalho
            f.write(f"-- Database Export\n")
            f.write(f"-- Database: {db_info[0]}\n")
            f.write(f"-- PostgreSQL Version: {db_info[1]}\n")
            f.write(f"-- Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"--\n\n")
            
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            
            print(f"[*] Encontradas {len(tables)} tabelas")
            print()
            
            # Exportar cada tabela
            for i, table in enumerate(tables, 1):
                print(f"[{i}/{len(tables)}] Exportando tabela: {table}")
                
                # Obter estrutura da tabela
                columns = inspector.get_columns(table)
                
                # Criar CREATE TABLE
                f.write(f"\n-- Table: {table}\n")
                f.write(f"DROP TABLE IF EXISTS {table} CASCADE;\n")
                f.write(f"CREATE TABLE {table} (\n")
                
                col_defs = []
                for col in columns:
                    col_name = col['name']
                    col_type = col['type']
                    nullable = "NOT NULL" if not col.get('nullable', True) else ""
                    default = f" DEFAULT {col['default']}" if col.get('default') else ""
                    
                    # Converter tipo SQLAlchemy para SQL
                    type_str = str(col_type)
                    if 'VARCHAR' in type_str or 'CHAR' in type_str:
                        if hasattr(col_type, 'length'):
                            type_str = f"VARCHAR({col_type.length})"
                        else:
                            type_str = "TEXT"
                    elif 'INTEGER' in type_str:
                        type_str = "INTEGER"
                    elif 'BOOLEAN' in type_str:
                        type_str = "BOOLEAN"
                    elif 'TIMESTAMP' in type_str or 'DATETIME' in type_str:
                        type_str = "TIMESTAMP"
                    elif 'DATE' in type_str:
                        type_str = "DATE"
                    elif 'TEXT' in type_str:
                        type_str = "TEXT"
                    
                    col_def = f"    {col_name} {type_str} {nullable} {default}".strip()
                    col_defs.append(col_def)
                
                f.write(",\n".join(col_defs))
                f.write("\n);\n\n")
                
                # Exportar dados
                with engine.connect() as conn:
                    result = conn.execute(text(f"SELECT * FROM {table};"))
                    rows = result.fetchall()
                    
                    if rows:
                        f.write(f"-- Data for table: {table}\n")
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
                                elif hasattr(val, 'isoformat'):  # datetime/date
                                    values.append(f"'{val.isoformat()}'")
                                else:
                                    val_str = str(val).replace("'", "''")
                                    values.append(f"'{val_str}'")
                            
                            f.write(f"INSERT INTO {table} ({', '.join(col_names)}) VALUES ({', '.join(values)});\n")
                        f.write("\n")
        
        file_size = os.path.getsize(output_file) / (1024 * 1024)  # MB
        print()
        print("=" * 60)
        print("[OK] Exportacao concluida com sucesso!")
        print(f"Arquivo: {output_file}")
        print(f"Tamanho: {file_size:.2f} MB")
        print("=" * 60)
        return True
        
    except Exception as e:
        print()
        print("[ERRO] Erro ao exportar:")
        print(str(e))
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    export_database()

