# Como Configurar DATABASE_URL no Render - Passo a Passo Detalhado

## ⚠️ IMPORTANTE: Onde colar o quê

- **KEY (Chave)**: Deve ser exatamente `DATABASE_URL` (sem espaços, sem caracteres especiais)
- **VALUE (Valor)**: É aqui que você cola a URL completa do PostgreSQL

## Passo a Passo Completo

### 1. Copiar a URL do Banco de Dados

1. No Render Dashboard, clique em **"Databases"** no menu lateral (ou procure por `aadvita-db`)
2. Clique no banco **`aadvita-db`**
3. Role a página para baixo até encontrar a seção **"Connections"**
4. Na seção "Connections", encontre **"Internal Database URL"**
5. Clique no botão **"Show"** ao lado de "Internal Database URL"
6. A URL completa aparecerá (algo como: `postgresql://aadvita_user:senha@dpg-xxxxx:5432/aadvita`)
7. Clique no botão **"Copy"** para copiar a URL completa
8. **ANOTE ou mantenha essa URL copiada** - você vai precisar dela no próximo passo

### 2. Configurar no Serviço Web

1. No Render Dashboard, clique em **"Services"** ou **"Web Services"** no menu lateral
2. Clique no serviço **`aadvita`** (o serviço web, não o banco)
3. No menu lateral do serviço, clique em **"Environment"**
4. Na tabela de variáveis de ambiente, procure por **`DATABASE_URL`**

#### Se `DATABASE_URL` JÁ EXISTE:

1. Clique no botão **"Edit"** (ou ícone de lápis) ao lado de `DATABASE_URL`
2. No campo **"KEY"**: Deixe como está (`DATABASE_URL`) - NÃO MEXA AQUI
3. No campo **"VALUE"**: 
   - Apague tudo que estiver lá (provavelmente está `aadvita-db`)
   - Cole a URL completa que você copiou no passo 1
4. Clique em **"Save"** ou **"Save Changes"**

#### Se `DATABASE_URL` NÃO EXISTE:

1. Clique no botão **"+ Add Environment Variable"** ou **"+ Add"**
2. No campo **"KEY"**: Digite exatamente `DATABASE_URL` (sem espaços, tudo maiúsculo)
3. No campo **"VALUE"**: Cole a URL completa que você copiou no passo 1
4. Clique em **"Save"** ou **"Add"**

### 3. Verificar se Está Correto

Após salvar, a variável deve aparecer assim:

```
KEY: DATABASE_URL
VALUE: postgresql://aadvita_user:xxxxx@dpg-xxxxx:5432/aadvita
```

**NÃO deve aparecer apenas `aadvita-db` no VALUE!**

### 4. Aguardar o Deploy

1. O Render fará um novo deploy automaticamente
2. Aguarde alguns minutos
3. Vá em **"Logs"** no serviço `aadvita`
4. Procure por estas mensagens:
   - ✅ `Usando PostgreSQL: postgresql://...`
   - 📊 `Tipo de banco de dados: postgresql`

Se aparecer `⚠️ AVISO: Usando SQLite local`, significa que a URL não foi configurada corretamente.

## ⚠️ Erros Comuns

### Erro: "Environment variable keys must consist of..."

**Causa**: Você colocou a URL no campo KEY ao invés do campo VALUE

**Solução**: 
- KEY deve ser: `DATABASE_URL`
- VALUE deve ser: a URL completa do PostgreSQL

### Erro: A variável não aparece

**Solução**: Certifique-se de ter clicado em "Save" após adicionar/editar

## Precisa de Ajuda?

Se ainda tiver problemas, envie uma captura de tela da página "Environment" do serviço `aadvita` que eu ajudo a identificar o problema.

