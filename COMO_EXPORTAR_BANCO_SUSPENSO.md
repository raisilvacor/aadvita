# Como Exportar Banco de Dados Suspenso do Render

## Situação
O banco de dados está suspenso no Render e você precisa extrair os dados.

## Soluções

### Opção 1: Reativar Temporariamente o Banco (Recomendado)

1. **Acesse o Render Dashboard:**
   - Vá para https://dashboard.render.com
   - Faça login na sua conta

2. **Encontre o Banco de Dados:**
   - Procure pelo serviço PostgreSQL: `clinica_db_cxsq`
   - Ou pelo host: `dpg-d4s4dkeuk2gs73a52mug-a`

3. **Reative o Banco:**
   - Clique no serviço de banco de dados
   - Clique no botão **"Resume"** ou **"Resume Service"**
   - Aguarde 2-5 minutos para o banco inicializar

4. **Execute o Script:**
   ```bash
   python export_database_final.py
   ```

5. **Após Exportar:**
   - O arquivo SQL será salvo na pasta do projeto
   - Você pode suspender o banco novamente se quiser

### Opção 2: Usar o Render Dashboard para Exportar

1. **No Render Dashboard:**
   - Vá para o serviço de banco de dados
   - Clique em **"Connect"** ou **"Shell"**
   - Use o terminal web do Render

2. **Execute no Terminal:**
   ```bash
   pg_dump $DATABASE_URL > backup.sql
   ```
   Ou:
   ```bash
   PGPASSWORD=1GJkXP0EOQYis7RA7bfY3PwmB5OtjUX2 pg_dump -h dpg-d4s4dkeuk2gs73a52mug-a.oregon-postgres.render.com -U clinica_db_cxsq_user -d clinica_db_cxsq > backup.sql
   ```

### Opção 3: Verificar Backups Automáticos

1. **No Render Dashboard:**
   - Vá para o serviço de banco de dados
   - Procure pela seção **"Backups"** ou **"Snapshots"**
   - O Render pode ter backups automáticos salvos

2. **Baixar Backup:**
   - Se houver backups disponíveis, você pode baixá-los diretamente
   - Geralmente estão em formato `.dump` ou `.sql`

### Opção 4: Usar o Endpoint da Aplicação (Quando Banco Estiver Ativo)

1. **Reative o banco** (seguir Opção 1)

2. **Acesse:**
   ```
   https://www.aadvita.org.br/admin/export-database
   ```
   (Você precisa estar logado como administrador)

3. **O arquivo será baixado automaticamente**

## Informações do Banco

- **Host:** dpg-d4s4dkeuk2gs73a52mug-a.oregon-postgres.render.com
- **Database:** clinica_db_cxsq
- **User:** clinica_db_cxsq_user
- **Password:** 1GJkXP0EOQYis7RA7bfY3PwmB5OtjUX2
- **URL Completa:** postgresql://clinica_db_cxsq_user:1GJkXP0EOQYis7RA7bfY3PwmB5OtjUX2@dpg-d4s4dkeuk2gs73a52mug-a.oregon-postgres.render.com/clinica_db_cxsq

## Importante

- **Bancos suspensos no Render são mantidos por 90 dias** antes de serem deletados
- Após reativar, o banco fica ativo até você suspender novamente
- O script `export_database_final.py` funciona apenas quando o banco estiver ativo
- Certifique-se de ter espaço em disco suficiente para o dump

## Próximos Passos Após Exportar

1. **Criar novo banco no Neon.tech** (ou outro provedor)
2. **Importar o arquivo SQL:**
   ```bash
   psql -h novo-host -U novo-user -d novo-database -f database_export_YYYYMMDD_HHMMSS.sql
   ```
3. **Atualizar DATABASE_URL** na aplicação

