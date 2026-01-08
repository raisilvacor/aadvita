# Como Exportar o Banco de Dados do Render

## Método 1: Usando pg_dump (Recomendado)

### Windows

1. **Instale o PostgreSQL Client:**
   - Baixe em: https://www.postgresql.org/download/windows/
   - Ou use o instalador: https://www.enterprisedb.com/downloads/postgres-postgresql-downloads
   - Durante a instalação, certifique-se de instalar as "Command Line Tools"

2. **Execute o comando:**
   ```bash
   set PGPASSWORD=1GJkXP0EOQYis7RA7bfY3PwmB5OtjUX2
   pg_dump -h dpg-d4s4dkeuk2gs73a52mug-a.oregon-postgres.render.com -p 5432 -U clinica_db_cxsq_user -d clinica_db_cxsq -F p -f database_export.sql
   ```

### Linux/Mac

```bash
export PGPASSWORD=1GJkXP0EOQYis7RA7bfY3PwmB5OtjUX2
pg_dump -h dpg-d4s4dkeuk2gs73a52mug-a.oregon-postgres.render.com -p 5432 -U clinica_db_cxsq_user -d clinica_db_cxsq -F p -f database_export.sql
```

## Método 2: Usando o Script Python

Execute:
```bash
python export_database.py
```

**Nota:** O script tentará primeiro usar `pg_dump` e, se não estiver disponível, usará `psycopg`.

## Método 3: Usando psql (Alternativa)

```bash
psql "postgresql://clinica_db_cxsq_user:1GJkXP0EOQYis7RA7bfY3PwmB5OtjUX2@dpg-d4s4dkeuk2gs73a52mug-a.oregon-postgres.render.com:5432/clinica_db_cxsq" -c "\copy (SELECT * FROM table_name) TO 'export.csv' CSV HEADER"
```

## Informações da Conexão

- **Host:** dpg-d4s4dkeuk2gs73a52mug-a.oregon-postgres.render.com
- **Porta:** 5432
- **Database:** clinica_db_cxsq
- **User:** clinica_db_cxsq_user
- **Password:** 1GJkXP0EOQYis7RA7bfY3PwmB5OtjUX2

## Importante

- O arquivo de exportação será salvo na pasta principal do projeto
- O arquivo terá o formato `.sql` e pode ser importado usando `psql` ou ferramentas de gerenciamento de banco
- Certifique-se de ter espaço em disco suficiente para o dump completo

