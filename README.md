# AADVITA - Site Institucional

Site moderno e acessível para a Associação de Deficientes Visuais AADVITA, desenvolvido em Python com Flask.

## 🎯 Características

- **Totalmente Acessível**: Implementado seguindo as diretrizes WCAG 2.1
- **Navegação por Teclado**: Suporte completo para navegação sem mouse
- **Leitores de Tela**: Compatível com NVDA, JAWS, VoiceOver
- **Alto Contraste**: Suporte para modo de alto contraste
- **Responsivo**: Design adaptável para todos os dispositivos

## 📋 Funcionalidades

### Agendas
- **Agenda Presencial**: Reuniões e eventos presenciais
- **Agenda Virtual**: Reuniões e eventos online

### Outras Seções
- **Projetos**: Destaque dos projetos desenvolvidos
- **Ações**: Registro de ações e iniciativas
- **Apoiadores**: Lista de empresas e pessoas que apoiam a causa

## 🚀 Instalação

### Pré-requisitos
- Python 3.8 ou superior
- pip (gerenciador de pacotes Python)

### Passos

1. Clone ou baixe este repositório

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

3. Execute a aplicação:
```bash
python app.py
```

4. Acesse no navegador:
```
http://localhost:5000
```

## 📁 Estrutura do Projeto

```
AADVITA/
│
├── app.py                 # Aplicação Flask principal
├── requirements.txt       # Dependências do projeto
├── aadvita.db            # Banco de dados SQLite (criado automaticamente)
│
├── templates/            # Templates HTML
│   ├── base.html
│   ├── index.html
│   ├── agenda_presencial.html
│   ├── agenda_virtual.html
│   ├── projetos.html
│   ├── acoes.html
│   └── apoiadores.html
│
└── static/               # Arquivos estáticos
    ├── css/
    │   └── style.css
    ├── js/
    │   └── main.js
    └── images/
```

## ♿ Acessibilidade

### Recursos Implementados

1. **ARIA Labels**: Todos os elementos interativos possuem labels descritivos
2. **Navegação por Teclado**: 
   - Tab para navegar
   - Enter/Espaço para ativar
   - Escape para fechar menus
   - Alt+H para ir ao header
   - Alt+M para ir ao conteúdo principal
   - Alt+F para ir ao footer
3. **Skip Links**: Link para pular para o conteúdo principal
4. **Focus Visible**: Indicadores claros de foco
5. **Estrutura Semântica**: Uso correto de HTML5 semântico
6. **Contraste**: Cores com alto contraste (WCAG AAA)
7. **Reduced Motion**: Suporte para preferências de movimento reduzido

### Testes de Acessibilidade

Recomendamos testar com:
- NVDA (Windows)
- JAWS (Windows)
- VoiceOver (macOS/iOS)
- Orca (Linux)

## 🛠️ Tecnologias Utilizadas

- **Backend**: Flask (Python)
- **Banco de Dados**: SQLite
- **Frontend**: HTML5, CSS3, JavaScript
- **Acessibilidade**: ARIA, WCAG 2.1

## 📝 Licença

Este projeto foi desenvolvido para a AADVITA.

## 🤝 Contribuindo

Contribuições são bem-vindas! Por favor, mantenha o foco em acessibilidade ao fazer alterações.

## 📧 Contato

Para dúvidas ou sugestões, entre em contato através do email cadastrado no site.

---

**Desenvolvido com foco em inclusão e acessibilidade** ♿

