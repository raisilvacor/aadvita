# Database Export Tool

Ferramenta profissional para exportar banco de dados PostgreSQL diretamente do seu computador.

## Características

- ✅ **Zero instalações** - Usa apenas bibliotecas já instaladas no projeto
- ✅ **Exportação completa** - Estrutura e dados de todas as tabelas
- ✅ **Progresso visual** - Mostra progresso em tempo real
- ✅ **Tratamento de erros** - Mensagens claras e orientações
- ✅ **Compatível Windows/Linux/Mac** - Funciona em qualquer sistema

## Requisitos

- Python 3.8+
- Bibliotecas do projeto já instaladas (SQLAlchemy, psycopg)

## Uso

### 1. Configurar URL do Banco

Edite a variável `DATABASE_URL` no início do arquivo `export_database.py`:

```python
DATABASE_URL = "postgresql://user:password@host:port/database"
```

### 2. Executar Exportação

```bash
python export_database.py
```

### 3. Resultado

O script irá:
- Conectar ao banco de dados
- Listar todas as tabelas
- Exportar estrutura e dados de cada tabela
- Gerar arquivo SQL na pasta do projeto

**Arquivo gerado:** `database_export_YYYYMMDD_HHMMSS.sql`

## Exemplo de Saída

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
  Tamanho: 2.45 MB (2,572,800 bytes)
  Tabelas: 48
  Registros: 1,234
```

## Importar no Novo Banco

Após exportar, importe no novo banco de dados:

```bash
# Neon.tech ou outro PostgreSQL
psql "postgresql://user:pass@host/database" -f database_export_YYYYMMDD_HHMMSS.sql
```

Ou usando variável de ambiente:

```bash
psql $DATABASE_URL -f database_export_YYYYMMDD_HHMMSS.sql
```

## Solução de Problemas

### Banco Suspenso ou Inacessível

Se o banco estiver suspenso no Render:

1. **Reative temporariamente:**
   - Acesse https://dashboard.render.com
   - Vá para o serviço PostgreSQL
   - Clique em "Resume"
   - Aguarde 2-5 minutos

2. **Execute o script novamente:**
   ```bash
   python export_database.py
   ```

3. **Verifique backups automáticos:**
   - No Render Dashboard, procure por "Backups" ou "Snapshots"
   - Baixe qualquer backup disponível

### Erro de Conexão SSL

Se aparecer erro de SSL:
- O banco pode estar suspenso
- Verifique se o banco está ativo no Render Dashboard
- Tente reativar o banco temporariamente

### Erro de Encoding (Windows)

O script está configurado para funcionar no Windows. Se houver problemas de encoding, certifique-se de que o terminal suporta UTF-8.

## Estrutura do Arquivo SQL Gerado

O arquivo SQL gerado contém:

1. **Cabeçalho** - Informações sobre a exportação
2. **DROP TABLE** - Comandos para remover tabelas existentes
3. **CREATE TABLE** - Estrutura completa de cada tabela
4. **INSERT** - Todos os dados de cada tabela
5. **Rodapé** - Estatísticas da exportação

## Notas Importantes

- ⚠️ O script requer que o banco esteja **ativo e acessível**
- ⚠️ Para bancos suspensos, é necessário reativar temporariamente
- ⚠️ O arquivo SQL pode ser grande dependendo do tamanho do banco
- ✅ O script funciona completamente offline após conectar
- ✅ Não requer instalação de ferramentas adicionais

## Suporte

Se encontrar problemas:
1. Verifique se o banco está ativo
2. Verifique a URL do banco de dados
3. Verifique sua conexão com a internet
4. Consulte os logs de erro para mais detalhes

