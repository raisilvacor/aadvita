#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Database Export Tool
Exporta banco de dados PostgreSQL para arquivo SQL
Usa apenas bibliotecas já instaladas no projeto
"""

import os
import sys
from datetime import datetime
from typing import Optional, List, Tuple

# Configuração do banco de dados
DATABASE_URL = "postgresql://clinica_db_cxsq_user:1GJkXP0EOQYis7RA7bfY3PwmB5OtjUX2@dpg-d4s4dkeuk2gs73a52mug-a.oregon-postgres.render.com/clinica_db_cxsq"


class DatabaseExporter:
    """Classe para exportar banco de dados PostgreSQL"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = None
        self.output_file = None
        
    def connect(self) -> bool:
        """Estabelece conexão com o banco de dados"""
        try:
            from sqlalchemy import create_engine, text
            
            # Converter para usar psycopg3 (já instalado)
            if self.database_url.startswith('postgresql://'):
                db_url = self.database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
            else:
                db_url = self.database_url
            
            # Adicionar parâmetros SSL
            if '?' not in db_url:
                db_url = f"{db_url}?sslmode=require"
            else:
                db_url = f"{db_url}&sslmode=require"
            
            print("Conectando ao banco de dados...", end=" ", flush=True)
            
            self.engine = create_engine(
                db_url,
                echo=False,
                pool_pre_ping=True,
                connect_args={
                    "sslmode": "require",
                    "connect_timeout": 10
                }
            )
            
            # Testar conexão
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT current_database(), version();"))
                db_info = result.fetchone()
                print("[OK] Conectado")
                print(f"  Database: {db_info[0]}")
                print(f"  PostgreSQL: {db_info[1].split(',')[0]}")
                return True
                
        except Exception as e:
            error_msg = str(e)
            print("[ERRO] Falhou")
            
            if "could not translate host name" in error_msg or "Name or service not known" in error_msg:
                print("\nERRO: Banco de dados nao encontrado ou suspenso.")
                print("\nSolucoes:")
                print("1. Verifique se o banco esta ativo no Render Dashboard")
                print("2. Tente reativar o banco temporariamente")
                print("3. Verifique backups automaticos no Render Dashboard")
            elif "SSL" in error_msg or "connection" in error_msg.lower():
                print(f"\nERRO: {error_msg[:200]}")
                print("\nO banco pode estar suspenso ou inacessivel.")
                print("Tente reativar o banco no Render Dashboard antes de executar novamente.")
            else:
                print(f"\nERRO: {error_msg[:200]}")
            return False
    
    def get_tables(self) -> List[str]:
        """Retorna lista de tabelas do banco"""
        from sqlalchemy import inspect
        inspector = inspect(self.engine)
        return inspector.get_table_names()
    
    def export_table_structure(self, table: str, file_handle) -> Tuple[List[str], int]:
        """Exporta estrutura de uma tabela"""
        from sqlalchemy import inspect
        
        inspector = inspect(self.engine)
        columns = inspector.get_columns(table)
        col_names = [col['name'] for col in columns]
        
        # Escrever DROP TABLE
        file_handle.write(f"\n-- ============================================\n")
        file_handle.write(f"-- Table: {table}\n")
        file_handle.write(f"-- ============================================\n")
        file_handle.write(f"DROP TABLE IF EXISTS {table} CASCADE;\n\n")
        
        # Escrever CREATE TABLE
        file_handle.write(f"CREATE TABLE {table} (\n")
        
        col_defs = []
        for col in columns:
            col_name = col['name']
            col_type = str(col['type'])
            
            # Limpar tipo SQLAlchemy para formato SQL padrão
            if 'VARCHAR' in col_type.upper():
                if hasattr(col['type'], 'length') and col['type'].length:
                    col_type = f"VARCHAR({col['type'].length})"
                else:
                    col_type = "TEXT"
            elif 'INTEGER' in col_type.upper() or 'INT' in col_type.upper():
                col_type = "INTEGER"
            elif 'BOOLEAN' in col_type.upper() or 'BOOL' in col_type.upper():
                col_type = "BOOLEAN"
            elif 'TIMESTAMP' in col_type.upper() or 'DATETIME' in col_type.upper():
                col_type = "TIMESTAMP"
            elif 'DATE' in col_type.upper():
                col_type = "DATE"
            elif 'TEXT' in col_type.upper():
                col_type = "TEXT"
            
            nullable = "" if col.get('nullable', True) else " NOT NULL"
            default = f" DEFAULT {col['default']}" if col.get('default') else ""
            
            col_def = f"    {col_name} {col_type}{nullable}{default}".strip()
            col_defs.append(col_def)
        
        file_handle.write(",\n".join(col_defs))
        file_handle.write("\n);\n\n")
        
        return col_names, len(columns)
    
    def export_table_data(self, table: str, col_names: List[str], file_handle) -> int:
        """Exporta dados de uma tabela"""
        from sqlalchemy import text
        
        row_count = 0
        
        try:
            with self.engine.connect() as conn:
                # Usar stream para tabelas grandes
                result = conn.execute(text(f"SELECT * FROM {table}"))
                
                file_handle.write(f"-- Data for table: {table}\n")
                
                batch_size = 1000
                batch = []
                
                for row in result:
                    values = []
                    for val in row:
                        if val is None:
                            values.append("NULL")
                        elif isinstance(val, str):
                            # Escapar caracteres especiais
                            val_escaped = val.replace("\\", "\\\\").replace("'", "''")
                            values.append(f"'{val_escaped}'")
                        elif isinstance(val, (int, float)):
                            values.append(str(val))
                        elif isinstance(val, bool):
                            values.append("TRUE" if val else "FALSE")
                        elif hasattr(val, 'isoformat'):  # datetime/date
                            values.append(f"'{val.isoformat()}'")
                        elif isinstance(val, bytes):
                            # Dados binários - usar hex
                            values.append(f"'\\x{val.hex()}'")
                        else:
                            val_str = str(val).replace("\\", "\\\\").replace("'", "''")
                            values.append(f"'{val_str}'")
                    
                    batch.append(f"INSERT INTO {table} ({', '.join(col_names)}) VALUES ({', '.join(values)});\n")
                    row_count += 1
                    
                    # Escrever em lotes para melhor performance
                    if len(batch) >= batch_size:
                        file_handle.writelines(batch)
                        file_handle.flush()
                        batch = []
                        if row_count % 100 == 0:
                            print(f"    {row_count} registros...", end="\r", flush=True)
                
                # Escrever resto do batch
                if batch:
                    file_handle.writelines(batch)
                
                file_handle.write("\n")
                
        except Exception as e:
            print(f"\n    AVISO: Erro ao exportar dados de {table}: {str(e)[:100]}")
            file_handle.write(f"-- ERRO ao exportar dados: {str(e)[:200]}\n\n")
        
        return row_count
    
    def export(self, output_file: Optional[str] = None) -> bool:
        """Exporta todo o banco de dados"""
        if not self.engine:
            print("ERRO: Não há conexão com o banco de dados.")
            return False
        
        try:
            from sqlalchemy import text
            
            # Gerar nome do arquivo se não fornecido
            if not output_file:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = f"database_export_{timestamp}.sql"
            
            self.output_file = output_file
            
            print(f"\nExportando para: {output_file}")
            print("-" * 60)
            
            # Obter lista de tabelas
            tables = self.get_tables()
            total_tables = len(tables)
            
            if total_tables == 0:
                print("AVISO: Nenhuma tabela encontrada no banco de dados.")
                return False
            
            print(f"Tabelas encontradas: {total_tables}\n")
            
            # Abrir arquivo para escrita
            with open(output_file, 'w', encoding='utf-8') as f:
                # Escrever cabeçalho
                f.write("-- ============================================\n")
                f.write("-- Database Export\n")
                f.write(f"-- Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"-- Database: {self.database_url.split('@')[1].split('/')[1] if '@' in self.database_url else 'unknown'}\n")
                f.write(f"-- Total Tables: {total_tables}\n")
                f.write("-- ============================================\n\n")
                
                # Configurar encoding
                f.write("SET client_encoding = 'UTF8';\n\n")
                
                total_rows = 0
                
                # Exportar cada tabela
                for idx, table in enumerate(tables, 1):
                    print(f"[{idx}/{total_tables}] {table}", end=" ... ", flush=True)
                    
                    try:
                        # Exportar estrutura
                        col_names, col_count = self.export_table_structure(table, f)
                        
                        # Exportar dados
                        row_count = self.export_table_data(table, col_names, f)
                        total_rows += row_count
                        
                        print(f"[OK] ({row_count} registros, {col_count} colunas)")
                        
                    except Exception as e:
                        print(f"[ERRO] {str(e)[:50]}")
                        f.write(f"-- ERRO ao exportar tabela {table}: {str(e)[:200]}\n\n")
                
                # Escrever rodapé
                f.write("\n-- ============================================\n")
                f.write(f"-- Export completed\n")
                f.write(f"-- Total Tables: {total_tables}\n")
                f.write(f"-- Total Rows: {total_rows}\n")
                f.write(f"-- Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("-- ============================================\n")
            
            # Estatísticas finais
            file_size = os.path.getsize(output_file)
            file_size_mb = file_size / (1024 * 1024)
            
            print("-" * 60)
            print(f"\n[OK] Exportacao concluida com sucesso!")
            print(f"  Arquivo: {output_file}")
            print(f"  Tamanho: {file_size_mb:.2f} MB ({file_size:,} bytes)")
            print(f"  Tabelas: {total_tables}")
            print(f"  Registros: {total_rows:,}")
            
            return True
            
        except Exception as e:
            print(f"\n[ERRO] Erro durante exportacao: {str(e)}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """Função principal"""
    print("=" * 60)
    print("Database Export Tool")
    print("=" * 60)
    print()
    
    exporter = DatabaseExporter(DATABASE_URL)
    
    # Tentar conectar
    if not exporter.connect():
        print("\nNão foi possível conectar ao banco de dados.")
        print("\nVerifique:")
        print("1. Se o banco está ativo no Render Dashboard")
        print("2. Se a URL do banco está correta")
        print("3. Se há problemas de rede/firewall")
        sys.exit(1)
    
    # Exportar
    success = exporter.export()
    
    if success:
        print("\n" + "=" * 60)
        print("Próximos passos:")
        print("1. Verifique o arquivo SQL gerado")
        print("2. Importe no novo banco de dados:")
        print(f"   psql 'nova_url_do_banco' -f {exporter.output_file}")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\nExportação falhou. Verifique os erros acima.")
        sys.exit(1)


if __name__ == '__main__':
    main()
