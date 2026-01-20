# Como Exportar Banco de Dados do Render

## ⚠️ Situação Atual

O banco de dados está **suspenso** no Render (versão free). Para exportar os dados, é necessário **reativar temporariamente**.

## 📋 Passo a Passo Completo

### 1. Reativar o Banco no Render

1. **Acesse:** https://dashboard.render.com
2. **Faça login** na sua conta
3. **Navegue até o serviço PostgreSQL:**
   - Procure por: `clinica_db_cxsq`
   - Ou host: `dpg-d4s4dkeuk2gs73a52mug-a`
4. **Clique no serviço de banco de dados**
5. **Procure o botão "Resume" ou "Activate"**
6. **Clique para reativar**
7. **Aguarde 2-5 minutos** para o banco inicializar completamente

### 2. Verificar se o Banco Está Ativo

- No Dashboard, o status deve mudar para "Active" ou "Running"
- Aguarde alguns minutos após clicar em "Resume"

### 3. Executar o Script de Exportação

No terminal/PowerShell, execute:

```bash
python export_database.py
```

### 4. Aguardar Exportação

O script irá:
- Conectar ao banco
- Exportar todas as tabelas
- Gerar arquivo SQL na pasta do projeto

**Arquivo gerado:** `database_export_YYYYMMDD_HHMMSS.sql`

### 5. Verificar Arquivo Gerado

Certifique-se de que o arquivo foi criado:
```bash
dir database_export_*.sql
```

### 6. Suspender o Banco Novamente (Opcional)

Após exportar, você pode suspender o banco novamente no Dashboard para não consumir recursos.

## 🔄 Alternativa: Verificar Backups Automáticos

O Render pode ter backups automáticos mesmo para bancos suspensos:

1. **No Dashboard do Render:**
   - Vá para o serviço PostgreSQL
   - Procure por aba "Backups" ou "Snapshots"
   - Se houver backups, baixe-os diretamente

2. **Os backups geralmente são:**
   - Arquivos `.dump` (formato binário PostgreSQL)
   - Arquivos `.sql` (formato texto)

## 📊 Informações do Banco

```
Host: dpg-d4s4dkeuk2gs73a52mug-a.oregon-postgres.render.com
Port: 5432
Database: clinica_db_cxsq
User: clinica_db_cxsq_user
Password: 1GJkXP0EOQYis7RA7bfY3PwmB5OtjUX2
URL: postgresql://clinica_db_cxsq_user:1GJkXP0EOQYis7RA7bfY3PwmB5OtjUX2@dpg-d4s4dkeuk2gs73a52mug-a.oregon-postgres.render.com/clinica_db_cxsq
```

## ✅ Checklist Antes de Executar

- [ ] Banco reativado no Render Dashboard
- [ ] Status do banco mostra "Active" ou "Running"
- [ ] Aguardou pelo menos 2-5 minutos após reativar
- [ ] Está na pasta do projeto (E:\AADVITA)
- [ ] Python está instalado e funcionando

## 🚨 Problemas Comuns

### Erro: "SSL connection has been closed unexpectedly"
- **Causa:** Banco ainda não está totalmente ativo ou está suspenso
- **Solução:** Aguarde mais alguns minutos e tente novamente

### Erro: "could not translate host name"
- **Causa:** Banco foi deletado ou não existe mais
- **Solução:** Verifique backups automáticos no Render

### Script não executa
- **Causa:** Python não encontrado ou bibliotecas faltando
- **Solução:** Execute `pip install -r requirements.txt`

## 📝 Após Exportar

1. **Criar novo banco no Neon.tech:**
   - Acesse https://console.neon.tech
   - Crie um novo projeto
   - Anote a nova DATABASE_URL

2. **Importar o backup:**
   ```bash
   psql "nova_database_url" -f database_export_YYYYMMDD_HHMMSS.sql
   ```

3. **Atualizar aplicação:**
   - Configure a nova DATABASE_URL no Render
   - Faça deploy da aplicação

## 💡 Dica

Se você conseguir acesso temporário ao terminal web do Render (através do Dashboard), pode executar `pg_dump` diretamente de lá, que é mais rápido e confiável.

