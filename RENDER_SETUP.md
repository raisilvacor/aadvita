# Configuração do PostgreSQL no Render

## Problema
Os dados cadastrados desaparecem após cada deploy/reinicialização porque o SQLite local não persiste no Render (sistema de arquivos efêmero).

## Solução
Usar PostgreSQL gerenciado pelo Render, que persiste os dados entre deploys.

## Verificações no Render Dashboard

### 1. Verificar se o PostgreSQL foi criado
1. Acesse o dashboard do Render
2. Verifique se existe um serviço chamado `aadvita-db` do tipo PostgreSQL
3. Se não existir, o `render.yaml` pode não ter sido processado corretamente

### 2. Verificar a variável DATABASE_URL
1. No serviço web `aadvita`, vá em "Environment"
2. Verifique se existe a variável `DATABASE_URL`
3. Ela deve estar conectada ao banco `aadvita-db`

### 3. Se o PostgreSQL não foi criado automaticamente

#### Opção A: Criar manualmente via Dashboard
1. No Render Dashboard, clique em "New +"
2. Selecione "PostgreSQL"
3. Configure:
   - Name: `aadvita-db`
   - Database: `aadvita`
   - User: `aadvita_user`
   - Plan: Free
4. Após criar, copie a "Internal Database URL"
5. No serviço web `aadvita`, vá em "Environment"
6. Adicione a variável:
   - Key: `DATABASE_URL`
   - Value: Cole a Internal Database URL copiada

#### Opção B: Usar a Connection String Externa (se necessário)
Se a Internal Database URL não funcionar, use a "External Database URL" (mas isso pode ter limitações de segurança).

### 4. Verificar os logs após o deploy
Após fazer o deploy, verifique os logs do serviço web. Você deve ver:
- ✅ `Usando PostgreSQL: postgresql://...`
- ✅ `Tipo de banco de dados: postgresql`
- ✅ `Tabelas do banco de dados verificadas/criadas`

Se ver:
- ⚠️ `AVISO: Usando SQLite local - dados NÃO persistirão no Render!`

Significa que a variável `DATABASE_URL` não está configurada corretamente.

### 5. Após configurar o PostgreSQL
1. Faça um novo deploy
2. O banco será inicializado automaticamente na primeira execução
3. Os dados cadastrados agora persistirão entre deploys

## Importante
- O plano Free do PostgreSQL tem limitações (90 dias de inatividade pode deletar o banco)
- Para produção, considere usar um plano pago
- Faça backup regular dos dados importantes

