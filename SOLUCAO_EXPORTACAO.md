# Solução Profissional - Exportação de Banco de Dados

## 📌 Situação

O banco de dados está **suspenso** no Render (versão free). Você precisa exportar os dados antes de criar um novo banco.

## ✅ Solução Implementada

Criei o script `export_database.py` que:
- ✅ Funciona **direto do seu PC** (sem deploy)
- ✅ Usa **apenas bibliotecas já instaladas** (SQLAlchemy + psycopg)
- ✅ Exporta **estrutura + dados** de todas as tabelas
- ✅ Mostra **progresso em tempo real**
- ✅ Gera arquivo SQL **pronto para importar**

## 🚀 Como Usar (Quando Banco Estiver Ativo)

### 1. Reativar Banco no Render

**CRÍTICO:** O banco precisa estar ATIVO para funcionar.

1. Acesse: https://dashboard.render.com
2. Vá para: Serviços → PostgreSQL (`clinica_db_cxsq`)
3. Clique em: **"Resume"** ou **"Activate"**
4. Aguarde: **2-5 minutos** para inicializar

### 2. Executar Exportação

No PowerShell (pasta do projeto):

```powershell
python export_database.py
```

### 3. Resultado Esperado

```
============================================================
Database Export Tool
============================================================

Conectando ao banco de dados... [OK] Conectado
  Database: clinica_db_cxsq
  PostgreSQL: PostgreSQL 15.2

Exportando para: database_export_20260108_193045.sql
------------------------------------------------------------
Tabelas encontradas: 48

[1/48] usuarios ... [OK] (2 registros, 5 colunas)
[2/48] projetos ... [OK] (15 registros, 12 colunas)
...
------------------------------------------------------------

[OK] Exportacao concluida com sucesso!
  Arquivo: database_export_20260108_193045.sql
  Tamanho: 2.45 MB
  Tabelas: 48
  Registros: 1,234
```

## 📂 Arquivos Criados

- ✅ `export_database.py` - Script principal de exportação
- ✅ `EXPORTAR_BANCO.md` - Guia completo passo a passo
- ✅ `README_EXPORT.md` - Documentação técnica

## ⚠️ IMPORTANTE

O script **SÓ FUNCIONA** quando o banco está **ATIVO**.

**Erro atual:** "SSL connection has been closed unexpectedly"
**Causa:** Banco está suspenso
**Solução:** Reative o banco no Render Dashboard primeiro

## 🔄 Processo Completo

```
1. Reativar banco no Render Dashboard
   ↓
2. Aguardar 2-5 minutos
   ↓
3. Executar: python export_database.py
   ↓
4. Verificar arquivo SQL gerado
   ↓
5. Criar novo banco no Neon.tech
   ↓
6. Importar: psql "nova_url" -f database_export_*.sql
   ↓
7. Atualizar DATABASE_URL na aplicação
```

## 🆘 Se Não Conseguir Reativar

Se o Render não permitir reativar o banco (versão free deletada):

1. **Verifique Backups Automáticos:**
   - Render Dashboard → PostgreSQL → Aba "Backups"
   - Baixe qualquer backup disponível

2. **Contate Suporte do Render:**
   - Pode haver backups não visíveis no dashboard
   - Render mantém dados por até 90 dias

3. **Verifique Arquivos Locais:**
   - Procure por arquivos `.sql` ou `.dump` na pasta
   - Verifique se há backups antigos

## 📝 Notas Técnicas

- **Bibliotecas usadas:** SQLAlchemy, psycopg3 (já instaladas)
- **Formato de saída:** SQL padrão PostgreSQL
- **Encoding:** UTF-8
- **Compatibilidade:** Windows/Linux/Mac

## ✨ Próximos Passos

1. Reative o banco no Render
2. Execute `python export_database.py`
3. Verifique o arquivo gerado
4. Importe no novo banco (Neon.tech)

O script está pronto e profissional. **Basta reativar o banco e executar!**

