# Como Verificar e Recuperar Backups do Render

## ⚠️ IMPORTANTE: Banco Suspenso na Versão Free

Se você está na versão free do Render, o banco pode ter sido suspenso ou deletado, mas há algumas formas de recuperar dados:

## Opção 1: Verificar Backups Automáticos no Dashboard

1. **Acesse o Render Dashboard:**
   - https://dashboard.render.com
   - Faça login

2. **Navegue até o Banco de Dados:**
   - Procure pelo serviço PostgreSQL
   - Nome: `clinica_db_cxsq` ou similar
   - Host: `dpg-d4s4dkeuk2gs73a52mug-a`

3. **Verifique a Aba "Backups":**
   - Clique no serviço PostgreSQL
   - Procure por uma aba/chamada "Backups", "Snapshots" ou "Backups & Snapshots"
   - O Render pode ter backups automáticos salvos

4. **Baixe o Backup:**
   - Se houver backups, clique em "Download"
   - Geralmente são arquivos `.dump` ou `.sql`

## Opção 2: Tentar Reativar Temporariamente (Pode Funcionar)

Mesmo na versão free, às vezes é possível reativar:

1. **No Dashboard:**
   - Clique no serviço PostgreSQL
   - Procure por botão "Resume" ou "Activate"
   - Clique e aguarde 2-5 minutos

2. **Execute o Script:**
   ```bash
   python salvar_dados_urgente.py
   ```

3. **Após exportar, você pode suspender novamente**

## Opção 3: Usar Terminal Web do Render

1. **No Dashboard:**
   - Vá para o serviço PostgreSQL
   - Clique em "Connect" ou "Shell"
   - Isso abre um terminal web

2. **Execute:**
   ```bash
   pg_dump $DATABASE_URL > backup.sql
   ```
   
   Ou manualmente:
   ```bash
   PGPASSWORD=1GJkXP0EOQYis7RA7bfY3PwmB5OtjUX2 pg_dump -h dpg-d4s4dkeuk2gs73a52mug-a.oregon-postgres.render.com -U clinica_db_cxsq_user -d clinica_db_cxsq > backup.sql
   ```

3. **Baixe o arquivo:**
   - Use o botão de download do terminal ou copie o conteúdo

## Opção 4: Verificar Backups na Aplicação

Se sua aplicação fez backups automáticos:

1. **Procure na pasta do projeto:**
   ```bash
   dir *.sql
   dir *.dump
   dir backups\
   ```

2. **Verifique logs:**
   - Os logs podem indicar se houve backup automático
   - Procure por mensagens de "backup" ou "export"

## Opção 5: Contatar Suporte do Render

1. **Acesse:**
   - https://render.com/contact ou abra um ticket no dashboard

2. **Explique:**
   - Que você precisa recuperar dados de um banco suspenso
   - O nome do serviço: `clinica_db_cxsq`
   - O host: `dpg-d4s4dkeuk2gs73a52mug-a`
   - Que está na versão free

3. **Peça:**
   - Se há backups disponíveis que não aparecem no dashboard
   - Se é possível reativar temporariamente para exportar

## Opção 6: Verificar Outras Fontes de Dados

1. **Logs da Aplicação:**
   - Os logs podem ter dados importantes
   - Verifique logs antigos no Render Dashboard

2. **Código Fonte:**
   - Verifique se há scripts de seed ou população de dados
   - Pode ter dados iniciais para recriar

3. **Backups Locais:**
   - Verifique seu computador por backups anteriores
   - Procure em pastas de downloads, documentos, etc.

## Informações do Banco para Suporte

- **Host:** dpg-d4s4dkeuk2gs73a52mug-a.oregon-postgres.render.com
- **Database:** clinica_db_cxsq
- **User:** clinica_db_cxsq_user
- **Região:** Oregon (US)

## Após Recuperar os Dados

1. **Criar novo banco no Neon.tech:**
   - Acesse https://console.neon.tech
   - Crie um novo projeto e banco de dados

2. **Importar o backup:**
   ```bash
   psql "postgresql://user:pass@host/db" -f backup.sql
   ```

3. **Atualizar DATABASE_URL na aplicação**

## Script de Último Recurso

Execute:
```bash
python salvar_dados_urgente.py
```

Este script tenta múltiplas formas de conexão e pode funcionar mesmo se o banco estiver instável.

