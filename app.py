from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime, date, timedelta
from calendar import monthrange
import os
import uuid
import re
import requests
from bs4 import BeautifulSoup
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'aadvita-secret-key-2024')
# Configurar banco de dados - usar variável de ambiente se disponível, senão usar SQLite local
database_url = os.environ.get('DATABASE_URL')
if database_url:
    # Render usa PostgreSQL, mas se for SQLite, ajustar o formato
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    # SQLite local - usar caminho absoluto para persistência no Render
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'aadvita.db')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['LANGUAGES'] = {
    'pt': 'Português',
    'es': 'Español',
    'en': 'English'
}
app.config['UPLOAD_FOLDER'] = 'static/images/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['ALLOWED_DOCUMENT_EXTENSIONS'] = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'odt', 'ods'}

db = SQLAlchemy(app)

# Dicionário de traduções
TRANSLATIONS = {
    'pt': {
        'Início': 'Início',
        'Agendas': 'Agendas',
        'Agenda Presencial': 'Agenda Presencial',
        'Agenda Virtual': 'Agenda Virtual',
        'Projetos': 'Projetos',
        'Ações': 'Ações',
        'Apoiadores': 'Apoiadores',
        'Selecionar idioma': 'Selecionar idioma',
        'Idioma atual': 'Idioma atual',
        'Bem-vindo à AADVITA': 'Bem-vindo à AADVITA',
        'Associação de Deficientes Visuais promovendo inclusão e acessibilidade': 'Associação de Deficientes Visuais promovendo inclusão e acessibilidade',
        'Conheça nossos projetos': 'Conheça nossos projetos',
        'Destaques': 'Destaques',
        'Próximas Reuniões Presenciais': 'Próximas Reuniões Presenciais',
        'Próximas Reuniões Virtuais': 'Próximas Reuniões Virtuais',
        'Projetos em Destaque': 'Projetos em Destaque',
        'Ações Recentes': 'Ações Recentes',
        'Ver todas as reuniões presenciais': 'Ver todas as reuniões presenciais',
        'Ver todas as reuniões virtuais': 'Ver todas as reuniões virtuais',
        'Ver todos os projetos': 'Ver todos os projetos',
        'Ver todas as ações': 'Ver todas as ações',
        'Agenda de Reuniões Presenciais': 'Agenda de Reuniões Presenciais',
        'Confira nossas próximas reuniões presenciais e eventos': 'Confira nossas próximas reuniões presenciais e eventos',
        'Agenda de Reuniões Virtuais': 'Agenda de Reuniões Virtuais',
        'Participe das nossas reuniões e eventos online': 'Participe das nossas reuniões e eventos online',
        'Nossos Projetos': 'Nossos Projetos',
        'Conheça os projetos que desenvolvemos para promover inclusão e acessibilidade': 'Conheça os projetos que desenvolvemos para promover inclusão e acessibilidade',
        'Nossas Ações': 'Nossas Ações',
        'Acompanhe as ações e iniciativas desenvolvidas pela AADVITA': 'Acompanhe as ações e iniciativas desenvolvidas pela AADVITA',
        'Nossos Apoiadores': 'Nossos Apoiadores',
        'Agradecemos a todos que apoiam nossa causa e tornam nossos projetos possíveis': 'Agradecemos a todos que apoiam nossa causa e tornam nossos projetos possíveis',
        'Informativo': 'Informativo',
        'Fique por dentro das notícias e podcasts da AADVITA': 'Fique por dentro das notícias e podcasts da AADVITA',
        'Todos': 'Todos',
        'Notícias': 'Notícias',
        'Podcast': 'Podcast',
        'Notícia': 'Notícia',
        'Publicado em': 'Publicado em',
        'Não há notícias cadastradas no momento.': 'Não há notícias cadastradas no momento.',
        'Não há podcasts cadastrados no momento.': 'Não há podcasts cadastrados no momento.',
        'Não há informativos cadastrados no momento.': 'Não há informativos cadastrados no momento.',
        'Ler Notícia': 'Ler Notícia',
        'Escutar Podcast': 'Escutar Podcast',
        'Voltar para Informativo': 'Voltar para Informativo',
        'Abrir no SoundCloud': 'Abrir no SoundCloud',
        'Clique no botão abaixo para escutar o podcast completo': 'Clique no botão abaixo para escutar o podcast completo',
        'Compartilhar': 'Compartilhar',
        'Compartilhar no Facebook': 'Compartilhar no Facebook',
        'Compartilhar no Twitter': 'Compartilhar no Twitter',
        'Compartilhar no WhatsApp': 'Compartilhar no WhatsApp',
        'Compartilhar no LinkedIn': 'Compartilhar no LinkedIn',
        'Copiar Link': 'Copiar Link',
        'Link Copiado!': 'Link Copiado!',
        'Copiar link': 'Copiar link',
        'Não foi possível copiar o link. Por favor, copie manualmente:': 'Não foi possível copiar o link. Por favor, copie manualmente:',
        'Rádio AADVITA': 'Rádio AADVITA',
        'Ouça nossos programas de rádio e acompanhe nossa programação': 'Ouça nossos programas de rádio e acompanhe nossa programação',
        'Apresentador': 'Apresentador',
        'Horário': 'Horário',
        'Ao Vivo': 'Ao Vivo',
        'Clique em play para ouvir ao vivo': 'Clique em play para ouvir ao vivo',
        'Episódio': 'Episódio',
        'Ouça o episódio completo': 'Ouça o episódio completo',
        'Seu navegador não suporta o elemento de áudio.': 'Seu navegador não suporta o elemento de áudio.',
        'Não há programas de rádio cadastrados no momento.': 'Não há programas de rádio cadastrados no momento.',
        'Rádio AADVITA - Ao Vivo': 'Rádio AADVITA - Ao Vivo',
        'Transmitindo ao vivo': 'Transmitindo ao vivo',
        'Nossos Programas': 'Nossos Programas',
        'Campanhas': 'Campanhas',
        'Conheça nossas campanhas e participe': 'Conheça nossas campanhas e participe',
        'Apoie-nos': 'Apoie-nos',
        'Apoie nossa causa e faça a diferença': 'Apoie nossa causa e faça a diferença',
        'Editais': 'Editais',
        'Confira nossos editais e oportunidades': 'Confira nossos editais e oportunidades',
        'Acesso Rápido': 'Acesso Rápido',
        'Em breve, informações sobre nossas campanhas estarão disponíveis aqui.': 'Em breve, informações sobre nossas campanhas estarão disponíveis aqui.',
        'Como Apoiar': 'Como Apoiar',
        'Sua contribuição é fundamental para continuarmos promovendo inclusão e acessibilidade.': 'Sua contribuição é fundamental para continuarmos promovendo inclusão e acessibilidade.',
        'Em breve, mais informações sobre como apoiar estarão disponíveis aqui.': 'Em breve, mais informações sobre como apoiar estarão disponíveis aqui.',
        'Em breve, informações sobre nossos editais estarão disponíveis aqui.': 'Em breve, informações sobre nossos editais estarão disponíveis aqui.',
        'Sobre': 'Sobre',
        'Sobre a AADVITA': 'Sobre a AADVITA',
        'Transparência': 'Transparência',
        'Acompanhe nossa gestão, relatórios e informações financeiras': 'Acompanhe nossa gestão, relatórios e informações financeiras',
        'Nossa Compromisso com a Transparência': 'Nossa Compromisso com a Transparência',
        'A AADVITA acredita que a transparência é fundamental para construir confiança e fortalecer nossa relação com a comunidade. Por isso, disponibilizamos informações sobre nossa gestão, atividades e recursos financeiros.': 'A AADVITA acredita que a transparência é fundamental para construir confiança e fortalecer nossa relação com a comunidade. Por isso, disponibilizamos informações sobre nossa gestão, atividades e recursos financeiros.',
        'Relatórios Financeiros': 'Relatórios Financeiros',
        'Acompanhe nossos relatórios financeiros, demonstrativos e balanços.': 'Acompanhe nossos relatórios financeiros, demonstrativos e balanços.',
        'Estatuto e Documentos': 'Estatuto e Documentos',
        'Acesse nosso estatuto social, atas de reuniões e documentos oficiais.': 'Acesse nosso estatuto social, atas de reuniões e documentos oficiais.',
        'Prestação de Contas': 'Prestação de Contas',
        'Confira como utilizamos os recursos recebidos e os resultados alcançados.': 'Confira como utilizamos os recursos recebidos e os resultados alcançados.',
        'Projetos e Ações': 'Projetos e Ações',
        'Veja os projetos desenvolvidos e ações realizadas em benefício da comunidade.': 'Veja os projetos desenvolvidos e ações realizadas em benefício da comunidade.',
        'Doações e Recursos': 'Doações e Recursos',
        'Informações sobre doações recebidas e como contribuir com nossa causa.': 'Informações sobre doações recebidas e como contribuir com nossa causa.',
        'Diretoria e Conselho': 'Diretoria e Conselho',
        'Conheça os membros da diretoria e conselho fiscal responsáveis pela gestão.': 'Conheça os membros da diretoria e conselho fiscal responsáveis pela gestão.',
        'Em breve': 'Em breve',
        'Ver Projetos': 'Ver Projetos',
        'Ver Detalhes': 'Ver Detalhes',
        'Voltar para Projetos': 'Voltar para Projetos',
        'Término:': 'Término:',
        'Identificação do Projeto': 'Identificação do Projeto',
        'Contexto e Justificativa': 'Contexto e Justificativa',
        'Objetivos': 'Objetivos',
        'Público-Alvo': 'Público-Alvo',
        'Metodologia': 'Metodologia',
        'Recursos Necessários': 'Recursos Necessários',
        'Parcerias': 'Parcerias',
        'Resultados Esperados': 'Resultados Esperados',
        'Monitoramento e Avaliação': 'Monitoramento e Avaliação',
        'Cronograma de Execução': 'Cronograma de Execução',
        'Orçamento': 'Orçamento',
        'Exemplo Resumido': 'Exemplo Resumido',
        'Considerações Finais': 'Considerações Finais',
        'Descrição': 'Descrição',
        'Ver Diretoria': 'Ver Diretoria',
        'Ver Relatórios': 'Ver Relatórios',
        'Acompanhe nossas doações e gastos de forma transparente': 'Acompanhe nossas doações e gastos de forma transparente',
        'Doações Recebidas': 'Doações Recebidas',
        'Gastos Realizados': 'Gastos Realizados',
        'Tipo': 'Tipo',
        'Descrição': 'Descrição',
        'Doador': 'Doador',
        'País': 'País',
        'Valor/Quantidade': 'Valor/Quantidade',
        'Data': 'Data',
        'Observações': 'Observações',
        'Categoria': 'Categoria',
        'Fornecedor': 'Fornecedor',
        'Valor': 'Valor',
        'Financeira': 'Financeira',
        'Material': 'Material',
        'Serviço': 'Serviço',
        'itens': 'itens',
        'unidades': 'unidades',
        'Total de Doações Financeiras': 'Total de Doações Financeiras',
        'Total de Doações em Material': 'Total de Doações em Material',
        'Total de Doações em Serviços': 'Total de Doações em Serviços',
        'Total de Gastos': 'Total de Gastos',
        'Nenhuma doação cadastrada no momento.': 'Nenhuma doação cadastrada no momento.',
        'Nenhum gasto cadastrado no momento.': 'Nenhum gasto cadastrado no momento.',
        'Voltar para Transparência': 'Voltar para Transparência',
        'Baixar Documento': 'Baixar Documento',
        'Acompanhe nossos relatórios financeiros, demonstrativos e balanços de forma transparente': 'Acompanhe nossos relatórios financeiros, demonstrativos e balanços de forma transparente',
        'Nenhum relatório financeiro cadastrado no momento.': 'Nenhum relatório financeiro cadastrado no momento.',
        'Relatório': 'Relatório',
        'Demonstrativo': 'Demonstrativo',
        'Balanço': 'Balanço',
        'Ver Relatórios': 'Ver Relatórios',
        'Ver Documentos': 'Ver Documentos',
        'Ver Prestação de Contas': 'Ver Prestação de Contas',
        'Ver Informações': 'Ver Informações',
        'Estatuto': 'Estatuto',
        'Ata': 'Ata',
        'Acesse nosso estatuto social, atas de reuniões e documentos oficiais': 'Acesse nosso estatuto social, atas de reuniões e documentos oficiais',
        'Confira como utilizamos os recursos recebidos e os resultados alcançados': 'Confira como utilizamos os recursos recebidos e os resultados alcançados',
        'Informações sobre doações recebidas e como contribuir com nossa causa': 'Informações sobre doações recebidas e como contribuir com nossa causa',
        'Nenhum documento cadastrado no momento.': 'Nenhum documento cadastrado no momento.',
        'Nenhuma prestação de contas cadastrada no momento.': 'Nenhuma prestação de contas cadastrada no momento.',
        'Nenhuma informação de doação cadastrada no momento.': 'Nenhuma informação de doação cadastrada no momento.',
        'Período:': 'Período:',
        'A partir de': 'A partir de',
        'Recursos Recebidos:': 'Recursos Recebidos:',
        'Resultados Alcançados:': 'Resultados Alcançados:',
        'Como Contribuir:': 'Como Contribuir:',
        'Informações de Contato': 'Informações de Contato',
        'Para mais informações sobre transparência, entre em contato conosco através dos canais oficiais.': 'Para mais informações sobre transparência, entre em contato conosco através dos canais oficiais.',
        'E-mail:': 'E-mail:',
        'Telefone:': 'Telefone:',
        'Entre em contato através do formulário': 'Entre em contato através do formulário',
        'Conheça nossa história, missão e valores': 'Conheça nossa história, missão e valores',
        'Quem Somos': 'Quem Somos',
        'A AADVITA - Associação dos Deficientes Visuais Tapuienses é uma organização sem fins lucrativos dedicada a promover a inclusão, acessibilidade e qualidade de vida para pessoas com deficiência visual em nossa comunidade.': 'A AADVITA - Associação dos Deficientes Visuais Tapuienses é uma organização sem fins lucrativos dedicada a promover a inclusão, acessibilidade e qualidade de vida para pessoas com deficiência visual em nossa comunidade.',
        'Nossa Missão': 'Nossa Missão',
        'Promover a inclusão social, educacional e profissional de pessoas com deficiência visual, oferecendo apoio, capacitação e recursos necessários para que possam desenvolver todo o seu potencial e participar plenamente da sociedade.': 'Promover a inclusão social, educacional e profissional de pessoas com deficiência visual, oferecendo apoio, capacitação e recursos necessários para que possam desenvolver todo o seu potencial e participar plenamente da sociedade.',
        'Nossos Valores': 'Nossos Valores',
        'Inclusão:': 'Inclusão:',
        'Acreditamos que todos têm o direito de participar plenamente da sociedade': 'Acreditamos que todos têm o direito de participar plenamente da sociedade',
        'Respeito:': 'Respeito:',
        'Valorizamos a diversidade e a dignidade de cada pessoa': 'Valorizamos a diversidade e a dignidade de cada pessoa',
        'Compromisso:': 'Compromisso:',
        'Trabalhamos com dedicação para alcançar nossos objetivos': 'Trabalhamos com dedicação para alcançar nossos objetivos',
        'Solidariedade:': 'Solidariedade:',
        'Apoiamos uns aos outros em nossa jornada coletiva': 'Apoiamos uns aos outros em nossa jornada coletiva',
        'Transparência:': 'Transparência:',
        'Mantemos práticas éticas e transparentes em todas as nossas ações': 'Mantemos práticas éticas e transparentes em todas as nossas ações',
        'Diretoria': 'Diretoria',
        'Diretor de Comunicação': 'Diretor de Comunicação',
        'Presidente': 'Presidente',
        'Vice Presidente': 'Vice Presidente',
        'Primeiro(a) Secretário(a)': 'Primeiro(a) Secretário(a)',
        'Segundo(a) Secretário(a)': 'Segundo(a) Secretário(a)',
        'Tesoureiro(a)': 'Tesoureiro(a)',
        'Nome do Presidente': 'Nome do Presidente',
        'Nome do Vice Presidente': 'Nome do Vice-Presidente',
        'Vice-Presidente': 'Vice-Presidente',
        'Vice Presidente': 'Vice-Presidente',
        'Nome do Primeiro Secretário': 'Nome do Primeiro Secretário',
        'Nome do Segundo Secretário': 'Nome do Segundo Secretário',
        'Nome do Tesoureiro': 'Nome do Tesoureiro',
        'Primeiro Secretário(a)': 'Primeiro Secretário(a)',
        'Segundo Secretário(a)': 'Segundo Secretário(a)',
        'Primeiro Tesoureiro(a)': 'Primeiro Tesoureiro(a)',
        'Conselho Fiscal': 'Conselho Fiscal',
        'Conselheiro': 'Conselheiro(a)',
        'Conselheiro(a)': 'Conselheiro(a)',
        'Coordenação Social': 'Coordenação Social',
        'Coordenador(a)': 'Coordenador(a)',
        'Membro da Coordenação Social': 'Coordenador(a)',
        'Nenhum coordenador(a) cadastrado(a).': 'Nenhum coordenador(a) cadastrado(a).',
        'Nome do Conselheiro 1': 'Nome do Conselheiro 1',
        'Nome do Conselheiro 2': 'Nome do Conselheiro 2',
        'Associação dedicada a promover a inclusão e acessibilidade para pessoas com deficiência visual.': 'Associação dedicada a promover a inclusão e acessibilidade para pessoas com deficiência visual.',
        'Contato': 'Contato',
        'Links Rápidos': 'Links Rápidos',
        'Não há reuniões presenciais programadas no momento.': 'Não há reuniões presenciais programadas no momento.',
        'Não há reuniões virtuais programadas no momento.': 'Não há reuniões virtuais programadas no momento.',
        'Não há projetos cadastrados no momento.': 'Não há projetos cadastrados no momento.',
        'Não há ações cadastradas no momento.': 'Não há ações cadastradas no momento.',
        'Não há reuniões presenciais cadastradas no momento.': 'Não há reuniões presenciais cadastradas no momento.',
        'Não há reuniões virtuais cadastradas no momento.': 'Não há reuniões virtuais cadastradas no momento.',
        'Volte em breve para conferir nossa agenda atualizada.': 'Volte em breve para conferir nossa agenda atualizada.',
        'Acessar reunião': 'Acessar reunião',
        'Acessar evento': 'Acessar evento',
        'Local:': 'Local:',
        'Endereço:': 'Endereço:',
        'Plataforma:': 'Plataforma:',
        'Data:': 'Data:',
        'Hora:': 'Hora:',
        'Visitar site': 'Visitar site',
        'Não há apoiadores cadastrados no momento.': 'Não há apoiadores cadastrados no momento.',
        'Galeria': 'Galeria',
        'Galeria de Imagens': 'Galeria de Imagens',
        'Fotos de Eventos': 'Fotos de Eventos',
        'Fotos de Ações': 'Fotos de Ações',
        'Galeria Geral': 'Galeria Geral',
        'Confira nossa galeria completa de álbuns': 'Confira nossa galeria completa de álbuns',
        'Ver Álbum': 'Ver Álbum',
        'Voltar para Galeria': 'Voltar para Galeria',
        'foto(s)': 'foto(s)',
        'Este álbum ainda não possui fotos.': 'Este álbum ainda não possui fotos.',
        'Nenhum álbum cadastrado no momento.': 'Nenhum álbum cadastrado no momento.',
        'Álbuns:': 'Álbuns:',
        'Enviar Imagem': 'Enviar Imagem',
        'Título (opcional)': 'Título (opcional)',
        'Descrição (opcional)': 'Descrição (opcional)',
        'Selecionar arquivo': 'Selecionar arquivo',
        'Nenhuma imagem cadastrada no momento.': 'Nenhuma imagem cadastrada no momento.',
        'Imagem ampliada': 'Imagem ampliada',
        'Fechar': 'Fechar',
        'Anterior': 'Anterior',
        'Próxima': 'Próxima',
        'Vídeos': 'Vídeos',
        'Nossos Vídeos': 'Nossos Vídeos',
        'Confira nossos vídeos e conteúdos em vídeo': 'Confira nossos vídeos e conteúdos em vídeo',
        'Vídeos em Destaque': 'Vídeos em Destaque',
        'Ver todos os vídeos': 'Ver todos os vídeos',
        'Nenhum vídeo cadastrado no momento.': 'Nenhum vídeo cadastrado no momento.',
        'Assistir vídeo': 'Assistir vídeo',
        'Associe-se': 'Associe-se',
        'Eventos': 'Eventos',
        'Próximos Eventos': 'Próximos Eventos',
        'Ver todos os eventos': 'Ver todos os eventos',
        'Não há eventos cadastrados no momento.': 'Não há eventos cadastrados no momento.',
        'Tipo:': 'Tipo:',
        'Ir para conteúdo principal': 'Ir para conteúdo principal',
        'Abrir menu': 'Abrir menu',
        'Menu': 'Menu',
        'Navegação principal': 'Navegação principal',
        'AADVITA - Página inicial': 'AADVITA - Página inicial',
        'Português': 'Português',
        'Español': 'Español',
        'English': 'English',
        'Fechar mensagem': 'Fechar mensagem',
        'Email:': 'Email:',
        'Telefone:': 'Telefone:',
        'WhatsApp:': 'WhatsApp:',
        'Doações': 'Doações',
        'QR Code para doação': 'QR Code para doação',
        'Todos os direitos reservados.': 'Todos os direitos reservados.',
        'Desenvolvido por:': 'Desenvolvido por:',
        'AADVITA - Associação de Deficientes Visuais': 'AADVITA - Associação de Deficientes Visuais',
        '(abre em nova aba)': '(abre em nova aba)',
        'Entrar': 'Entrar',
        'Acesse sua conta ou área administrativa': 'Acesse sua conta ou área administrativa',
        'Associado': 'Associado',
        'Administrador': 'Administrador',
        'Digite seu CPF cadastrado': 'Digite seu CPF cadastrado',
        'Senha': 'Senha',
        'Digite sua senha': 'Digite sua senha',
        'Opções de idioma': 'Opções de idioma',
        'Associação dos Deficientes Visuais Tapuienses AADVITA - Promovendo inclusão e acessibilidade': 'Associação dos Deficientes Visuais Tapuienses AADVITA - Promovendo inclusão e acessibilidade',
        'AADVITA - Associação dos Deficientes Visuais Tapuienses': 'AADVITA - Associação dos Deficientes Visuais Tapuienses',
    },
    'es': {
        'Início': 'Inicio',
        'Agendas': 'Agendas',
        'Agenda Presencial': 'Agenda Presencial',
        'Agenda Virtual': 'Agenda Virtual',
        'Projetos': 'Proyectos',
        'Ações': 'Acciones',
        'Apoiadores': 'Apoiadores',
        'Selecionar idioma': 'Seleccionar idioma',
        'Idioma atual': 'Idioma actual',
        'Bem-vindo à AADVITA': 'Bienvenido a AADVITA',
        'Associação de Deficientes Visuais promovendo inclusão e acessibilidade': 'Asociación de Deficientes Visuales promoviendo inclusión y accesibilidad',
        'Conheça nossos projetos': 'Conoce nuestros proyectos',
        'Destaques': 'Destacados',
        'Próximas Reuniões Presenciais': 'Próximas Reuniones Presenciales',
        'Próximas Reuniões Virtuais': 'Próximas Reuniones Virtuales',
        'Projetos em Destaque': 'Proyectos Destacados',
        'Ações Recentes': 'Acciones Recientes',
        'Ver todas as reuniões presenciais': 'Ver todas las reuniones presenciales',
        'Ver todas as reuniões virtuais': 'Ver todas las reuniones virtuales',
        'Ver todos os projetos': 'Ver todos los proyectos',
        'Ver todas as ações': 'Ver todas las acciones',
        'Agenda de Reuniões Presenciais': 'Agenda de Reuniones Presenciales',
        'Confira nossas próximas reuniões presenciais e eventos': 'Consulta nuestras próximas reuniones presenciales y eventos',
        'Agenda de Reuniões Virtuais': 'Agenda de Reuniones Virtuales',
        'Participe das nossas reuniões e eventos online': 'Participa en nuestras reuniones y eventos en línea',
        'Nossos Projetos': 'Nuestros Proyectos',
        'Conheça os projetos que desenvolvemos para promover inclusão e acessibilidade': 'Conoce los proyectos que desarrollamos para promover inclusión y accesibilidad',
        'Nossas Ações': 'Nuestras Acciones',
        'Acompanhe as ações e iniciativas desenvolvidas pela AADVITA': 'Acompaña las acciones e iniciativas desarrolladas por AADVITA',
        'Nossos Apoiadores': 'Nuestros Apoiadores',
        'Agradecemos a todos que apoiam nossa causa e tornam nossos projetos possíveis': 'Agradecemos a todos los que apoyan nuestra causa y hacen posibles nuestros proyectos',
        'Informativo': 'Informativo',
        'Fique por dentro das notícias e podcasts da AADVITA': 'Mantente al tanto de las noticias y podcasts de AADVITA',
        'Todos': 'Todos',
        'Notícias': 'Noticias',
        'Podcast': 'Podcast',
        'Notícia': 'Noticia',
        'Publicado em': 'Publicado el',
        'Não há notícias cadastradas no momento.': 'No hay noticias registradas en este momento.',
        'Não há podcasts cadastrados no momento.': 'No hay podcasts registrados en este momento.',
        'Não há informativos cadastrados no momento.': 'No hay informativos registrados en este momento.',
        'Ler Notícia': 'Leer Noticia',
        'Escutar Podcast': 'Escuchar Podcast',
        'Voltar para Informativo': 'Volver a Informativo',
        'Abrir no SoundCloud': 'Abrir en SoundCloud',
        'Clique no botão abaixo para escutar o podcast completo': 'Haga clic en el botón a continuación para escuchar el podcast completo',
        'Compartilhar': 'Compartir',
        'Compartilhar no Facebook': 'Compartir en Facebook',
        'Compartilhar no Twitter': 'Compartir en Twitter',
        'Compartilhar no WhatsApp': 'Compartir en WhatsApp',
        'Compartilhar no LinkedIn': 'Compartir en LinkedIn',
        'Copiar Link': 'Copiar Enlace',
        'Link Copiado!': '¡Enlace Copiado!',
        'Copiar link': 'Copiar enlace',
        'Não foi possível copiar o link. Por favor, copie manualmente:': 'No se pudo copiar el enlace. Por favor, copie manualmente:',
        'Rádio AADVITA': 'Radio AADVITA',
        'Ouça nossos programas de rádio e acompanhe nossa programação': 'Escucha nuestros programas de radio y sigue nuestra programación',
        'Apresentador': 'Presentador',
        'Horário': 'Horario',
        'Ao Vivo': 'En Vivo',
        'Clique em play para ouvir ao vivo': 'Haz clic en play para escuchar en vivo',
        'Episódio': 'Episodio',
        'Ouça o episódio completo': 'Escucha el episodio completo',
        'Seu navegador não suporta o elemento de áudio.': 'Su navegador no soporta el elemento de audio.',
        'Não há programas de rádio cadastrados no momento.': 'No hay programas de radio registrados en este momento.',
        'Rádio AADVITA - Ao Vivo': 'Radio AADVITA - En Vivo',
        'Transmitindo ao vivo': 'Transmitiendo en vivo',
        'Nossos Programas': 'Nuestros Programas',
        'Campanhas': 'Campañas',
        'Conheça nossas campanhas e participe': 'Conoce nuestras campañas y participa',
        'Apoie-nos': 'Apóyanos',
        'Apoie nossa causa e faça a diferença': 'Apoya nuestra causa y marca la diferencia',
        'Editais': 'Editales',
        'Confira nossos editais e oportunidades': 'Consulta nuestros editales y oportunidades',
        'Acesso Rápido': 'Acceso Rápido',
        'Em breve, informações sobre nossas campanhas estarão disponíveis aqui.': 'Pronto, la información sobre nuestras campañas estará disponible aquí.',
        'Como Apoiar': 'Cómo Apoyar',
        'Sua contribuição é fundamental para continuarmos promovendo inclusão e acessibilidade.': 'Su contribución es fundamental para continuar promoviendo la inclusión y accesibilidad.',
        'Em breve, mais informações sobre como apoiar estarão disponíveis aqui.': 'Pronto, más información sobre cómo apoyar estará disponible aquí.',
        'Em breve, informações sobre nossos editais estarão disponíveis aqui.': 'Pronto, la información sobre nuestros editales estará disponible aquí.',
        'Sobre': 'Sobre',
        'Sobre a AADVITA': 'Sobre AADVITA',
        'Conheça nossa história, missão e valores': 'Conoce nuestra historia, misión y valores',
        'Transparência': 'Transparencia',
        'Acompanhe nossa gestão, relatórios e informações financeiras': 'Consulta nuestra gestión, informes e información financiera',
        'Nossa Compromisso com a Transparência': 'Nuestro Compromiso con la Transparencia',
        'A AADVITA acredita que a transparência é fundamental para construir confiança e fortalecer nossa relação com a comunidade. Por isso, disponibilizamos informações sobre nossa gestão, atividades e recursos financeiros.': 'AADVITA cree que la transparencia es fundamental para construir confianza y fortalecer nuestra relación con la comunidad. Por eso, proporcionamos información sobre nuestra gestión, actividades y recursos financieros.',
        'Relatórios Financeiros': 'Informes Financieros',
        'Acompanhe nossos relatórios financeiros, demonstrativos e balanços.': 'Consulta nuestros informes financieros, estados financieros y balances.',
        'Estatuto e Documentos': 'Estatuto y Documentos',
        'Acesse nosso estatuto social, atas de reuniões e documentos oficiais.': 'Accede a nuestro estatuto social, actas de reuniones y documentos oficiales.',
        'Prestação de Contas': 'Rendición de Cuentas',
        'Confira como utilizamos os recursos recebidos e os resultados alcançados.': 'Consulta cómo utilizamos los recursos recibidos y los resultados alcanzados.',
        'Projetos e Ações': 'Proyectos y Acciones',
        'Veja os projetos desenvolvidos e ações realizadas em benefício da comunidade.': 'Consulta los proyectos desarrollados y acciones realizadas en beneficio de la comunidad.',
        'Doações e Recursos': 'Donaciones y Recursos',
        'Informações sobre doações recebidas e como contribuir com nossa causa.': 'Información sobre donaciones recibidas y cómo contribuir con nuestra causa.',
        'Diretoria e Conselho': 'Directiva y Consejo',
        'Conheça os membros da diretoria e conselho fiscal responsáveis pela gestão.': 'Conoce los miembros de la directiva y consejo fiscal responsables de la gestión.',
        'Em breve': 'Próximamente',
        'Ver Projetos': 'Ver Proyectos',
        'Ver Detalhes': 'Ver Detalles',
        'Voltar para Projetos': 'Volver a Proyectos',
        'Término:': 'Término:',
        'Identificação do Projeto': 'Identificación del Proyecto',
        'Contexto e Justificativa': 'Contexto y Justificación',
        'Objetivos': 'Objetivos',
        'Público-Alvo': 'Público Objetivo',
        'Metodologia': 'Metodología',
        'Recursos Necessários': 'Recursos Necesarios',
        'Parcerias': 'Alianzas',
        'Resultados Esperados': 'Resultados Esperados',
        'Monitoramento e Avaliação': 'Monitoreo y Evaluación',
        'Cronograma de Execução': 'Cronograma de Ejecución',
        'Orçamento': 'Presupuesto',
        'Exemplo Resumido': 'Ejemplo Resumido',
        'Considerações Finais': 'Consideraciones Finales',
        'Descrição': 'Descripción',
        'Ver Diretoria': 'Ver Directiva',
        'Ver Relatórios': 'Ver Informes',
        'Acompanhe nossas doações e gastos de forma transparente': 'Consulta nuestras donaciones y gastos de forma transparente',
        'Doações Recebidas': 'Donaciones Recibidas',
        'Gastos Realizados': 'Gastos Realizados',
        'Tipo': 'Tipo',
        'Descrição': 'Descripción',
        'Doador': 'Donante',
        'País': 'País',
        'Valor/Quantidade': 'Valor/Cantidad',
        'Data': 'Fecha',
        'Observações': 'Observaciones',
        'Categoria': 'Categoría',
        'Fornecedor': 'Proveedor',
        'Valor': 'Valor',
        'Financeira': 'Financiera',
        'Material': 'Material',
        'Serviço': 'Servicio',
        'itens': 'artículos',
        'unidades': 'unidades',
        'Total de Doações Financeiras': 'Total de Donaciones Financieras',
        'Total de Doações em Material': 'Total de Donaciones en Material',
        'Total de Doações em Serviços': 'Total de Donaciones en Servicios',
        'Total de Gastos': 'Total de Gastos',
        'Nenhuma doação cadastrada no momento.': 'No hay donaciones registradas en este momento.',
        'Nenhum gasto cadastrado no momento.': 'No hay gastos registrados en este momento.',
        'Voltar para Transparência': 'Volver a Transparencia',
        'Baixar Documento': 'Descargar Documento',
        'Acompanhe nossos relatórios financeiros, demonstrativos e balanços de forma transparente': 'Consulta nuestros informes financieros, estados financieros y balances de forma transparente',
        'Nenhum relatório financeiro cadastrado no momento.': 'No hay informes financieros registrados en este momento.',
        'Relatório': 'Informe',
        'Demonstrativo': 'Estado Financiero',
        'Balanço': 'Balance',
        'Ver Relatórios': 'Ver Informes',
        'Ver Documentos': 'Ver Documentos',
        'Ver Prestação de Contas': 'Ver Rendición de Cuentas',
        'Ver Informações': 'Ver Información',
        'Estatuto': 'Estatuto',
        'Ata': 'Acta',
        'Acesse nosso estatuto social, atas de reuniões e documentos oficiais': 'Accede a nuestro estatuto social, actas de reuniones y documentos oficiales',
        'Confira como utilizamos os recursos recebidos e os resultados alcançados': 'Consulta cómo utilizamos los recursos recibidos y los resultados alcanzados',
        'Informações sobre doações recebidas e como contribuir com nossa causa': 'Información sobre donaciones recibidas y cómo contribuir con nuestra causa',
        'Nenhum documento cadastrado no momento.': 'No hay documentos registrados en este momento.',
        'Nenhuma prestação de contas cadastrada no momento.': 'No hay rendiciones de cuentas registradas en este momento.',
        'Nenhuma informação de doação cadastrada no momento.': 'No hay información de donaciones registrada en este momento.',
        'Período:': 'Período:',
        'A partir de': 'A partir de',
        'Recursos Recebidos:': 'Recursos Recibidos:',
        'Resultados Alcançados:': 'Resultados Alcanzados:',
        'Como Contribuir:': 'Cómo Contribuir:',
        'Informações de Contato': 'Información de Contacto',
        'Para mais informações sobre transparência, entre em contato conosco através dos canais oficiais.': 'Para más información sobre transparencia, contáctanos a través de los canales oficiales.',
        'E-mail:': 'Correo:',
        'Telefone:': 'Teléfono:',
        'Entre em contato através do formulário': 'Contáctanos a través del formulario',
        'Quem Somos': 'Quiénes Somos',
        'A AADVITA - Associação dos Deficientes Visuais Tapuienses é uma organização sem fins lucrativos dedicada a promover a inclusão, acessibilidade e qualidade de vida para pessoas com deficiência visual em nossa comunidade.': 'AADVITA - Asociación de Deficientes Visuales Tapuienses es una organización sin fines de lucro dedicada a promover la inclusión, accesibilidad y calidad de vida para personas con discapacidad visual en nuestra comunidad.',
        'Nossa Missão': 'Nuestra Misión',
        'Promover a inclusão social, educacional e profissional de pessoas com deficiência visual, oferecendo apoio, capacitação e recursos necessários para que possam desenvolver todo o seu potencial e participar plenamente da sociedade.': 'Promover la inclusión social, educativa y profesional de personas con discapacidad visual, ofreciendo apoyo, capacitación y recursos necesarios para que puedan desarrollar todo su potencial y participar plenamente en la sociedad.',
        'Nossos Valores': 'Nuestros Valores',
        'Inclusão:': 'Inclusión:',
        'Acreditamos que todos têm o direito de participar plenamente da sociedade': 'Creemos que todos tienen derecho a participar plenamente en la sociedad',
        'Respeito:': 'Respeto:',
        'Valorizamos a diversidade e a dignidade de cada pessoa': 'Valoramos la diversidad y la dignidad de cada persona',
        'Compromisso:': 'Compromiso:',
        'Trabalhamos com dedicação para alcançar nossos objetivos': 'Trabajamos con dedicación para alcanzar nuestros objetivos',
        'Solidariedade:': 'Solidaridad:',
        'Apoiamos uns aos outros em nossa jornada coletiva': 'Nos apoyamos mutuamente en nuestro viaje colectivo',
        'Transparência:': 'Transparencia:',
        'Mantemos práticas éticas e transparentes em todas as nossas ações': 'Mantenemos prácticas éticas y transparentes en todas nuestras acciones',
        'Diretoria': 'Directiva',
        'Diretor de Comunicação': 'Director de Comunicación',
        'Presidente': 'Presidente',
        'Vice Presidente': 'Vicepresidente',
        'Primeiro(a) Secretário(a)': 'Primer(a) Secretario(a)',
        'Segundo(a) Secretário(a)': 'Segundo(a) Secretario(a)',
        'Tesoureiro(a)': 'Tesorero(a)',
        'Nome do Presidente': 'Nombre del Presidente',
        'Nome do Vice Presidente': 'Nombre del Vicepresidente',
        'Vice-Presidente': 'Vicepresidente',
        'Vice Presidente': 'Vicepresidente',
        'Nome do Primeiro Secretário': 'Nombre del Primer Secretario',
        'Nome do Segundo Secretário': 'Nombre del Segundo Secretario',
        'Nome do Tesoureiro': 'Nombre del Tesorero',
        'Primeiro Secretário(a)': 'Primer Secretario(a)',
        'Segundo Secretário(a)': 'Segundo Secretario(a)',
        'Primeiro Tesoureiro(a)': 'Primer Tesorero(a)',
        'Conselho Fiscal': 'Consejo Fiscal',
        'Conselheiro': 'Consejero(a)',
        'Conselheiro(a)': 'Consejero(a)',
        'Coordenação Social': 'Coordinación Social',
        'Coordenador(a)': 'Coordinador(a)',
        'Membro da Coordenação Social': 'Coordinador(a)',
        'Nenhum coordenador(a) cadastrado(a).': 'Ningún coordinador(a) registrado(a).',
        'Nome do Conselheiro 1': 'Nombre del Consejero 1',
        'Nome do Conselheiro 2': 'Nombre del Consejero 2',
        'Associação dedicada a promover a inclusão e acessibilidade para pessoas com deficiência visual.': 'Asociación dedicada a promover la inclusión y accesibilidad para personas con discapacidad visual.',
        'Contato': 'Contacto',
        'Links Rápidos': 'Enlaces Rápidos',
        'Não há reuniões presenciais programadas no momento.': 'No hay reuniones presenciales programadas en este momento.',
        'Não há reuniões virtuais programadas no momento.': 'No hay reuniones virtuales programadas en este momento.',
        'Não há projetos cadastrados no momento.': 'No hay proyectos registrados en este momento.',
        'Não há ações cadastradas no momento.': 'No hay acciones registradas en este momento.',
        'Não há reuniões presenciais cadastradas no momento.': 'No hay reuniones presenciales registradas en este momento.',
        'Não há reuniões virtuais cadastradas no momento.': 'No hay reuniones virtuales registradas en este momento.',
        'Volte em breve para conferir nossa agenda atualizada.': 'Vuelve pronto para consultar nuestra agenda actualizada.',
        'Acessar reunião': 'Acceder a reunión',
        'Acessar evento': 'Acceder a evento',
        'Local:': 'Local:',
        'Endereço:': 'Dirección:',
        'Plataforma:': 'Plataforma:',
        'Data:': 'Fecha:',
        'Hora:': 'Hora:',
        'Visitar site': 'Visitar sitio',
        'Não há apoiadores cadastrados no momento.': 'No hay apoyadores registrados en este momento.',
        'Galeria': 'Galería',
        'Galeria de Imagens': 'Galería de Imágenes',
        'Fotos de Eventos': 'Fotos de Eventos',
        'Fotos de Ações': 'Fotos de Acciones',
        'Galeria Geral': 'Galería General',
        'Confira nossa galeria completa de álbuns': 'Consulte nuestra galería completa de álbumes',
        'Ver Álbum': 'Ver Álbum',
        'Voltar para Galeria': 'Volver a Galería',
        'foto(s)': 'foto(s)',
        'Este álbum ainda não possui fotos.': 'Este álbum aún no tiene fotos.',
        'Nenhum álbum cadastrado no momento.': 'No hay álbumes registrados en este momento.',
        'Álbuns:': 'Álbumes:',
        'Enviar Imagem': 'Enviar Imagen',
        'Título (opcional)': 'Título (opcional)',
        'Descrição (opcional)': 'Descripción (opcional)',
        'Selecionar arquivo': 'Seleccionar archivo',
        'Nenhuma imagem cadastrada no momento.': 'No hay imágenes registradas en este momento.',
        'Imagem ampliada': 'Imagen ampliada',
        'Fechar': 'Cerrar',
        'Anterior': 'Anterior',
        'Próxima': 'Siguiente',
        'Vídeos': 'Videos',
        'Nossos Vídeos': 'Nuestros Videos',
        'Confira nossos vídeos e conteúdos em vídeo': 'Consulta nuestros videos y contenidos en video',
        'Vídeos em Destaque': 'Videos Destacados',
        'Ver todos os vídeos': 'Ver todos los videos',
        'Nenhum vídeo cadastrado no momento.': 'No hay videos registrados en este momento.',
        'Assistir vídeo': 'Ver video',
        'Associe-se': 'Asóciate',
        'Eventos': 'Eventos',
        'Próximos Eventos': 'Próximos Eventos',
        'Ver todos os eventos': 'Ver todos los eventos',
        'Não há eventos cadastrados no momento.': 'No hay eventos registrados en este momento.',
        'Tipo:': 'Tipo:',
        'Ir para conteúdo principal': 'Ir al contenido principal',
        'Abrir menu': 'Abrir menú',
        'Menu': 'Menú',
        'Navegação principal': 'Navegación principal',
        'AADVITA - Página inicial': 'AADVITA - Página de inicio',
        'Português': 'Portugués',
        'Español': 'Español',
        'English': 'Inglés',
        'Fechar mensagem': 'Cerrar mensaje',
        'Email:': 'Correo:',
        'Telefone:': 'Teléfono:',
        'WhatsApp:': 'WhatsApp:',
        'Doações': 'Donaciones',
        'QR Code para doação': 'Código QR para donación',
        'Todos os direitos reservados.': 'Todos los derechos reservados.',
        'Desenvolvido por:': 'Desarrollado por:',
        'AADVITA - Associação de Deficientes Visuais': 'AADVITA - Asociación de Deficientes Visuales',
        '(abre em nova aba)': '(se abre en nueva pestaña)',
        'Entrar': 'Iniciar sesión',
        'Acesse sua conta ou área administrativa': 'Accede a tu cuenta o área administrativa',
        'Associado': 'Asociado',
        'Administrador': 'Administrador',
        'Digite seu CPF cadastrado': 'Ingresa tu CPF registrado',
        'Senha': 'Contraseña',
        'Digite sua senha': 'Ingresa tu contraseña',
        'Opções de idioma': 'Opciones de idioma',
        'Associação dos Deficientes Visuais Tapuienses AADVITA - Promovendo inclusão e acessibilidade': 'Asociación de Deficientes Visuales Tapuienses AADVITA - Promoviendo inclusión y accesibilidad',
        'AADVITA - Associação dos Deficientes Visuais Tapuienses': 'AADVITA - Asociación de Deficientes Visuales Tapuienses',
    },
    'en': {
        'Início': 'Home',
        'Agendas': 'Schedules',
        'Agenda Presencial': 'In-Person Schedule',
        'Agenda Virtual': 'Virtual Schedule',
        'Projetos': 'Projects',
        'Ações': 'Actions',
        'Apoiadores': 'Supporters',
        'Selecionar idioma': 'Select language',
        'Idioma atual': 'Current language',
        'Bem-vindo à AADVITA': 'Welcome to AADVITA',
        'Associação de Deficientes Visuais promovendo inclusão e acessibilidade': 'Association of Visually Impaired promoting inclusion and accessibility',
        'Conheça nossos projetos': 'Learn about our projects',
        'Destaques': 'Highlights',
        'Próximas Reuniões Presenciais': 'Upcoming In-Person Meetings',
        'Próximas Reuniões Virtuais': 'Upcoming Virtual Meetings',
        'Projetos em Destaque': 'Featured Projects',
        'Ações Recentes': 'Recent Actions',
        'Ver todas as reuniões presenciais': 'View all in-person meetings',
        'Ver todas as reuniões virtuais': 'View all virtual meetings',
        'Ver todos os projetos': 'View all projects',
        'Ver todas as ações': 'View all actions',
        'Agenda de Reuniões Presenciais': 'In-Person Meeting Schedule',
        'Confira nossas próximas reuniões presenciais e eventos': 'Check out our upcoming in-person meetings and events',
        'Agenda de Reuniões Virtuais': 'Virtual Meeting Schedule',
        'Participe das nossas reuniões e eventos online': 'Join our online meetings and events',
        'Nossos Projetos': 'Our Projects',
        'Conheça os projetos que desenvolvemos para promover inclusão e acessibilidade': 'Learn about the projects we develop to promote inclusion and accessibility',
        'Nossas Ações': 'Our Actions',
        'Acompanhe as ações e iniciativas desenvolvidas pela AADVITA': 'Follow the actions and initiatives developed by AADVITA',
        'Nossos Apoiadores': 'Our Supporters',
        'Agradecemos a todos que apoiam nossa causa e tornam nossos projetos possíveis': 'We thank everyone who supports our cause and makes our projects possible',
        'Informativo': 'News & Podcasts',
        'Fique por dentro das notícias e podcasts da AADVITA': 'Stay up to date with AADVITA news and podcasts',
        'Todos': 'All',
        'Notícias': 'News',
        'Podcast': 'Podcast',
        'Notícia': 'News',
        'Publicado em': 'Published on',
        'Não há notícias cadastradas no momento.': 'No news registered at this time.',
        'Não há podcasts cadastrados no momento.': 'No podcasts registered at this time.',
        'Não há informativos cadastrados no momento.': 'No news or podcasts registered at this time.',
        'Ler Notícia': 'Read News',
        'Escutar Podcast': 'Listen to Podcast',
        'Voltar para Informativo': 'Back to News & Podcasts',
        'Abrir no SoundCloud': 'Open in SoundCloud',
        'Clique no botão abaixo para escutar o podcast completo': 'Click the button below to listen to the full podcast',
        'Compartilhar': 'Share',
        'Compartilhar no Facebook': 'Share on Facebook',
        'Compartilhar no Twitter': 'Share on Twitter',
        'Compartilhar no WhatsApp': 'Share on WhatsApp',
        'Compartilhar no LinkedIn': 'Share on LinkedIn',
        'Copiar Link': 'Copy Link',
        'Link Copiado!': 'Link Copied!',
        'Copiar link': 'Copy link',
        'Não foi possível copiar o link. Por favor, copie manualmente:': 'Could not copy link. Please copy manually:',
        'Rádio AADVITA': 'AADVITA Radio',
        'Ouça nossos programas de rádio e acompanhe nossa programação': 'Listen to our radio programs and follow our schedule',
        'Apresentador': 'Host',
        'Horário': 'Schedule',
        'Ao Vivo': 'Live',
        'Clique em play para ouvir ao vivo': 'Click play to listen live',
        'Episódio': 'Episode',
        'Ouça o episódio completo': 'Listen to the full episode',
        'Seu navegador não suporta o elemento de áudio.': 'Your browser does not support the audio element.',
        'Não há programas de rádio cadastrados no momento.': 'No radio programs registered at this time.',
        'Rádio AADVITA - Ao Vivo': 'AADVITA Radio - Live',
        'Transmitindo ao vivo': 'Live Broadcasting',
        'Nossos Programas': 'Our Programs',
        'Campanhas': 'Campaigns',
        'Conheça nossas campanhas e participe': 'Learn about our campaigns and participate',
        'Apoie-nos': 'Support Us',
        'Apoie nossa causa e faça a diferença': 'Support our cause and make a difference',
        'Editais': 'Public Notices',
        'Confira nossos editais e oportunidades': 'Check our public notices and opportunities',
        'Acesso Rápido': 'Quick Access',
        'Em breve, informações sobre nossas campanhas estarão disponíveis aqui.': 'Soon, information about our campaigns will be available here.',
        'Como Apoiar': 'How to Support',
        'Sua contribuição é fundamental para continuarmos promovendo inclusão e acessibilidade.': 'Your contribution is essential for us to continue promoting inclusion and accessibility.',
        'Em breve, mais informações sobre como apoiar estarão disponíveis aqui.': 'Soon, more information on how to support will be available here.',
        'Em breve, informações sobre nossos editais estarão disponíveis aqui.': 'Soon, information about our public notices will be available here.',
        'Sobre': 'About',
        'Sobre a AADVITA': 'About AADVITA',
        'Conheça nossa história, missão e valores': 'Learn about our history, mission and values',
        'Transparência': 'Transparency',
        'Acompanhe nossa gestão, relatórios e informações financeiras': 'Follow our management, reports and financial information',
        'Nossa Compromisso com a Transparência': 'Our Commitment to Transparency',
        'A AADVITA acredita que a transparência é fundamental para construir confiança e fortalecer nossa relação com a comunidade. Por isso, disponibilizamos informações sobre nossa gestão, atividades e recursos financeiros.': 'AADVITA believes that transparency is fundamental to building trust and strengthening our relationship with the community. Therefore, we provide information about our management, activities and financial resources.',
        'Relatórios Financeiros': 'Financial Reports',
        'Acompanhe nossos relatórios financeiros, demonstrativos e balanços.': 'Follow our financial reports, statements and balances.',
        'Estatuto e Documentos': 'Statute and Documents',
        'Acesse nosso estatuto social, atas de reuniões e documentos oficiais.': 'Access our bylaws, meeting minutes and official documents.',
        'Prestação de Contas': 'Accountability',
        'Confira como utilizamos os recursos recebidos e os resultados alcançados.': 'See how we use the resources received and the results achieved.',
        'Projetos e Ações': 'Projects and Actions',
        'Veja os projetos desenvolvidos e ações realizadas em benefício da comunidade.': 'See the projects developed and actions carried out for the benefit of the community.',
        'Doações e Recursos': 'Donations and Resources',
        'Informações sobre doações recebidas e como contribuir com nossa causa.': 'Information about donations received and how to contribute to our cause.',
        'Diretoria e Conselho': 'Board and Council',
        'Conheça os membros da diretoria e conselho fiscal responsáveis pela gestão.': 'Meet the members of the board and fiscal council responsible for management.',
        'Em breve': 'Coming soon',
        'Ver Projetos': 'View Projects',
        'Ver Detalhes': 'View Details',
        'Voltar para Projetos': 'Back to Projects',
        'Término:': 'End:',
        'Identificação do Projeto': 'Project Identification',
        'Contexto e Justificativa': 'Context and Justification',
        'Objetivos': 'Objectives',
        'Público-Alvo': 'Target Audience',
        'Metodologia': 'Methodology',
        'Recursos Necessários': 'Necessary Resources',
        'Parcerias': 'Partnerships',
        'Resultados Esperados': 'Expected Results',
        'Monitoramento e Avaliação': 'Monitoring and Evaluation',
        'Cronograma de Execução': 'Execution Schedule',
        'Orçamento': 'Budget',
        'Exemplo Resumido': 'Summary Example',
        'Considerações Finais': 'Final Considerations',
        'Descrição': 'Description',
        'Ver Diretoria': 'View Board',
        'Ver Relatórios': 'View Reports',
        'Acompanhe nossas doações e gastos de forma transparente': 'Follow our donations and expenses transparently',
        'Doações Recebidas': 'Donations Received',
        'Gastos Realizados': 'Expenses Made',
        'Tipo': 'Type',
        'Descrição': 'Description',
        'Doador': 'Donor',
        'País': 'Country',
        'Valor/Quantidade': 'Value/Quantity',
        'Data': 'Date',
        'Observações': 'Observations',
        'Categoria': 'Category',
        'Fornecedor': 'Supplier',
        'Valor': 'Value',
        'Financeira': 'Financial',
        'Material': 'Material',
        'Serviço': 'Service',
        'itens': 'items',
        'unidades': 'units',
        'Total de Doações Financeiras': 'Total Financial Donations',
        'Total de Doações em Material': 'Total Material Donations',
        'Total de Doações em Serviços': 'Total Service Donations',
        'Total de Gastos': 'Total Expenses',
        'Nenhuma doação cadastrada no momento.': 'No donations registered at this time.',
        'Nenhum gasto cadastrado no momento.': 'No expenses registered at this time.',
        'Voltar para Transparência': 'Back to Transparency',
        'Baixar Documento': 'Download Document',
        'Acompanhe nossos relatórios financeiros, demonstrativos e balanços de forma transparente': 'Follow our financial reports, statements and balances transparently',
        'Nenhum relatório financeiro cadastrado no momento.': 'No financial reports registered at this time.',
        'Relatório': 'Report',
        'Demonstrativo': 'Statement',
        'Balanço': 'Balance',
        'Ver Relatórios': 'View Reports',
        'Ver Documentos': 'View Documents',
        'Ver Prestação de Contas': 'View Accountability',
        'Ver Informações': 'View Information',
        'Estatuto': 'Statute',
        'Ata': 'Minutes',
        'Acesse nosso estatuto social, atas de reuniões e documentos oficiais': 'Access our bylaws, meeting minutes and official documents',
        'Confira como utilizamos os recursos recebidos e os resultados alcançados': 'See how we use the resources received and the results achieved',
        'Informações sobre doações recebidas e como contribuir com nossa causa': 'Information about donations received and how to contribute to our cause',
        'Nenhum documento cadastrado no momento.': 'No documents registered at this time.',
        'Nenhuma prestação de contas cadastrada no momento.': 'No accountability reports registered at this time.',
        'Nenhuma informação de doação cadastrada no momento.': 'No donation information registered at this time.',
        'Período:': 'Period:',
        'A partir de': 'From',
        'Recursos Recebidos:': 'Resources Received:',
        'Resultados Alcançados:': 'Results Achieved:',
        'Como Contribuir:': 'How to Contribute:',
        'Informações de Contato': 'Contact Information',
        'Para mais informações sobre transparência, entre em contato conosco através dos canais oficiais.': 'For more information about transparency, contact us through official channels.',
        'E-mail:': 'Email:',
        'Telefone:': 'Phone:',
        'Entre em contato através do formulário': 'Contact us through the form',
        'Quem Somos': 'Who We Are',
        'A AADVITA - Associação dos Deficientes Visuais Tapuienses é uma organização sem fins lucrativos dedicada a promover a inclusão, acessibilidade e qualidade de vida para pessoas com deficiência visual em nossa comunidade.': 'AADVITA - Association of Visually Impaired Tapuienses is a non-profit organization dedicated to promoting inclusion, accessibility and quality of life for visually impaired people in our community.',
        'Nossa Missão': 'Our Mission',
        'Promover a inclusão social, educacional e profissional de pessoas com deficiência visual, oferecendo apoio, capacitação e recursos necessários para que possam desenvolver todo o seu potencial e participar plenamente da sociedade.': 'Promote social, educational and professional inclusion of visually impaired people, offering support, training and necessary resources so they can develop their full potential and fully participate in society.',
        'Nossos Valores': 'Our Values',
        'Inclusão:': 'Inclusion:',
        'Acreditamos que todos têm o direito de participar plenamente da sociedade': 'We believe everyone has the right to fully participate in society',
        'Respeito:': 'Respect:',
        'Valorizamos a diversidade e a dignidade de cada pessoa': 'We value diversity and the dignity of each person',
        'Compromisso:': 'Commitment:',
        'Trabalhamos com dedicação para alcançar nossos objetivos': 'We work with dedication to achieve our goals',
        'Solidariedade:': 'Solidarity:',
        'Apoiamos uns aos outros em nossa jornada coletiva': 'We support each other on our collective journey',
        'Transparência:': 'Transparency:',
        'Mantemos práticas éticas e transparentes em todas as nossas ações': 'We maintain ethical and transparent practices in all our actions',
        'Diretoria': 'Board of Directors',
        'Diretor de Comunicação': 'Director of Communications',
        'Presidente': 'President',
        'Vice Presidente': 'Vice-President',
        'Vice-Presidente': 'Vice-President',
        'Primeiro(a) Secretário(a)': 'First Secretary',
        'Segundo(a) Secretário(a)': 'Second Secretary',
        'Tesoureiro(a)': 'Treasurer',
        'Nome do Presidente': 'President Name',
        'Nome do Vice Presidente': 'Vice President Name',
        'Nome do Primeiro Secretário': 'First Secretary Name',
        'Nome do Segundo Secretário': 'Second Secretary Name',
        'Nome do Tesoureiro': 'Treasurer Name',
        'Primeiro Secretário(a)': 'First Secretary',
        'Segundo Secretário(a)': 'Second Secretary',
        'Primeiro Tesoureiro(a)': 'First Treasurer',
        'Conselho Fiscal': 'Fiscal Council',
        'Conselheiro': 'Councilor',
        'Conselheiro(a)': 'Councilor',
        'Coordenação Social': 'Social Coordination',
        'Coordenador(a)': 'Coordinator',
        'Membro da Coordenação Social': 'Coordinator',
        'Nenhum coordenador(a) cadastrado(a).': 'No coordinator(s) registered.',
        'Conselheiro': 'Councilor',
        'Nome do Conselheiro 1': 'Councilor 1 Name',
        'Nome do Conselheiro 2': 'Councilor 2 Name',
        'Associação dedicada a promover a inclusão e acessibilidade para pessoas com deficiência visual.': 'Association dedicated to promoting inclusion and accessibility for visually impaired people.',
        'Contato': 'Contact',
        'Links Rápidos': 'Quick Links',
        'Não há reuniões presenciais programadas no momento.': 'No in-person meetings scheduled at this time.',
        'Não há reuniões virtuais programadas no momento.': 'No virtual meetings scheduled at this time.',
        'Não há projetos cadastrados no momento.': 'No projects registered at this time.',
        'Não há ações cadastradas no momento.': 'No actions registered at this time.',
        'Não há reuniões presenciais cadastradas no momento.': 'No in-person meetings registered at this time.',
        'Não há reuniões virtuais cadastradas no momento.': 'No virtual meetings registered at this time.',
        'Volte em breve para conferir nossa agenda atualizada.': 'Come back soon to check our updated schedule.',
        'Acessar reunião': 'Join meeting',
        'Acessar evento': 'Join event',
        'Local:': 'Location:',
        'Endereço:': 'Address:',
        'Plataforma:': 'Platform:',
        'Data:': 'Date:',
        'Hora:': 'Time:',
        'Visitar site': 'Visit website',
        'Não há apoiadores cadastrados no momento.': 'No supporters registered at this time.',
        'Galeria': 'Gallery',
        'Galeria de Imagens': 'Image Gallery',
        'Fotos de Eventos': 'Event Photos',
        'Fotos de Ações': 'Action Photos',
        'Galeria Geral': 'General Gallery',
        'Confira nossa galeria completa de álbuns': 'Check out our complete album gallery',
        'Ver Álbum': 'View Album',
        'Voltar para Galeria': 'Back to Gallery',
        'foto(s)': 'photo(s)',
        'Este álbum ainda não possui fotos.': 'This album does not have photos yet.',
        'Nenhum álbum cadastrado no momento.': 'No albums registered at this time.',
        'Álbuns:': 'Albums:',
        'Enviar Imagem': 'Upload Image',
        'Título (opcional)': 'Title (optional)',
        'Descrição (opcional)': 'Description (optional)',
        'Selecionar arquivo': 'Select file',
        'Nenhuma imagem cadastrada no momento.': 'No images registered at this time.',
        'Imagem ampliada': 'Enlarged image',
        'Fechar': 'Close',
        'Anterior': 'Previous',
        'Próxima': 'Next',
        'Vídeos': 'Videos',
        'Nossos Vídeos': 'Our Videos',
        'Confira nossos vídeos e conteúdos em vídeo': 'Check out our videos and video content',
        'Vídeos em Destaque': 'Featured Videos',
        'Ver todos os vídeos': 'View all videos',
        'Nenhum vídeo cadastrado no momento.': 'No videos registered at this time.',
        'Assistir vídeo': 'Watch video',
        'Associe-se': 'Join Us',
        'Eventos': 'Events',
        'Próximos Eventos': 'Upcoming Events',
        'Ver todos os eventos': 'View all events',
        'Não há eventos cadastrados no momento.': 'No events registered at this time.',
        'Tipo:': 'Type:',
        'Ir para conteúdo principal': 'Skip to main content',
        'Abrir menu': 'Open menu',
        'Menu': 'Menu',
        'Navegação principal': 'Main navigation',
        'AADVITA - Página inicial': 'AADVITA - Home page',
        'Português': 'Portuguese',
        'Español': 'Spanish',
        'English': 'English',
        'Fechar mensagem': 'Close message',
        'Email:': 'Email:',
        'Telefone:': 'Phone:',
        'WhatsApp:': 'WhatsApp:',
        'Doações': 'Donations',
        'QR Code para doação': 'QR Code for donation',
        'Todos os direitos reservados.': 'All rights reserved.',
        'Desenvolvido por:': 'Developed by:',
        'AADVITA - Associação de Deficientes Visuais': 'AADVITA - Association of Visually Impaired',
        '(abre em nova aba)': '(opens in new tab)',
        'Entrar': 'Login',
        'Acesse sua conta ou área administrativa': 'Access your account or administrative area',
        'Associado': 'Member',
        'Administrador': 'Administrator',
        'Digite seu CPF cadastrado': 'Enter your registered CPF',
        'Senha': 'Password',
        'Digite sua senha': 'Enter your password',
        'Opções de idioma': 'Language options',
        'Associação dos Deficientes Visuais Tapuienses AADVITA - Promovendo inclusão e acessibilidade': 'Association of Visually Impaired Tapuienses AADVITA - Promoting inclusion and accessibility',
        'AADVITA - Associação dos Deficientes Visuais Tapuienses': 'AADVITA - Association of Visually Impaired Tapuienses',
    }
}

def get_locale():
    """Retorna o idioma atual da sessão"""
    return session.get('language', 'pt')

def _(text):
    """Função de tradução simples"""
    lang = get_locale()
    return TRANSLATIONS.get(lang, TRANSLATIONS['pt']).get(text, text)

# Filtro para converter quebras de linha em <br>
@app.template_filter('nl2br')
def nl2br_filter(text):
    if text:
        return text.replace('\n', '<br>')
    return text

# Modelos de Base de Datos
# Tabela de associação para Usuario e Permissao
usuario_permissao = db.Table('usuario_permissao',
    db.Column('usuario_id', db.Integer, db.ForeignKey('usuario.id'), primary_key=True),
    db.Column('permissao_id', db.Integer, db.ForeignKey('permissao.id'), primary_key=True)
)

class Permissao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), unique=True, nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.String(255))
    categoria = db.Column(db.String(50))  # Para agrupar permissões
    
    def __repr__(self):
        return f'<Permissao {self.codigo}>'

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    nome = db.Column(db.String(200), nullable=False)
    is_super_admin = db.Column(db.Boolean, default=False)  # Super admin tem acesso a tudo
    created_at = db.Column(db.DateTime, default=lambda: datetime.now())
    
    # Relacionamento many-to-many com permissões
    permissoes = db.relationship('Permissao', secondary=usuario_permissao, lazy='subquery', backref=db.backref('usuarios', lazy=True))
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def tem_permissao(self, codigo_permissao):
        """Verifica se o usuário tem uma permissão específica"""
        if self.is_super_admin:
            return True
        return any(p.codigo == codigo_permissao for p in self.permissoes)

class Configuracao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(100), unique=True, nullable=False)
    valor = db.Column(db.Text)
    tipo = db.Column(db.String(50))  # texto, numero, imagem, etc
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ReunionPresencial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text)
    fecha = db.Column(db.DateTime, nullable=False)
    hora = db.Column(db.String(10), nullable=False)
    lugar = db.Column(db.String(300), nullable=False)
    direccion = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ReunionVirtual(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text)
    fecha = db.Column(db.DateTime, nullable=False)
    hora = db.Column(db.String(10), nullable=False)
    plataforma = db.Column(db.String(100), nullable=False)
    link = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Projeto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    identificacao = db.Column(db.Text)
    contexto_justificativa = db.Column(db.Text)
    objetivos = db.Column(db.Text)
    publico_alvo = db.Column(db.Text)
    metodologia = db.Column(db.Text)
    recursos_necessarios = db.Column(db.Text)
    parcerias = db.Column(db.Text)
    resultados_esperados = db.Column(db.Text)
    monitoramento_avaliacao = db.Column(db.Text)
    cronograma_execucao = db.Column(db.Text)
    orcamento = db.Column(db.Text)
    consideracoes_finais = db.Column(db.Text)
    imagen = db.Column(db.String(300))
    estado = db.Column(db.String(50), default='Ativo')
    data_inicio = db.Column(db.Date)
    data_fim = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Tabelas de associação (definidas antes das classes que as usam)
evento_album = db.Table('evento_album',
    db.Column('evento_id', db.Integer, db.ForeignKey('evento.id'), primary_key=True),
    db.Column('album_id', db.Integer, db.ForeignKey('album.id'), primary_key=True)
)

acao_album = db.Table('acao_album',
    db.Column('acao_id', db.Integer, db.ForeignKey('acao.id'), primary_key=True),
    db.Column('album_id', db.Integer, db.ForeignKey('album.id'), primary_key=True)
)

class Acao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    data = db.Column(db.Date, nullable=False)
    categoria = db.Column(db.String(100))
    imagem = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamento com fotos
    fotos = db.relationship('AcaoFoto', backref='acao', lazy=True, cascade='all, delete-orphan')
    
    # Relacionamento many-to-many com álbuns
    albuns = db.relationship('Album', secondary=acao_album, lazy='subquery', backref=db.backref('acoes', lazy=True))

class AcaoFoto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    acao_id = db.Column(db.Integer, db.ForeignKey('acao.id'), nullable=False)
    caminho = db.Column(db.String(300), nullable=False)
    titulo = db.Column(db.String(200))
    descricao = db.Column(db.Text)
    ordem = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Apoiador(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(100))  # Empresa, Individual, Instituição
    logo = db.Column(db.String(300))
    website = db.Column(db.String(500))
    descricao = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now())

class Imagem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200))
    descricao = db.Column(db.Text)
    filename = db.Column(db.String(300), nullable=False)
    caminho = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SliderImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200))
    imagem = db.Column(db.String(300), nullable=False)  # Caminho da imagem
    link = db.Column(db.String(500))  # Link clicável (opcional)
    ordem = db.Column(db.Integer, default=0)  # Ordem de exibição
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<SliderImage {self.id}>'

class Album(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo_pt = db.Column(db.String(200), nullable=False)
    titulo_es = db.Column(db.String(200))
    titulo_en = db.Column(db.String(200))
    descricao_pt = db.Column(db.Text)
    descricao_es = db.Column(db.Text)
    descricao_en = db.Column(db.Text)
    capa = db.Column(db.String(300))  # Caminho da foto de capa
    ordem = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamento com fotos
    fotos = db.relationship('AlbumFoto', backref='album', lazy=True, cascade='all, delete-orphan')

class AlbumFoto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    album_id = db.Column(db.Integer, db.ForeignKey('album.id'), nullable=False)
    caminho = db.Column(db.String(300), nullable=False)
    titulo_pt = db.Column(db.String(200))
    titulo_es = db.Column(db.String(200))
    titulo_en = db.Column(db.String(200))
    descricao_pt = db.Column(db.Text)
    descricao_es = db.Column(db.Text)
    descricao_en = db.Column(db.Text)
    ordem = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Evento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text)
    data = db.Column(db.DateTime, nullable=False)
    hora = db.Column(db.String(10))
    local = db.Column(db.String(300))
    endereco = db.Column(db.Text)
    tipo = db.Column(db.String(100))  # Presencial, Virtual, Híbrido
    link = db.Column(db.String(500))
    imagem = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamento com fotos
    fotos = db.relationship('EventoFoto', backref='evento', lazy=True, cascade='all, delete-orphan')
    
    # Relacionamento many-to-many com álbuns
    albuns = db.relationship('Album', secondary=evento_album, lazy='subquery', backref=db.backref('eventos', lazy=True))

class EventoFoto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    evento_id = db.Column(db.Integer, db.ForeignKey('evento.id'), nullable=False)
    caminho = db.Column(db.String(300), nullable=False)
    titulo = db.Column(db.String(200))
    descricao = db.Column(db.Text)
    ordem = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text)
    url_youtube = db.Column(db.String(500), nullable=False)
    thumbnail = db.Column(db.String(500))
    categoria = db.Column(db.String(100))
    ordem = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def get_youtube_id(self):
        """Extrai o ID do vídeo do YouTube da URL"""
        import re
        # Suporta diferentes formatos de URL do YouTube
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, self.url_youtube)
            if match:
                return match.group(1)
        return None
    
    def get_embed_url(self):
        """Retorna a URL para embed do vídeo"""
        video_id = self.get_youtube_id()
        if video_id:
            return f"https://www.youtube.com/embed/{video_id}"
        return None
    
    def get_thumbnail_url(self):
        """Retorna a URL da thumbnail do YouTube"""
        video_id = self.get_youtube_id()
        if video_id:
            return f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
        return None

class Associado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome_completo = db.Column(db.String(200), nullable=False)
    cpf = db.Column(db.String(14), nullable=False, unique=True)
    data_nascimento = db.Column(db.Date, nullable=False)
    endereco = db.Column(db.Text, nullable=False)
    telefone = db.Column(db.String(20), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pendente')  # pendente, aprovado, negado
    # Campos para mensalidade
    valor_mensalidade = db.Column(db.Numeric(10, 2), default=0.00)
    desconto_tipo = db.Column(db.String(10), default=None)  # 'real' ou 'porcentagem'
    desconto_valor = db.Column(db.Numeric(10, 2), default=0.00)
    ativo = db.Column(db.Boolean, default=True)  # Controla se gera mensalidades automaticamente
    carteira_pdf = db.Column(db.String(300))  # Caminho do PDF da carteira de associado
    foto = db.Column(db.String(300))  # Caminho da foto do associado
    created_at = db.Column(db.DateTime, default=lambda: datetime.now())
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def calcular_valor_final(self):
        """Calcula o valor final da mensalidade com desconto"""
        valor_base = float(self.valor_mensalidade) if self.valor_mensalidade else 0.0
        desconto = float(self.desconto_valor) if self.desconto_valor else 0.0
        
        if self.desconto_tipo == 'porcentagem':
            valor_final = valor_base * (1 - desconto / 100)
        elif self.desconto_tipo == 'real':
            valor_final = valor_base - desconto
        else:
            valor_final = valor_base
        
        return max(0.0, valor_final)  # Não permite valor negativo

class Mensalidade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    associado_id = db.Column(db.Integer, db.ForeignKey('associado.id'), nullable=False)
    valor_base = db.Column(db.Numeric(10, 2), nullable=False)
    desconto_tipo = db.Column(db.String(10))  # 'real' ou 'porcentagem'
    desconto_valor = db.Column(db.Numeric(10, 2), default=0.00)
    valor_final = db.Column(db.Numeric(10, 2), nullable=False)
    mes_referencia = db.Column(db.Integer, nullable=False)  # 1-12
    ano_referencia = db.Column(db.Integer, nullable=False)
    data_vencimento = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='pendente')  # pendente, paga, cancelada
    data_pagamento = db.Column(db.Date)
    observacoes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now())
    
    # Relacionamento
    associado = db.relationship('Associado', backref='mensalidades')

class Doacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(50), nullable=False)  # 'financeira', 'material', 'servico'
    descricao = db.Column(db.Text, nullable=False)
    valor = db.Column(db.Numeric(10, 2))  # Valor em dinheiro (para financeira e servico)
    quantidade = db.Column(db.Integer)  # Quantidade (para material)
    unidade = db.Column(db.String(50))  # Unidade (ex: 'kg', 'litros', 'unidades')
    doador = db.Column(db.String(200))  # Nome do doador
    pais = db.Column(db.String(100))  # País do doador
    telefone = db.Column(db.String(50))  # Telefone do doador
    tipo_documento = db.Column(db.String(20))  # 'cpf', 'cnpj', 'passaporte', 'dni', etc.
    documento = db.Column(db.String(30))  # Documento (sem formatação)
    data_doacao = db.Column(db.Date, nullable=False)
    observacoes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now())

class Gasto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.Text, nullable=False)
    valor = db.Column(db.Numeric(10, 2), nullable=False)
    categoria = db.Column(db.String(100))  # Ex: 'Aluguel', 'Material', 'Serviços', 'Salários', etc.
    data_gasto = db.Column(db.Date, nullable=False)
    fornecedor = db.Column(db.String(200))  # Nome do fornecedor
    observacoes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now())

class SobreConteudo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(50), unique=True, nullable=False)  # 'quem_somos', 'missao', 'valores'
    conteudo_pt = db.Column(db.Text)
    conteudo_es = db.Column(db.Text)
    conteudo_en = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class MembroDiretoria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cargo = db.Column(db.String(100), nullable=False)  # 'Presidente', 'Vice-Presidente', etc.
    nome_pt = db.Column(db.String(200), nullable=False)
    nome_es = db.Column(db.String(200))
    nome_en = db.Column(db.String(200))
    foto = db.Column(db.String(500))
    ordem = db.Column(db.Integer, default=0)  # Para ordenar os cargos
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class MembroConselhoFiscal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome_pt = db.Column(db.String(200), nullable=False)
    nome_es = db.Column(db.String(200))
    nome_en = db.Column(db.String(200))
    foto = db.Column(db.String(500))
    ordem = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class MembroCoordenacaoSocial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cargo = db.Column(db.String(100), nullable=False)  # 'Membro da Coordenação Social', etc.
    nome_pt = db.Column(db.String(200), nullable=False)
    nome_es = db.Column(db.String(200))
    nome_en = db.Column(db.String(200))
    foto = db.Column(db.String(500))
    ordem = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class DadosAssociacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    cnpj = db.Column(db.String(18), nullable=False)
    endereco = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @staticmethod
    def get_dados():
        """Retorna os dados da associação, criando um registro padrão se não existir"""
        dados = DadosAssociacao.query.first()
        if not dados:
            dados = DadosAssociacao(
                nome='Associação AADVITA',
                cnpj='00.000.000/0001-00',
                endereco='Endereço não informado'
            )
            db.session.add(dados)
            db.session.commit()
        return dados

class OQueFazemosServico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    cor_icone = db.Column(db.String(7), nullable=False, default='#3b82f6')  # Cor em hexadecimal
    icone_svg = db.Column(db.Text)  # SVG do ícone
    ordem = db.Column(db.Integer, default=0)
    coluna = db.Column(db.Integer, nullable=False, default=1)  # 1, 2 ou 3
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<OQueFazemosServico {self.titulo}>'

class InstagramPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url_instagram = db.Column(db.String(500))  # URL do post no Instagram
    imagem_url = db.Column(db.String(500), nullable=False)  # URL da imagem
    legenda = db.Column(db.Text)  # Legenda do post
    data_post = db.Column(db.DateTime, nullable=False)  # Data de publicação no Instagram
    ordem = db.Column(db.Integer, default=0)  # Ordem de exibição
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<InstagramPost {self.id}>'

class RelatorioFinanceiro(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo_pt = db.Column(db.String(200), nullable=False)
    titulo_es = db.Column(db.String(200))
    titulo_en = db.Column(db.String(200))
    descricao_pt = db.Column(db.Text)
    descricao_es = db.Column(db.Text)
    descricao_en = db.Column(db.Text)
    arquivo = db.Column(db.String(500))  # Caminho do arquivo PDF/documento
    data_relatorio = db.Column(db.Date)
    tipo = db.Column(db.String(50))  # 'relatorio', 'demonstrativo', 'balanco'
    ordem = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class EstatutoDocumento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo_pt = db.Column(db.String(200), nullable=False)
    titulo_es = db.Column(db.String(200))
    titulo_en = db.Column(db.String(200))
    descricao_pt = db.Column(db.Text)
    descricao_es = db.Column(db.Text)
    descricao_en = db.Column(db.Text)
    arquivo = db.Column(db.String(500))  # Caminho do arquivo PDF/documento
    tipo = db.Column(db.String(50))  # 'estatuto', 'ata', 'documento'
    data_documento = db.Column(db.Date)
    ordem = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PrestacaoConta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo_pt = db.Column(db.String(200), nullable=False)
    titulo_es = db.Column(db.String(200))
    titulo_en = db.Column(db.String(200))
    descricao_pt = db.Column(db.Text)
    descricao_es = db.Column(db.Text)
    descricao_en = db.Column(db.Text)
    recursos_recebidos_pt = db.Column(db.Text)
    recursos_recebidos_es = db.Column(db.Text)
    recursos_recebidos_en = db.Column(db.Text)
    resultados_pt = db.Column(db.Text)
    resultados_es = db.Column(db.Text)
    resultados_en = db.Column(db.Text)
    periodo_inicio = db.Column(db.Date)
    periodo_fim = db.Column(db.Date)
    arquivo = db.Column(db.String(500))
    ordem = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class InformacaoDoacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo_pt = db.Column(db.String(200), nullable=False)
    titulo_es = db.Column(db.String(200))
    titulo_en = db.Column(db.String(200))
    descricao_pt = db.Column(db.Text)
    descricao_es = db.Column(db.Text)
    descricao_en = db.Column(db.Text)
    como_contribuir_pt = db.Column(db.Text)
    como_contribuir_es = db.Column(db.Text)
    como_contribuir_en = db.Column(db.Text)
    ordem = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Informativo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(50), nullable=False)  # 'Noticia' ou 'Podcast'
    titulo = db.Column(db.String(200), nullable=False)
    subtitulo = db.Column(db.String(300))  # Subtítulo opcional
    conteudo = db.Column(db.Text)  # Texto para notícias
    url_soundcloud = db.Column(db.String(500))  # URL do SoundCloud para podcasts
    imagem = db.Column(db.String(300))  # Imagem opcional para notícias
    data_publicacao = db.Column(db.Date, nullable=False, default=date.today)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class RadioPrograma(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text)
    apresentador = db.Column(db.String(200))  # Nome do apresentador
    horario = db.Column(db.String(100))  # Ex: "Segunda a Sexta, 14h às 16h"
    url_streaming = db.Column(db.String(500))  # URL para streaming ao vivo
    url_arquivo = db.Column(db.String(500))  # URL para arquivo de áudio (episódio)
    imagem = db.Column(db.String(300))  # Imagem do programa
    ativo = db.Column(db.Boolean, default=True)
    ordem = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class RadioConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url_streaming_principal = db.Column(db.String(500))  # URL principal de streaming da rádio
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Banner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(50), nullable=False, unique=True)  # 'Campanhas', 'Apoie-nos', 'Editais'
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.String(300))
    url = db.Column(db.String(500))  # URL de destino
    imagem = db.Column(db.String(300))  # Imagem opcional do banner
    cor_gradiente_inicio = db.Column(db.String(7), default='#667eea')  # Cor inicial do gradiente
    cor_gradiente_fim = db.Column(db.String(7), default='#764ba2')  # Cor final do gradiente
    ativo = db.Column(db.Boolean, default=True)
    ordem = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamento com conteúdos
    conteudos = db.relationship('BannerConteudo', backref='banner', lazy=True, cascade='all, delete-orphan', order_by='BannerConteudo.ordem')

class BannerConteudo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    banner_id = db.Column(db.Integer, db.ForeignKey('banner.id'), nullable=False)
    titulo = db.Column(db.String(200), nullable=False)
    conteudo = db.Column(db.Text)  # Conteúdo HTML/texto
    imagem = db.Column(db.String(300))  # Imagem opcional
    arquivo_pdf = db.Column(db.String(300))  # Arquivo PDF opcional
    ordem = db.Column(db.Integer, default=0)
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Decorador para proteger rotas administrativas
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('Você precisa fazer login para acessar esta página', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def permissao_required(codigo_permissao):
    """Decorador para verificar se o usuário tem uma permissão específica"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get('admin_logged_in'):
                flash('Você precisa fazer login para acessar esta página', 'error')
                return redirect(url_for('admin_login'))
            
            usuario_id = session.get('admin_user_id')
            if usuario_id:
                usuario = Usuario.query.get(usuario_id)
                if usuario and usuario.tem_permissao(codigo_permissao):
                    return f(*args, **kwargs)
            
            flash('Você não tem permissão para acessar esta funcionalidade', 'error')
            return redirect(url_for('admin_dashboard'))
        return decorated_function
    return decorator

# Decorador para proteger rotas de associados
def associado_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('associado_logged_in'):
            flash('Você precisa fazer login para acessar esta página', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ============================================
# ROTAS ADMINISTRATIVAS
# ============================================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        usuario = Usuario.query.filter_by(username=username).first()
        
        if usuario and usuario.check_password(password):
            session['admin_logged_in'] = True
            session['admin_username'] = username
            session['admin_nome'] = usuario.nome
            session['admin_user_id'] = usuario.id
            session['admin_is_super'] = usuario.is_super_admin
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Usuário ou senha incorretos', 'error')
    
    return render_template('admin/login.html')

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    flash('Logout realizado com sucesso!', 'success')
    return redirect(url_for('admin_login'))

@app.route('/admin')
@admin_required
def admin_dashboard():
    stats = {
        'reuniones_presenciales': ReunionPresencial.query.count(),
        'reuniones_virtuales': ReunionVirtual.query.count(),
        'projetos': Projeto.query.count(),
        'eventos': Evento.query.count(),
        'acoes': Acao.query.count(),
        'informativos': Informativo.query.count(),
        'radio_programas': RadioPrograma.query.filter_by(ativo=True).count(),
        'imagens': Imagem.query.count(),
        'videos': Video.query.count(),
        'associados': Associado.query.count(),
        'associados_pendentes': Associado.query.filter_by(status='pendente').count()
    }
    return render_template('admin/dashboard.html', stats=stats)

# ============================================
# CRUD - REUNIÕES PRESENCIAIS
# ============================================

@app.route('/admin/reuniones-presenciales')
@admin_required
def admin_reuniones_presenciales():
    reuniones = ReunionPresencial.query.order_by(ReunionPresencial.fecha.desc()).all()
    return render_template('admin/reuniones_presenciales.html', reuniones=reuniones)

@app.route('/admin/reuniones-presenciales/novo', methods=['GET', 'POST'])
@admin_required
def admin_reuniones_presenciales_novo():
    if request.method == 'POST':
        try:
            fecha_str = request.form.get('fecha')
            hora = request.form.get('hora')
            fecha_datetime = datetime.strptime(f"{fecha_str} {hora}", "%Y-%m-%d %H:%M")
            
            reunion = ReunionPresencial(
                titulo=request.form.get('titulo'),
                descripcion=request.form.get('descripcion'),
                fecha=fecha_datetime,
                hora=hora,
                lugar=request.form.get('lugar'),
                direccion=request.form.get('direccion')
            )
            db.session.add(reunion)
            db.session.commit()
            flash('Reunião presencial criada com sucesso!', 'success')
            return redirect(url_for('admin_reuniones_presenciales'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar reunião: {str(e)}', 'error')
    
    return render_template('admin/reuniones_presenciales_form.html')

@app.route('/admin/reuniones-presenciales/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_reuniones_presenciales_editar(id):
    reunion = ReunionPresencial.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            fecha_str = request.form.get('fecha')
            hora = request.form.get('hora')
            fecha_datetime = datetime.strptime(f"{fecha_str} {hora}", "%Y-%m-%d %H:%M")
            
            reunion.titulo = request.form.get('titulo')
            reunion.descripcion = request.form.get('descripcion')
            reunion.fecha = fecha_datetime
            reunion.hora = hora
            reunion.lugar = request.form.get('lugar')
            reunion.direccion = request.form.get('direccion')
            
            db.session.commit()
            flash('Reunião presencial atualizada com sucesso!', 'success')
            return redirect(url_for('admin_reuniones_presenciales'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar reunião: {str(e)}', 'error')
    
    return render_template('admin/reuniones_presenciales_form.html', reunion=reunion)

@app.route('/admin/reuniones-presenciales/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_reuniones_presenciales_excluir(id):
    reunion = ReunionPresencial.query.get_or_404(id)
    try:
        # Excluir do banco de dados
        db.session.delete(reunion)
        db.session.commit()
        flash('Reunião presencial excluída com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir reunião: {str(e)}', 'error')
        import traceback
        traceback.print_exc()
    return redirect(url_for('admin_reuniones_presenciales'))

# ============================================
# CRUD - REUNIÕES VIRTUAIS
# ============================================

@app.route('/admin/reuniones-virtuales')
@admin_required
def admin_reuniones_virtuales():
    reuniones = ReunionVirtual.query.order_by(ReunionVirtual.fecha.desc()).all()
    return render_template('admin/reuniones_virtuales.html', reuniones=reuniones)

@app.route('/admin/reuniones-virtuales/novo', methods=['GET', 'POST'])
@admin_required
def admin_reuniones_virtuales_novo():
    if request.method == 'POST':
        try:
            fecha_str = request.form.get('fecha')
            hora = request.form.get('hora')
            fecha_datetime = datetime.strptime(f"{fecha_str} {hora}", "%Y-%m-%d %H:%M")
            
            reunion = ReunionVirtual(
                titulo=request.form.get('titulo'),
                descripcion=request.form.get('descripcion'),
                fecha=fecha_datetime,
                hora=hora,
                plataforma=request.form.get('plataforma'),
                link=request.form.get('link')
            )
            db.session.add(reunion)
            db.session.commit()
            flash('Reunião virtual criada com sucesso!', 'success')
            return redirect(url_for('admin_reuniones_virtuales'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar reunião: {str(e)}', 'error')
    
    return render_template('admin/reuniones_virtuales_form.html')

@app.route('/admin/reuniones-virtuales/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_reuniones_virtuales_editar(id):
    reunion = ReunionVirtual.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            fecha_str = request.form.get('fecha')
            hora = request.form.get('hora')
            fecha_datetime = datetime.strptime(f"{fecha_str} {hora}", "%Y-%m-%d %H:%M")
            
            reunion.titulo = request.form.get('titulo')
            reunion.descripcion = request.form.get('descripcion')
            reunion.fecha = fecha_datetime
            reunion.hora = hora
            reunion.plataforma = request.form.get('plataforma')
            reunion.link = request.form.get('link')
            
            db.session.commit()
            flash('Reunião virtual atualizada com sucesso!', 'success')
            return redirect(url_for('admin_reuniones_virtuales'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar reunião: {str(e)}', 'error')
    
    return render_template('admin/reuniones_virtuales_form.html', reunion=reunion)

@app.route('/admin/reuniones-virtuales/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_reuniones_virtuales_excluir(id):
    reunion = ReunionVirtual.query.get_or_404(id)
    try:
        # Excluir do banco de dados
        db.session.delete(reunion)
        db.session.commit()
        flash('Reunião virtual excluída com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir reunião: {str(e)}', 'error')
        import traceback
        traceback.print_exc()
    return redirect(url_for('admin_reuniones_virtuales'))

# ============================================
# CRUD - PROJETOS
# ============================================

@app.route('/admin/projetos')
@admin_required
def admin_projetos():
    projetos = Projeto.query.order_by(Projeto.created_at.desc()).all()
    return render_template('admin/projetos.html', projetos=projetos)

@app.route('/admin/projetos/novo', methods=['GET', 'POST'])
@admin_required
def admin_projetos_novo():
    if request.method == 'POST':
        try:
            data_inicio_str = request.form.get('data_inicio')
            data_fim_str = request.form.get('data_fim')
            
            # Processar upload da foto
            imagen_path = None
            if 'imagen' in request.files:
                file = request.files['imagen']
                if file and file.filename != '' and allowed_file(file.filename):
                    upload_folder = app.config['UPLOAD_FOLDER']
                    os.makedirs(upload_folder, exist_ok=True)
                    
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    filepath = os.path.join(upload_folder, unique_filename)
                    file.save(filepath)
                    
                    imagen_path = f"images/uploads/{unique_filename}"
                elif file and file.filename != '':
                    flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP', 'error')
                    return redirect(url_for('admin_projetos_novo'))
            
            projeto = Projeto(
                titulo=request.form.get('titulo'),
                descripcion=request.form.get('descripcion'),
                identificacao=request.form.get('identificacao'),
                contexto_justificativa=request.form.get('contexto_justificativa'),
                objetivos=request.form.get('objetivos'),
                publico_alvo=request.form.get('publico_alvo'),
                metodologia=request.form.get('metodologia'),
                recursos_necessarios=request.form.get('recursos_necessarios'),
                parcerias=request.form.get('parcerias'),
                resultados_esperados=request.form.get('resultados_esperados'),
                monitoramento_avaliacao=request.form.get('monitoramento_avaliacao'),
                cronograma_execucao=request.form.get('cronograma_execucao'),
                orcamento=request.form.get('orcamento'),
                consideracoes_finais=request.form.get('consideracoes_finais'),
                estado=request.form.get('estado', 'Ativo'),
                data_inicio=datetime.strptime(data_inicio_str, "%Y-%m-%d").date() if data_inicio_str else None,
                data_fim=datetime.strptime(data_fim_str, "%Y-%m-%d").date() if data_fim_str else None,
                imagen=imagen_path
            )
            db.session.add(projeto)
            db.session.commit()
            flash('Projeto criado com sucesso!', 'success')
            return redirect(url_for('admin_projetos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar projeto: {str(e)}', 'error')
    
    return render_template('admin/projetos_form.html')

@app.route('/admin/projetos/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_projetos_editar(id):
    projeto = Projeto.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            data_inicio_str = request.form.get('data_inicio')
            data_fim_str = request.form.get('data_fim')
            
            # Processar upload da foto (se uma nova foi enviada)
            if 'imagen' in request.files:
                file = request.files['imagen']
                if file and file.filename != '' and allowed_file(file.filename):
                    # Remover foto antiga se existir
                    if projeto.imagen:
                        old_filepath = os.path.join('static', projeto.imagen)
                        if os.path.exists(old_filepath):
                            try:
                                os.remove(old_filepath)
                            except:
                                pass
                    
                    upload_folder = app.config['UPLOAD_FOLDER']
                    os.makedirs(upload_folder, exist_ok=True)
                    
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    filepath = os.path.join(upload_folder, unique_filename)
                    file.save(filepath)
                    
                    projeto.imagen = f"images/uploads/{unique_filename}"
                elif file and file.filename != '':
                    flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP', 'error')
                    return redirect(url_for('admin_projetos_editar', id=id))
            
            projeto.titulo = request.form.get('titulo')
            projeto.descripcion = request.form.get('descripcion')
            projeto.identificacao = request.form.get('identificacao')
            projeto.contexto_justificativa = request.form.get('contexto_justificativa')
            projeto.objetivos = request.form.get('objetivos')
            projeto.publico_alvo = request.form.get('publico_alvo')
            projeto.metodologia = request.form.get('metodologia')
            projeto.recursos_necessarios = request.form.get('recursos_necessarios')
            projeto.parcerias = request.form.get('parcerias')
            projeto.resultados_esperados = request.form.get('resultados_esperados')
            projeto.monitoramento_avaliacao = request.form.get('monitoramento_avaliacao')
            projeto.cronograma_execucao = request.form.get('cronograma_execucao')
            projeto.orcamento = request.form.get('orcamento')
            projeto.consideracoes_finais = request.form.get('consideracoes_finais')
            projeto.estado = request.form.get('estado', 'Ativo')
            projeto.data_inicio = datetime.strptime(data_inicio_str, "%Y-%m-%d").date() if data_inicio_str else None
            projeto.data_fim = datetime.strptime(data_fim_str, "%Y-%m-%d").date() if data_fim_str else None
            
            db.session.commit()
            flash('Projeto atualizado com sucesso!', 'success')
            return redirect(url_for('admin_projetos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar projeto: {str(e)}', 'error')
    
    return render_template('admin/projetos_form.html', projeto=projeto)

@app.route('/admin/projetos/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_projetos_excluir(id):
    projeto = Projeto.query.get_or_404(id)
    try:
        # Remover arquivo físico da imagem se existir
        if projeto.imagen:
            old_filepath = os.path.join('static', projeto.imagen)
            if os.path.exists(old_filepath):
                try:
                    os.remove(old_filepath)
                except Exception as e:
                    print(f"Erro ao remover arquivo da imagem: {str(e)}")
        
        # Excluir do banco de dados
        db.session.delete(projeto)
        db.session.commit()
        flash('Projeto excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir projeto: {str(e)}', 'error')
        import traceback
        traceback.print_exc()
    return redirect(url_for('admin_projetos'))

# ============================================
# CRUD - EVENTOS
# ============================================

@app.route('/admin/eventos')
@admin_required
def admin_eventos():
    eventos = Evento.query.order_by(Evento.data.desc()).all()
    return render_template('admin/eventos.html', eventos=eventos)

@app.route('/admin/eventos/novo', methods=['GET', 'POST'])
@admin_required
def admin_eventos_novo():
    if request.method == 'POST':
        try:
            data_str = request.form.get('data')
            hora = request.form.get('hora')
            data_datetime = datetime.strptime(f"{data_str} {hora}", "%Y-%m-%d %H:%M") if hora else datetime.strptime(data_str, "%Y-%m-%d")
            
            # Processar upload da foto
            imagem_path = None
            if 'imagem' in request.files:
                file = request.files['imagem']
                if file and file.filename != '' and allowed_file(file.filename):
                    upload_folder = app.config['UPLOAD_FOLDER']
                    os.makedirs(upload_folder, exist_ok=True)
                    
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    filepath = os.path.join(upload_folder, unique_filename)
                    file.save(filepath)
                    
                    imagem_path = f"images/uploads/{unique_filename}"
                elif file and file.filename != '':
                    flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP', 'error')
                    return redirect(url_for('admin_eventos_novo'))
            
            evento = Evento(
                titulo=request.form.get('titulo'),
                descricao=request.form.get('descricao'),
                data=data_datetime,
                hora=hora,
                local=request.form.get('local'),
                endereco=request.form.get('endereco'),
                tipo=request.form.get('tipo'),
                link=request.form.get('link'),
                imagem=imagem_path
            )
            db.session.add(evento)
            db.session.flush()  # Para obter o ID do evento
            
            # Processar álbuns selecionados
            albuns_selecionados = request.form.getlist('albuns')
            if albuns_selecionados:
                albuns_objs = Album.query.filter(Album.id.in_([int(aid) for aid in albuns_selecionados])).all()
                evento.albuns = albuns_objs
            
            db.session.commit()
            flash('Evento criado com sucesso!', 'success')
            return redirect(url_for('admin_eventos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar evento: {str(e)}', 'error')
    
    albuns = Album.query.order_by(Album.titulo_pt.asc()).all()
    return render_template('admin/eventos_form.html', albuns=albuns)

@app.route('/admin/eventos/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_eventos_editar(id):
    evento = Evento.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            data_str = request.form.get('data')
            hora = request.form.get('hora')
            data_datetime = datetime.strptime(f"{data_str} {hora}", "%Y-%m-%d %H:%M") if hora else datetime.strptime(data_str, "%Y-%m-%d")
            
            # Processar upload da foto (se uma nova foi enviada)
            if 'imagem' in request.files:
                file = request.files['imagem']
                if file and file.filename != '' and allowed_file(file.filename):
                    # Remover foto antiga se existir
                    if evento.imagem:
                        old_filepath = os.path.join('static', evento.imagem)
                        if os.path.exists(old_filepath):
                            try:
                                os.remove(old_filepath)
                            except:
                                pass
                    
                    upload_folder = app.config['UPLOAD_FOLDER']
                    os.makedirs(upload_folder, exist_ok=True)
                    
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    filepath = os.path.join(upload_folder, unique_filename)
                    file.save(filepath)
                    
                    evento.imagem = f"images/uploads/{unique_filename}"
                elif file and file.filename != '':
                    flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP', 'error')
                    return redirect(url_for('admin_eventos_editar', id=id))
            
            evento.titulo = request.form.get('titulo')
            evento.descricao = request.form.get('descricao')
            evento.data = data_datetime
            evento.hora = hora
            evento.local = request.form.get('local')
            evento.endereco = request.form.get('endereco')
            evento.tipo = request.form.get('tipo')
            evento.link = request.form.get('link')
            
            # Processar álbuns selecionados
            albuns_selecionados = request.form.getlist('albuns')
            albuns_objs = Album.query.filter(Album.id.in_([int(aid) for aid in albuns_selecionados])).all()
            evento.albuns = albuns_objs
            
            db.session.commit()
            flash('Evento atualizado com sucesso!', 'success')
            return redirect(url_for('admin_eventos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar evento: {str(e)}', 'error')
    
    albuns = Album.query.order_by(Album.titulo_pt.asc()).all()
    return render_template('admin/eventos_form.html', evento=evento, albuns=albuns)

@app.route('/admin/eventos/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_eventos_excluir(id):
    evento = Evento.query.get_or_404(id)
    try:
        # Remover arquivo físico da imagem se existir
        if evento.imagem:
            old_filepath = os.path.join('static', evento.imagem)
            if os.path.exists(old_filepath):
                try:
                    os.remove(old_filepath)
                except Exception as e:
                    print(f"Erro ao remover arquivo da imagem: {str(e)}")
        
        # Excluir do banco de dados
        db.session.delete(evento)
        db.session.commit()
        flash('Evento excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir evento: {str(e)}', 'error')
        import traceback
        traceback.print_exc()
    return redirect(url_for('admin_eventos'))

# ============================================
# GERENCIAR FOTOS DE EVENTOS
# ============================================

@app.route('/admin/eventos/<int:id>/fotos')
@admin_required
def admin_eventos_fotos(id):
    evento = Evento.query.get_or_404(id)
    fotos = EventoFoto.query.filter_by(evento_id=id).order_by(EventoFoto.ordem.asc(), EventoFoto.created_at.desc()).all()
    return render_template('admin/eventos_fotos.html', evento=evento, fotos=fotos)

@app.route('/admin/eventos/<int:id>/fotos/adicionar', methods=['POST'])
@admin_required
def admin_eventos_fotos_adicionar(id):
    evento = Evento.query.get_or_404(id)
    
    if 'foto' not in request.files:
        flash('Nenhum arquivo selecionado', 'error')
        return redirect(url_for('admin_eventos_fotos', id=id))
    
    file = request.files['foto']
    if file.filename == '':
        flash('Nenhum arquivo selecionado', 'error')
        return redirect(url_for('admin_eventos_fotos', id=id))
    
    if file and allowed_file(file.filename):
        try:
            upload_folder = app.config['UPLOAD_FOLDER']
            os.makedirs(upload_folder, exist_ok=True)
            
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4()}_{filename}"
            filepath = os.path.join(upload_folder, unique_filename)
            file.save(filepath)
            
            ordem = request.form.get('ordem', 0)
            foto = EventoFoto(
                evento_id=id,
                caminho=f"images/uploads/{unique_filename}",
                titulo=request.form.get('titulo'),
                descricao=request.form.get('descricao'),
                ordem=int(ordem) if ordem else 0
            )
            db.session.add(foto)
            db.session.commit()
            flash('Foto adicionada com sucesso!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao adicionar foto: {str(e)}', 'error')
    else:
        flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP', 'error')
    
    return redirect(url_for('admin_eventos_fotos', id=id))

@app.route('/admin/eventos/fotos/<int:foto_id>/excluir', methods=['POST'])
@admin_required
def admin_eventos_fotos_excluir(foto_id):
    foto = EventoFoto.query.get_or_404(foto_id)
    evento_id = foto.evento_id
    
    try:
        # Remover arquivo físico
        if foto.caminho:
            filepath = os.path.join('static', foto.caminho)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except:
                    pass
        
        db.session.delete(foto)
        db.session.commit()
        flash('Foto excluída com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir foto: {str(e)}', 'error')
    
    return redirect(url_for('admin_eventos_fotos', id=evento_id))

# ============================================
# CRUD - AÇÕES
# ============================================

@app.route('/admin/acoes')
@admin_required
def admin_acoes():
    acoes = Acao.query.order_by(Acao.data.desc()).all()
    return render_template('admin/acoes.html', acoes=acoes)

@app.route('/admin/acoes/novo', methods=['GET', 'POST'])
@admin_required
def admin_acoes_novo():
    if request.method == 'POST':
        try:
            data_str = request.form.get('data')
            
            # Processar upload da foto
            imagem_path = None
            if 'imagem' in request.files:
                file = request.files['imagem']
                if file and file.filename != '' and allowed_file(file.filename):
                    upload_folder = app.config['UPLOAD_FOLDER']
                    os.makedirs(upload_folder, exist_ok=True)
                    
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    filepath = os.path.join(upload_folder, unique_filename)
                    file.save(filepath)
                    
                    imagem_path = f"images/uploads/{unique_filename}"
                elif file and file.filename != '':
                    flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP', 'error')
                    return redirect(url_for('admin_acoes_novo'))
            
            acao = Acao(
                titulo=request.form.get('titulo'),
                descricao=request.form.get('descricao'),
                data=datetime.strptime(data_str, "%Y-%m-%d").date(),
                categoria=request.form.get('categoria'),
                imagem=imagem_path
            )
            db.session.add(acao)
            db.session.commit()
            flash('Ação criada com sucesso!', 'success')
            return redirect(url_for('admin_acoes'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar ação: {str(e)}', 'error')
    
    albuns = Album.query.order_by(Album.titulo_pt.asc()).all()
    return render_template('admin/acoes_form.html', albuns=albuns)

@app.route('/admin/acoes/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_acoes_editar(id):
    acao = Acao.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            data_str = request.form.get('data')
            
            # Processar upload da foto (se uma nova foi enviada)
            if 'imagem' in request.files:
                file = request.files['imagem']
                if file and file.filename != '' and allowed_file(file.filename):
                    # Remover foto antiga se existir
                    if acao.imagem:
                        old_filepath = os.path.join('static', acao.imagem)
                        if os.path.exists(old_filepath):
                            try:
                                os.remove(old_filepath)
                            except:
                                pass
                    
                    upload_folder = app.config['UPLOAD_FOLDER']
                    os.makedirs(upload_folder, exist_ok=True)
                    
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    filepath = os.path.join(upload_folder, unique_filename)
                    file.save(filepath)
                    
                    acao.imagem = f"images/uploads/{unique_filename}"
                elif file and file.filename != '':
                    flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP', 'error')
                    return redirect(url_for('admin_acoes_editar', id=id))
            
            acao.titulo = request.form.get('titulo')
            acao.descricao = request.form.get('descricao')
            acao.data = datetime.strptime(data_str, "%Y-%m-%d").date()
            acao.categoria = request.form.get('categoria')
            
            # Processar álbuns selecionados
            albuns_selecionados = request.form.getlist('albuns')
            albuns_objs = Album.query.filter(Album.id.in_([int(aid) for aid in albuns_selecionados])).all()
            acao.albuns = albuns_objs
            
            db.session.commit()
            flash('Ação atualizada com sucesso!', 'success')
            return redirect(url_for('admin_acoes'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar ação: {str(e)}', 'error')
    
    albuns = Album.query.order_by(Album.titulo_pt.asc()).all()
    return render_template('admin/acoes_form.html', acao=acao, albuns=albuns)

@app.route('/admin/acoes/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_acoes_excluir(id):
    acao = Acao.query.get_or_404(id)
    try:
        # Remover arquivo físico da imagem se existir
        if acao.imagem:
            old_filepath = os.path.join('static', acao.imagem)
            if os.path.exists(old_filepath):
                try:
                    os.remove(old_filepath)
                except Exception as e:
                    print(f"Erro ao remover arquivo da imagem: {str(e)}")
        
        # Excluir do banco de dados
        db.session.delete(acao)
        db.session.commit()
        flash('Ação excluída com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir ação: {str(e)}', 'error')
        import traceback
        traceback.print_exc()
    return redirect(url_for('admin_acoes'))

# ============================================
# GERENCIAR FOTOS DE AÇÕES
# ============================================

@app.route('/admin/acoes/<int:id>/fotos')
@admin_required
def admin_acoes_fotos(id):
    acao = Acao.query.get_or_404(id)
    fotos = AcaoFoto.query.filter_by(acao_id=id).order_by(AcaoFoto.ordem.asc(), AcaoFoto.created_at.desc()).all()
    return render_template('admin/acoes_fotos.html', acao=acao, fotos=fotos)

@app.route('/admin/acoes/<int:id>/fotos/adicionar', methods=['POST'])
@admin_required
def admin_acoes_fotos_adicionar(id):
    acao = Acao.query.get_or_404(id)
    
    if 'foto' not in request.files:
        flash('Nenhum arquivo selecionado', 'error')
        return redirect(url_for('admin_acoes_fotos', id=id))
    
    file = request.files['foto']
    if file.filename == '':
        flash('Nenhum arquivo selecionado', 'error')
        return redirect(url_for('admin_acoes_fotos', id=id))
    
    if file and allowed_file(file.filename):
        try:
            upload_folder = app.config['UPLOAD_FOLDER']
            os.makedirs(upload_folder, exist_ok=True)
            
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4()}_{filename}"
            filepath = os.path.join(upload_folder, unique_filename)
            file.save(filepath)
            
            ordem = request.form.get('ordem', 0)
            foto = AcaoFoto(
                acao_id=id,
                caminho=f"images/uploads/{unique_filename}",
                titulo=request.form.get('titulo'),
                descricao=request.form.get('descricao'),
                ordem=int(ordem) if ordem else 0
            )
            db.session.add(foto)
            db.session.commit()
            flash('Foto adicionada com sucesso!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao adicionar foto: {str(e)}', 'error')
    else:
        flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP', 'error')
    
    return redirect(url_for('admin_acoes_fotos', id=id))

@app.route('/admin/acoes/fotos/<int:foto_id>/excluir', methods=['POST'])
@admin_required
def admin_acoes_fotos_excluir(foto_id):
    foto = AcaoFoto.query.get_or_404(foto_id)
    acao_id = foto.acao_id
    
    try:
        # Remover arquivo físico
        if foto.caminho:
            filepath = os.path.join('static', foto.caminho)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except:
                    pass
        
        db.session.delete(foto)
        db.session.commit()
        flash('Foto excluída com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir foto: {str(e)}', 'error')
    
    return redirect(url_for('admin_acoes_fotos', id=acao_id))

# ============================================
# CRUD - ÁLBUNS
# ============================================

@app.route('/admin/albuns')
@admin_required
def admin_albuns():
    albuns = Album.query.order_by(Album.ordem.asc(), Album.created_at.desc()).all()
    return render_template('admin/albuns.html', albuns=albuns)

@app.route('/admin/albuns/novo', methods=['GET', 'POST'])
@admin_required
def admin_albuns_novo():
    if request.method == 'POST':
        try:
            # Processar upload da capa (se uma foi enviada)
            capa_path = None
            if 'capa' in request.files:
                file = request.files['capa']
                if file and file.filename != '' and allowed_file(file.filename):
                    upload_folder = app.config['UPLOAD_FOLDER']
                    os.makedirs(upload_folder, exist_ok=True)
                    
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    filepath = os.path.join(upload_folder, unique_filename)
                    file.save(filepath)
                    
                    capa_path = f"images/uploads/{unique_filename}"
                elif file and file.filename != '':
                    flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP', 'error')
                    return redirect(url_for('admin_albuns_novo'))
            
            ordem = request.form.get('ordem', 0)
            album = Album(
                titulo_pt=request.form.get('titulo_pt'),
                titulo_es=request.form.get('titulo_es'),
                titulo_en=request.form.get('titulo_en'),
                descricao_pt=request.form.get('descricao_pt'),
                descricao_es=request.form.get('descricao_es'),
                descricao_en=request.form.get('descricao_en'),
                capa=capa_path,
                ordem=int(ordem) if ordem else 0
            )
            db.session.add(album)
            db.session.commit()
            flash('Álbum criado com sucesso!', 'success')
            return redirect(url_for('admin_albuns'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar álbum: {str(e)}', 'error')
    
    return render_template('admin/albuns_form.html')

@app.route('/admin/albuns/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_albuns_editar(id):
    album = Album.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            # Processar upload da capa (se uma nova foi enviada)
            if 'capa' in request.files:
                file = request.files['capa']
                if file and file.filename != '' and allowed_file(file.filename):
                    # Remover capa antiga se existir
                    if album.capa:
                        old_filepath = os.path.join('static', album.capa)
                        if os.path.exists(old_filepath):
                            try:
                                os.remove(old_filepath)
                            except:
                                pass
                    
                    upload_folder = app.config['UPLOAD_FOLDER']
                    os.makedirs(upload_folder, exist_ok=True)
                    
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    filepath = os.path.join(upload_folder, unique_filename)
                    file.save(filepath)
                    
                    album.capa = f"images/uploads/{unique_filename}"
                elif file and file.filename != '':
                    flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP', 'error')
                    return redirect(url_for('admin_albuns_editar', id=id))
            
            album.titulo_pt = request.form.get('titulo_pt')
            album.titulo_es = request.form.get('titulo_es')
            album.titulo_en = request.form.get('titulo_en')
            album.descricao_pt = request.form.get('descricao_pt')
            album.descricao_es = request.form.get('descricao_es')
            album.descricao_en = request.form.get('descricao_en')
            ordem = request.form.get('ordem', 0)
            album.ordem = int(ordem) if ordem else 0
            
            db.session.commit()
            flash('Álbum atualizado com sucesso!', 'success')
            return redirect(url_for('admin_albuns'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar álbum: {str(e)}', 'error')
    
    return render_template('admin/albuns_form.html', album=album)

@app.route('/admin/albuns/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_albuns_excluir(id):
    album = Album.query.get_or_404(id)
    try:
        # Remover capa se existir
        if album.capa:
            filepath = os.path.join('static', album.capa)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception as e:
                    print(f"Erro ao remover arquivo da capa: {str(e)}")
        
        # Excluir do banco de dados (as fotos serão removidas automaticamente pelo cascade)
        db.session.delete(album)
        db.session.commit()
        flash('Álbum excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir álbum: {str(e)}', 'error')
        import traceback
        traceback.print_exc()
    return redirect(url_for('admin_albuns'))

# ============================================
# GERENCIAR FOTOS DE ÁLBUNS
# ============================================

@app.route('/admin/albuns/<int:id>/fotos')
@admin_required
def admin_albuns_fotos(id):
    album = Album.query.get_or_404(id)
    fotos = AlbumFoto.query.filter_by(album_id=id).order_by(AlbumFoto.ordem.asc(), AlbumFoto.created_at.desc()).all()
    return render_template('admin/albuns_fotos.html', album=album, fotos=fotos)

@app.route('/admin/albuns/<int:id>/fotos/adicionar', methods=['POST'])
@admin_required
def admin_albuns_fotos_adicionar(id):
    album = Album.query.get_or_404(id)
    
    # Verificar se há arquivos no campo 'fotos' (múltiplos)
    if 'fotos' not in request.files:
        flash('Nenhum arquivo selecionado', 'error')
        return redirect(url_for('admin_albuns_fotos', id=id))
    
    files = request.files.getlist('fotos')
    
    # Filtrar apenas arquivos com nome (arquivos válidos)
    valid_files = [f for f in files if f.filename != '']
    
    if not valid_files:
        flash('Nenhum arquivo selecionado', 'error')
        return redirect(url_for('admin_albuns_fotos', id=id))
    
    upload_folder = app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)
    
    ordem_inicial = int(request.form.get('ordem_inicial', 0) or 0)
    fotos_adicionadas = 0
    erros = []
    
    try:
        for index, file in enumerate(valid_files):
            if allowed_file(file.filename):
                try:
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    filepath = os.path.join(upload_folder, unique_filename)
                    file.save(filepath)
                    
                    # Usar o nome do arquivo (sem extensão) como título padrão
                    nome_base = os.path.splitext(filename)[0]
                    
                    foto = AlbumFoto(
                        album_id=id,
                        caminho=f"images/uploads/{unique_filename}",
                        titulo_pt=nome_base,
                        ordem=ordem_inicial + index
                    )
                    db.session.add(foto)
                    fotos_adicionadas += 1
                except Exception as e:
                    erros.append(f"Erro ao processar {file.filename}: {str(e)}")
            else:
                erros.append(f"Tipo de arquivo não permitido: {file.filename}")
        
        db.session.commit()
        
        if fotos_adicionadas > 0:
            if fotos_adicionadas == 1:
                flash(f'{fotos_adicionadas} foto adicionada com sucesso!', 'success')
            else:
                flash(f'{fotos_adicionadas} fotos adicionadas com sucesso!', 'success')
        
        if erros:
            for erro in erros:
                flash(erro, 'error')
                
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao adicionar fotos: {str(e)}', 'error')
    
    return redirect(url_for('admin_albuns_fotos', id=id))

@app.route('/admin/albuns/fotos/<int:foto_id>/excluir', methods=['POST'])
@admin_required
def admin_albuns_fotos_excluir(foto_id):
    foto = AlbumFoto.query.get_or_404(foto_id)
    album_id = foto.album_id
    
    try:
        # Remover arquivo físico
        if foto.caminho:
            filepath = os.path.join('static', foto.caminho)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except:
                    pass
        
        db.session.delete(foto)
        db.session.commit()
        flash('Foto excluída com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir foto: {str(e)}', 'error')
    
    return redirect(url_for('admin_albuns_fotos', id=album_id))

# ============================================
# CRUD - IMAGENS
# ============================================

@app.route('/admin/imagens')
@admin_required
def admin_imagens():
    imagens = Imagem.query.order_by(Imagem.created_at.desc()).all()
    return render_template('admin/imagens.html', imagens=imagens)

@app.route('/admin/imagens/novo', methods=['GET', 'POST'])
@admin_required
def admin_imagens_novo():
    if request.method == 'POST':
        try:
            if 'file' not in request.files:
                flash('Nenhum arquivo selecionado', 'error')
                return redirect(url_for('admin_imagens_novo'))
            
            file = request.files['file']
            if file.filename == '':
                flash('Nenhum arquivo selecionado', 'error')
                return redirect(url_for('admin_imagens_novo'))
            
            if file and allowed_file(file.filename):
                upload_folder = app.config['UPLOAD_FOLDER']
                os.makedirs(upload_folder, exist_ok=True)
                
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4()}_{filename}"
                filepath = os.path.join(upload_folder, unique_filename)
                file.save(filepath)
                
                imagem = Imagem(
                    titulo=request.form.get('titulo', filename),
                    descricao=request.form.get('descricao'),
                    filename=unique_filename,
                    caminho=f"images/uploads/{unique_filename}"
                )
                db.session.add(imagem)
                db.session.commit()
                flash('Imagem enviada com sucesso!', 'success')
                return redirect(url_for('admin_imagens'))
            else:
                flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP', 'error')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao enviar imagem: {str(e)}', 'error')
    
    return render_template('admin/imagens_form.html')

@app.route('/admin/imagens/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_imagens_editar(id):
    imagem = Imagem.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            imagem.titulo = request.form.get('titulo')
            imagem.descricao = request.form.get('descricao')
            
            db.session.commit()
            flash('Imagem atualizada com sucesso!', 'success')
            return redirect(url_for('admin_imagens'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar imagem: {str(e)}', 'error')
    
    return render_template('admin/imagens_form.html', imagem=imagem)

@app.route('/admin/imagens/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_imagens_excluir(id):
    imagem = Imagem.query.get_or_404(id)
    try:
        # Remover arquivo físico se existir
        if imagem.caminho:
            filepath = os.path.join('static', imagem.caminho)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception as e:
                    print(f"Erro ao remover arquivo: {str(e)}")
        
        # Excluir do banco de dados
        db.session.delete(imagem)
        db.session.commit()
        flash('Imagem excluída com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir imagem: {str(e)}', 'error')
        import traceback
        traceback.print_exc()
    return redirect(url_for('admin_imagens'))

# ============================================
# CRUD - VÍDEOS
# ============================================

@app.route('/admin/videos')
@admin_required
def admin_videos():
    videos = Video.query.order_by(Video.ordem.desc(), Video.created_at.desc()).all()
    return render_template('admin/videos.html', videos=videos)

@app.route('/admin/videos/novo', methods=['GET', 'POST'])
@admin_required
def admin_videos_novo():
    if request.method == 'POST':
        try:
            ordem = request.form.get('ordem', 0)
            video = Video(
                titulo=request.form.get('titulo'),
                descricao=request.form.get('descricao'),
                url_youtube=request.form.get('url_youtube'),
                categoria=request.form.get('categoria'),
                ordem=int(ordem) if ordem else 0
            )
            db.session.add(video)
            db.session.commit()
            flash('Vídeo criado com sucesso!', 'success')
            return redirect(url_for('admin_videos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar vídeo: {str(e)}', 'error')
    
    return render_template('admin/videos_form.html')

@app.route('/admin/videos/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_videos_editar(id):
    video = Video.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            ordem = request.form.get('ordem', 0)
            video.titulo = request.form.get('titulo')
            video.descricao = request.form.get('descricao')
            video.url_youtube = request.form.get('url_youtube')
            video.categoria = request.form.get('categoria')
            video.ordem = int(ordem) if ordem else 0
            
            db.session.commit()
            flash('Vídeo atualizado com sucesso!', 'success')
            return redirect(url_for('admin_videos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar vídeo: {str(e)}', 'error')
    
    return render_template('admin/videos_form.html', video=video)

@app.route('/admin/videos/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_videos_excluir(id):
    video = Video.query.get_or_404(id)
    try:
        # Excluir do banco de dados
        db.session.delete(video)
        db.session.commit()
        flash('Vídeo excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir vídeo: {str(e)}', 'error')
        import traceback
        traceback.print_exc()
    return redirect(url_for('admin_videos'))

# ============================================
# GERENCIAMENTO DO RODAPÉ
# ============================================

@app.route('/admin/rodape', methods=['GET', 'POST'])
@admin_required
def admin_rodape():
    if request.method == 'POST':
        try:
            # Atualizar configurações do rodapé
            configs = {
                'footer_email': request.form.get('footer_email'),
                'footer_telefone': request.form.get('footer_telefone'),
                'footer_whatsapp': request.form.get('footer_whatsapp'),
                'footer_whatsapp_link': request.form.get('footer_whatsapp_link'),
                'footer_instagram': request.form.get('footer_instagram'),
                'footer_facebook': request.form.get('footer_facebook'),
                'footer_youtube': request.form.get('footer_youtube'),
                'footer_copyright_year': request.form.get('footer_copyright_year')
            }
            
            for chave, valor in configs.items():
                config = Configuracao.query.filter_by(chave=chave).first()
                if config:
                    config.valor = valor
                    config.updated_at = datetime.utcnow()
                else:
                    config = Configuracao(chave=chave, valor=valor, tipo='texto')
                    db.session.add(config)
            
            # Upload do QR Code se fornecido
            if 'qrcode_file' in request.files:
                file = request.files['qrcode_file']
                if file.filename != '':
                    if file and allowed_file(file.filename):
                        upload_folder = 'static/images'
                        os.makedirs(upload_folder, exist_ok=True)
                        
                        filename = secure_filename(file.filename)
                        # Salvar como qrcode.png
                        filepath = os.path.join(upload_folder, 'qrcode.png')
                        file.save(filepath)
                        
                        config = Configuracao.query.filter_by(chave='footer_qrcode').first()
                        if config:
                            config.valor = 'images/qrcode.png'
                            config.updated_at = datetime.utcnow()
                        else:
                            config = Configuracao(chave='footer_qrcode', valor='images/qrcode.png', tipo='imagem')
                            db.session.add(config)
            
            db.session.commit()
            flash('Configurações do rodapé atualizadas com sucesso!', 'success')
            return redirect(url_for('admin_rodape'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar configurações: {str(e)}', 'error')
    
    # Buscar todas as configurações
    configs = {}
    for config in Configuracao.query.filter(Configuracao.chave.like('footer_%')).all():
        configs[config.chave] = config.valor
    
    return render_template('admin/rodape.html', configs=configs)

# ============================================
# GERENCIAMENTO DOS DADOS DA ASSOCIAÇÃO
# ============================================

@app.route('/admin/dados-associacao', methods=['GET', 'POST'])
@admin_required
def admin_dados_associacao():
    """Gerencia os dados da associação (Nome, CNPJ, Endereço)"""
    dados = DadosAssociacao.get_dados()
    
    if request.method == 'POST':
        try:
            dados.nome = request.form.get('nome', '')
            dados.cnpj = request.form.get('cnpj', '')
            dados.endereco = request.form.get('endereco', '')
            dados.updated_at = datetime.utcnow()
            
            db.session.commit()
            flash('Dados da associação atualizados com sucesso!', 'success')
            return redirect(url_for('admin_dados_associacao'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar dados: {str(e)}', 'error')
    
    return render_template('admin/dados_associacao.html', dados=dados)

# ============================================
# GERENCIAMENTO "O QUE FAZEMOS"
# ============================================

@app.route('/admin/dados-associacao/o-que-fazemos')
@admin_required
def admin_o_que_fazemos():
    """Lista todos os serviços do módulo 'O que fazemos'"""
    servicos = OQueFazemosServico.query.order_by(OQueFazemosServico.coluna.asc(), OQueFazemosServico.ordem.asc()).all()
    return render_template('admin/o_que_fazemos.html', servicos=servicos)

@app.route('/admin/dados-associacao/o-que-fazemos/novo', methods=['GET', 'POST'])
@admin_required
def admin_o_que_fazemos_novo():
    """Cria um novo serviço"""
    if request.method == 'POST':
        try:
            titulo = request.form.get('titulo', '').strip()
            descricao = request.form.get('descricao', '').strip()
            cor_icone = request.form.get('cor_icone', '#3b82f6')
            icone_svg = request.form.get('icone_svg', '').strip()
            ordem = int(request.form.get('ordem', 0))
            coluna = int(request.form.get('coluna', 1))
            ativo = request.form.get('ativo') == 'on'
            
            if not titulo:
                flash('Título é obrigatório!', 'error')
                return redirect(url_for('admin_o_que_fazemos_novo'))
            
            if not descricao:
                flash('Descrição é obrigatória!', 'error')
                return redirect(url_for('admin_o_que_fazemos_novo'))
            
            if coluna not in [1, 2, 3]:
                coluna = 1
            
            servico = OQueFazemosServico(
                titulo=titulo,
                descricao=descricao,
                cor_icone=cor_icone,
                icone_svg=icone_svg,
                ordem=ordem,
                coluna=coluna,
                ativo=ativo
            )
            
            db.session.add(servico)
            db.session.commit()
            flash('Serviço criado com sucesso!', 'success')
            return redirect(url_for('admin_o_que_fazemos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar serviço: {str(e)}', 'error')
    
    return render_template('admin/o_que_fazemos_form.html', servico=None)

@app.route('/admin/dados-associacao/o-que-fazemos/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_o_que_fazemos_editar(id):
    """Edita um serviço existente"""
    servico = OQueFazemosServico.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            servico.titulo = request.form.get('titulo', '').strip()
            servico.descricao = request.form.get('descricao', '').strip()
            servico.cor_icone = request.form.get('cor_icone', '#3b82f6')
            servico.icone_svg = request.form.get('icone_svg', '').strip()
            servico.ordem = int(request.form.get('ordem', 0))
            servico.coluna = int(request.form.get('coluna', 1))
            servico.ativo = request.form.get('ativo') == 'on'
            servico.updated_at = datetime.utcnow()
            
            if not servico.titulo:
                flash('Título é obrigatório!', 'error')
                return redirect(url_for('admin_o_que_fazemos_editar', id=id))
            
            if not servico.descricao:
                flash('Descrição é obrigatória!', 'error')
                return redirect(url_for('admin_o_que_fazemos_editar', id=id))
            
            if servico.coluna not in [1, 2, 3]:
                servico.coluna = 1
            
            db.session.commit()
            flash('Serviço atualizado com sucesso!', 'success')
            return redirect(url_for('admin_o_que_fazemos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar serviço: {str(e)}', 'error')
    
    return render_template('admin/o_que_fazemos_form.html', servico=servico)

@app.route('/admin/dados-associacao/o-que-fazemos/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_o_que_fazemos_excluir(id):
    """Exclui um serviço"""
    servico = OQueFazemosServico.query.get_or_404(id)
    
    try:
        # Excluir do banco de dados
        db.session.delete(servico)
        db.session.commit()
        flash('Serviço excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir serviço: {str(e)}', 'error')
        import traceback
        traceback.print_exc()
    
    return redirect(url_for('admin_o_que_fazemos'))

# ============================================
# GERENCIAMENTO INSTAGRAM
# ============================================

@app.route('/admin/instagram')
@admin_required
def admin_instagram():
    """Lista todos os posts do Instagram"""
    posts = InstagramPost.query.order_by(InstagramPost.data_post.desc(), InstagramPost.ordem.asc()).all()
    return render_template('admin/instagram.html', posts=posts)

@app.route('/admin/instagram/novo', methods=['GET', 'POST'])
@admin_required
def admin_instagram_novo():
    """Cria um novo post do Instagram"""
    if request.method == 'POST':
        try:
            url_instagram = request.form.get('url_instagram', '').strip()
            imagem_url = request.form.get('imagem_url', '').strip()
            legenda = request.form.get('legenda', '').strip()
            data_post_str = request.form.get('data_post')
            ordem = int(request.form.get('ordem', 0))
            ativo = request.form.get('ativo') == 'on'
            
            if not imagem_url:
                flash('URL da imagem é obrigatória!', 'error')
                return redirect(url_for('admin_instagram_novo'))
            
            data_post = datetime.utcnow()
            if data_post_str:
                try:
                    data_post = datetime.strptime(data_post_str, '%Y-%m-%d')
                except:
                    pass
            
            post = InstagramPost(
                url_instagram=url_instagram if url_instagram else None,
                imagem_url=imagem_url,
                legenda=legenda if legenda else None,
                data_post=data_post,
                ordem=ordem,
                ativo=ativo
            )
            
            db.session.add(post)
            db.session.commit()
            flash('Post do Instagram criado com sucesso!', 'success')
            return redirect(url_for('admin_instagram'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar post: {str(e)}', 'error')
    
    return render_template('admin/instagram_form.html', post=None)

@app.route('/admin/instagram/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_instagram_editar(id):
    """Edita um post do Instagram existente"""
    post = InstagramPost.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            post.url_instagram = request.form.get('url_instagram', '').strip()
            post.imagem_url = request.form.get('imagem_url', '').strip()
            post.legenda = request.form.get('legenda', '').strip()
            data_post_str = request.form.get('data_post')
            post.ordem = int(request.form.get('ordem', 0))
            post.ativo = request.form.get('ativo') == 'on'
            post.updated_at = datetime.utcnow()
            
            if not post.imagem_url:
                flash('URL da imagem é obrigatória!', 'error')
                return redirect(url_for('admin_instagram_editar', id=id))
            
            if data_post_str:
                try:
                    post.data_post = datetime.strptime(data_post_str, '%Y-%m-%d')
                except:
                    pass
            
            db.session.commit()
            flash('Post do Instagram atualizado com sucesso!', 'success')
            return redirect(url_for('admin_instagram'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar post: {str(e)}', 'error')
    
    return render_template('admin/instagram_form.html', post=post)

@app.route('/admin/instagram/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_instagram_excluir(id):
    """Exclui um post do Instagram"""
    post = InstagramPost.query.get_or_404(id)
    
    try:
        db.session.delete(post)
        db.session.commit()
        flash('Post do Instagram excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir post: {str(e)}', 'error')
    
    return redirect(url_for('admin_instagram'))

@app.route('/admin/instagram/sincronizar', methods=['POST'])
@admin_required
def admin_instagram_sincronizar():
    """Sincroniza as últimas fotos do Instagram"""
    try:
        # Buscar URL do Instagram configurada
        footer_configs = {}
        for config in Configuracao.query.filter(Configuracao.chave.like('footer_%')).all():
            footer_configs[config.chave] = config.valor
        
        instagram_url = footer_configs.get('footer_instagram', '')
        
        if not instagram_url:
            flash('Configure a URL do Instagram no rodapé primeiro!', 'error')
            return redirect(url_for('admin_instagram'))
        
        # Extrair username da URL
        username_match = re.search(r'instagram\.com/([^/?]+)', instagram_url)
        if not username_match:
            flash('URL do Instagram inválida!', 'error')
            return redirect(url_for('admin_instagram'))
        
        username = username_match.group(1)
        
        # Buscar posts do Instagram (isso já baixa as imagens localmente)
        posts_cadastrados = buscar_posts_instagram(username, instagram_url)
        
        if posts_cadastrados:
            flash(f'{posts_cadastrados} posts sincronizados e imagens baixadas com sucesso!', 'success')
        else:
            flash('Nenhum post encontrado. Tente adicionar posts manualmente ou verifique se o perfil é público.', 'warning')
        
    except Exception as e:
        error_msg = str(e)
        # Mensagens de erro mais amigáveis
        if '404' in error_msg or 'não encontrado' in error_msg.lower():
            flash(f'Perfil não encontrado: {error_msg}. Verifique se a URL do Instagram está correta no rodapé.', 'error')
        elif '403' in error_msg or 'negado' in error_msg.lower() or 'privado' in error_msg.lower():
            flash(f'Acesso negado: {error_msg}. O perfil pode ser privado. Tente adicionar posts manualmente.', 'error')
        elif 'conexão' in error_msg.lower() or 'connection' in error_msg.lower():
            flash(f'Erro de conexão: {error_msg}. Verifique sua conexão com a internet.', 'error')
        else:
            flash(f'Erro ao sincronizar: {error_msg}. O Instagram pode estar bloqueando requisições automáticas. Tente adicionar posts manualmente.', 'error')
    
    return redirect(url_for('admin_instagram'))

def baixar_e_salvar_imagem_instagram(url_imagem, shortcode):
    """Baixa uma imagem do Instagram e salva localmente"""
    try:
        if not shortcode or not url_imagem:
            return url_imagem
        
        # Criar diretório para imagens do Instagram se não existir
        instagram_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'instagram')
        os.makedirs(instagram_dir, exist_ok=True)
        
        # Nome do arquivo usando o shortcode do post
        # Limpar o shortcode para usar como nome de arquivo
        shortcode_clean = re.sub(r'[^\w\-]', '_', shortcode)
        filename = f"instagram_{shortcode_clean}.jpg"
        filepath = os.path.join(instagram_dir, filename)
        
        # Se o arquivo já existe, retornar o caminho relativo (mesmo formato usado no template)
        if os.path.exists(filepath):
            # Retornar caminho no formato: images/uploads/instagram/filename.jpg
            return os.path.join('images', 'uploads', 'instagram', filename).replace('\\', '/')
        
        # Headers para baixar a imagem
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://www.instagram.com/',
            'Origin': 'https://www.instagram.com'
        }
        
        # Baixar a imagem
        response = requests.get(url_imagem, headers=headers, timeout=20, verify=False, stream=True)
        if response.status_code == 200:
            # Determinar a extensão correta do arquivo pelo Content-Type
            content_type = response.headers.get('Content-Type', '')
            if 'webp' in content_type:
                filename = filename.replace('.jpg', '.webp')
                filepath = os.path.join(instagram_dir, filename)
            elif 'png' in content_type:
                filename = filename.replace('.jpg', '.png')
                filepath = os.path.join(instagram_dir, filename)
            
            # Salvar a imagem
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            print(f"[Instagram] Imagem salva localmente: {filename}")
            # Retornar o caminho relativo no formato usado no template
            return os.path.join('images', 'uploads', 'instagram', filename).replace('\\', '/')
        else:
            print(f"[Instagram] Erro ao baixar imagem: {response.status_code} - {url_imagem[:50]}...")
            # Se não conseguir baixar, retornar a URL original
            return url_imagem
    except Exception as e:
        print(f"[Instagram] Erro ao baixar e salvar imagem {shortcode}: {str(e)}")
        # Se houver erro, retornar a URL original
        return url_imagem

def buscar_posts_instagram(username, instagram_url_base):
    """Busca as últimas fotos do Instagram e atualiza o banco de dados"""
    posts_data = []
    error_messages = []
    
    try:
        # URL do perfil público do Instagram
        profile_url = f"https://www.instagram.com/{username}/"
        
        # Headers mais completos para simular um navegador real
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
        }
        
        # Fazer requisição com verificação de SSL
        try:
            response = requests.get(profile_url, headers=headers, timeout=15, verify=True)
        except requests.exceptions.SSLError:
            # Tentar sem verificação SSL se houver problema
            response = requests.get(profile_url, headers=headers, timeout=15, verify=False)
        except requests.exceptions.RequestException as e:
            raise Exception(f'Erro de conexão: {str(e)}')
        
        if response.status_code == 404:
            raise Exception(f'Perfil @{username} não encontrado. Verifique se o nome do perfil está correto.')
        elif response.status_code == 403:
            raise Exception('Acesso negado pelo Instagram. O perfil pode ser privado ou o Instagram está bloqueando requisições.')
        elif response.status_code != 200:
            raise Exception(f'Erro ao acessar perfil do Instagram (código: {response.status_code})')
        
        # Verificar se a resposta contém conteúdo válido
        if not response.text or len(response.text) < 1000:
            raise Exception('Resposta do Instagram vazia ou inválida.')
        
        # Parsear HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # MÉTODO 1: Procurar por scripts com window._sharedData ou dados JSON
        scripts = soup.find_all('script')
        posts_data = []
        import json
        
        for script in scripts:
            if not script.string:
                continue
            script_text = script.string
            
            # Tentar múltiplos padrões de JSON
            patterns = [
                r'window\._sharedData\s*=\s*({.+?});',
                r'<script[^>]*>({.+?})</script>',
                r'"ProfilePage":\s*\[({.+?})\]',
                r'<script type="application/json"[^>]*>({.+?})</script>',
            ]
            
            for pattern in patterns:
                matches = re.finditer(pattern, script_text, re.DOTALL)
                for match in matches:
                    try:
                        json_str = match.group(1)
                        # Limpar o JSON se necessário
                        json_str = json_str.strip()
                        if not json_str.startswith('{'):
                            continue
                        data = json.loads(json_str)
                        
                        # Tentar diferentes caminhos na estrutura JSON
                        user_data = None
                        if 'entry_data' in data and 'ProfilePage' in data['entry_data']:
                            if len(data['entry_data']['ProfilePage']) > 0:
                                user_data = data['entry_data']['ProfilePage'][0]
                        elif 'graphql' in data and 'user' in data['graphql']:
                            user_data = {'graphql': {'user': data['graphql']['user']}}
                        elif 'user' in data:
                            user_data = {'graphql': {'user': data['user']}}
                        
                        if user_data and 'graphql' in user_data and 'user' in user_data['graphql']:
                            user = user_data['graphql']['user']
                            if 'edge_owner_to_timeline_media' in user:
                                edges = user['edge_owner_to_timeline_media'].get('edges', [])
                                for edge in edges[:6]:
                                    node = edge.get('node', {})
                                    if not node.get('is_video', False):
                                        display_url = node.get('display_url', '') or node.get('thumbnail_src', '')
                                        if display_url:
                                            post_data = {
                                                'shortcode': node.get('shortcode', ''),
                                                'display_url': display_url,
                                                'caption': '',
                                                'taken_at_timestamp': node.get('taken_at_timestamp', 0),
                                                'is_video': False
                                            }
                                            # Tentar pegar a legenda
                                            if 'edge_media_to_caption' in node:
                                                caption_edges = node['edge_media_to_caption'].get('edges', [])
                                                if caption_edges and len(caption_edges) > 0:
                                                    post_data['caption'] = caption_edges[0].get('node', {}).get('text', '')
                                            
                                            posts_data.append(post_data)
                                if posts_data:
                                    break
                    except (json.JSONDecodeError, KeyError, TypeError) as e:
                        continue
                if posts_data:
                    break
            if posts_data:
                break
        
        # Método 3: Buscar links e imagens diretamente no HTML (scraping direto)
        if not posts_data:
            try:
                # Buscar todos os links que apontam para posts
                links = soup.find_all('a', href=re.compile(r'/p/'))
                seen_codes = set()
                
                for link in links:
                    if len(posts_data) >= 6:
                        break
                    href = link.get('href', '')
                    code_match = re.search(r'/p/([^/?#]+)', href)
                    if code_match:
                        shortcode = code_match.group(1)
                        if shortcode and shortcode not in seen_codes:
                            seen_codes.add(shortcode)
                            # Buscar imagem dentro do link ou próxima ao link
                            img = link.find('img')
                            if not img:
                                # Tentar encontrar imagem irmã ou pai
                                parent = link.find_parent()
                                if parent:
                                    img = parent.find('img')
                            
                            if img:
                                # Tentar múltiplos atributos para URL da imagem
                                img_url = (img.get('src') or 
                                          img.get('data-src') or 
                                          img.get('data-lazy-src') or 
                                          img.get('data-original') or
                                          img.get('data-srcset', '').split(',')[0].split(' ')[0] if img.get('data-srcset') else None)
                                
                                if img_url:
                                    # Normalizar URL
                                    if not img_url.startswith('http'):
                                        if img_url.startswith('//'):
                                            img_url = 'https:' + img_url
                                        elif img_url.startswith('/'):
                                            img_url = 'https://www.instagram.com' + img_url
                                        else:
                                            img_url = 'https://www.instagram.com/' + img_url
                                    
                                    # Verificar se é uma URL válida do Instagram
                                    if any(domain in img_url for domain in ['instagram.com', 'scontent', 'cdninstagram', 'fbcdn']):
                                        alt_text = img.get('alt', '') or img.get('title', '')
                                        posts_data.append({
                                            'shortcode': shortcode,
                                            'display_url': img_url,
                                            'caption': alt_text[:500] if alt_text else '',
                                            'taken_at_timestamp': 0,
                                            'is_video': False
                                        })
            except Exception as alt_error:
                error_messages.append(f'Erro no método alternativo: {str(alt_error)}')
        
        # Método 4: Tentar usar API GraphQL do Instagram (método mais confiável) - PRIORIDADE ALTA
        try:
            # Usar endpoint GraphQL do Instagram com headers atualizados
            api_url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
            api_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'Accept': '*/*',
                'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'X-Requested-With': 'XMLHttpRequest',
                'X-IG-App-ID': '936619743392459',
                'X-IG-WWW-Claim': '0',
                'Referer': f'https://www.instagram.com/{username}/',
                'Origin': 'https://www.instagram.com',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'Connection': 'keep-alive'
            }
            
            api_response = requests.get(api_url, headers=api_headers, timeout=20, verify=False, allow_redirects=True)
            if api_response.status_code == 200:
                import json
                try:
                    api_data = api_response.json()
                    if 'data' in api_data and 'user' in api_data['data']:
                        user = api_data['data']['user']
                        if 'edge_owner_to_timeline_media' in user:
                            edges = user['edge_owner_to_timeline_media'].get('edges', [])
                            for edge in edges[:12]:  # Buscar mais para ter opções
                                node = edge.get('node', {})
                                if not node.get('is_video', False):
                                    display_url = node.get('display_url', '')
                                    if not display_url:
                                        display_url = node.get('thumbnail_src', '')
                                    if not display_url and 'thumbnail_resources' in node:
                                        thumbnails = node.get('thumbnail_resources', [])
                                        if thumbnails:
                                            display_url = thumbnails[-1].get('src', '')
                                    if display_url:
                                        shortcode = node.get('shortcode', '')
                                        caption = ''
                                        if 'edge_media_to_caption' in node:
                                            caption_edges = node['edge_media_to_caption'].get('edges', [])
                                            if caption_edges:
                                                caption = caption_edges[0].get('node', {}).get('text', '')
                                        posts_data.append({
                                            'shortcode': shortcode,
                                            'display_url': display_url,
                                            'caption': caption,
                                            'taken_at_timestamp': node.get('taken_at_timestamp', 0),
                                            'is_video': False
                                        })
                    if posts_data:
                        # Limitar a 6 posts
                        posts_data = posts_data[:6]
                except (json.JSONDecodeError, KeyError) as e:
                    error_messages.append(f'Erro ao parsear JSON da API: {str(e)[:50]}')
        except Exception as api_error:
            error_messages.append(f'API não disponível: {str(api_error)[:50]}')
        
        # Método 4.5: Buscar JSON diretamente do HTML com padrão mais recente
        if not posts_data:
            try:
                # Procurar por script type="application/json"
                json_scripts = soup.find_all('script', type='application/json')
                for script in json_scripts:
                    try:
                        import json
                        data = json.loads(script.string)
                        # Tentar diferentes caminhos
                        if 'entry_data' in data:
                            if 'ProfilePage' in data['entry_data']:
                                for page in data['entry_data']['ProfilePage']:
                                    if 'graphql' in page and 'user' in page['graphql']:
                                        user = page['graphql']['user']
                                        if 'edge_owner_to_timeline_media' in user:
                                            edges = user['edge_owner_to_timeline_media'].get('edges', [])
                                            for edge in edges[:6]:
                                                node = edge.get('node', {})
                                                if not node.get('is_video', False):
                                                    display_url = node.get('display_url', '') or node.get('thumbnail_src', '')
                                                    if display_url:
                                                        posts_data.append({
                                                            'shortcode': node.get('shortcode', ''),
                                                            'display_url': display_url,
                                                            'caption': node.get('edge_media_to_caption', {}).get('edges', [{}])[0].get('node', {}).get('text', '') if node.get('edge_media_to_caption', {}).get('edges') else '',
                                                            'taken_at_timestamp': node.get('taken_at_timestamp', 0),
                                                            'is_video': False
                                                        })
                                            if posts_data:
                                                break
                    except (json.JSONDecodeError, KeyError, AttributeError):
                        continue
                    if posts_data:
                        break
            except Exception as e:
                error_messages.append(f'Erro no método JSON direto: {str(e)[:50]}')
        
        # Atualizar banco de dados
        posts_cadastrados = 0
        for post_data in posts_data[:6]:
            # Verificar se o post já existe
            url_instagram = f"{instagram_url_base.rstrip('/')}/p/{post_data['shortcode']}/"
            existing_post = InstagramPost.query.filter_by(url_instagram=url_instagram).first()
            
            # Baixar e salvar imagem localmente
            shortcode = post_data.get('shortcode', '')
            display_url = post_data.get('display_url', '')
            
            # Verificar se o post existente já tem imagem local válida
            imagem_existente_local = False
            imagem_url = display_url  # Usar a URL da busca por padrão
            
            if existing_post and existing_post.imagem_url:
                # Se a imagem já é local, verificar se o arquivo existe
                if existing_post.imagem_url.startswith('images/'):
                    # Verificar se o arquivo realmente existe no disco
                    caminho_arquivo = os.path.join('static', existing_post.imagem_url)
                    if os.path.exists(caminho_arquivo):
                        # Arquivo existe, usar a imagem local
                        imagem_existente_local = True
                        imagem_url = existing_post.imagem_url
                    else:
                        # Arquivo não existe, tentar baixar novamente
                        imagem_existente_local = False
                        print(f"[Instagram] Imagem local não encontrada no disco: {existing_post.imagem_url}, tentando baixar novamente")
                else:
                    # Se a imagem não é local, tentar baixar
                    imagem_existente_local = False
            
            # Tentar baixar a imagem e salvar localmente (só se não for local válida ou se for novo post)
            if not imagem_existente_local and display_url and shortcode:
                try:
                    imagem_local = baixar_e_salvar_imagem_instagram(display_url, shortcode)
                    # Se a imagem foi baixada com sucesso, usar o caminho local
                    if imagem_local and not imagem_local.startswith('http'):
                        imagem_url = imagem_local
                        print(f"[Instagram] Imagem local salva para post {shortcode}: {imagem_url}")
                    else:
                        # Se falhou, usar a URL original (pode expirar)
                        imagem_url = display_url
                        print(f"[Instagram] Não foi possível baixar imagem local para post {shortcode}, usando URL original")
                except Exception as img_error:
                    print(f"[Instagram] Erro ao baixar imagem do post {shortcode}: {str(img_error)}")
                    # Se falhar, usar a URL original ou manter a existente
                    if not existing_post:
                        imagem_url = display_url
                    else:
                        # Manter a URL existente se não conseguir baixar
                        imagem_url = existing_post.imagem_url
            
            if not existing_post:
                # Criar novo post
                data_post = datetime.utcnow()
                if post_data['taken_at_timestamp']:
                    data_post = datetime.fromtimestamp(post_data['taken_at_timestamp'])
                
                new_post = InstagramPost(
                    url_instagram=url_instagram,
                    imagem_url=imagem_url,
                    legenda=post_data['caption'][:500] if post_data['caption'] else None,  # Limitar tamanho
                    data_post=data_post,
                    ordem=0,
                    ativo=True
                )
                db.session.add(new_post)
                posts_cadastrados += 1
            else:
                # Atualizar post existente
                # Sempre atualizar a imagem se for local ou se a URL mudou
                if imagem_url != existing_post.imagem_url:
                    existing_post.imagem_url = imagem_url
                if post_data['caption']:
                    existing_post.legenda = post_data['caption'][:500]
                if post_data['taken_at_timestamp']:
                    existing_post.data_post = datetime.fromtimestamp(post_data['taken_at_timestamp'])
                existing_post.ativo = True
                existing_post.updated_at = datetime.utcnow()
        
        try:
            db.session.commit()
        except Exception as commit_error:
            db.session.rollback()
            print(f"[Instagram] Erro ao fazer commit: {str(commit_error)}")
            # Tentar buscar posts existentes mesmo se o commit falhou
            posts_existentes = InstagramPost.query.filter_by(ativo=True).limit(6).count()
            if posts_existentes > 0:
                # Se houver posts existentes, retornar sucesso parcial
                return posts_existentes
            raise Exception(f'Erro ao salvar posts: {str(commit_error)}')
        
        if posts_cadastrados > 0:
            return posts_cadastrados
        elif posts_data:
            # Posts encontrados mas nenhum foi cadastrado (provavelmente já existiam e foram atualizados)
            return len(posts_data)
        else:
            # Nenhum post encontrado - verificar se há posts existentes no banco
            posts_existentes = InstagramPost.query.filter_by(ativo=True).limit(6).count()
            if posts_existentes > 0:
                # Se houver posts existentes, retornar sucesso parcial (não atualizou, mas há posts)
                print(f"[Instagram] Nenhum novo post encontrado, mas há {posts_existentes} posts existentes no banco.")
                return posts_existentes
            # Nenhum post encontrado e nenhum post existente
            if error_messages:
                raise Exception('; '.join(error_messages))
            else:
                raise Exception('Nenhum post encontrado. O perfil pode não ter posts públicos ou o Instagram mudou sua estrutura.')
        
    except Exception as e:
        db.session.rollback()
        # Verificar se há posts existentes antes de lançar exceção
        try:
            posts_existentes = InstagramPost.query.filter_by(ativo=True).limit(6).count()
            if posts_existentes > 0:
                # Se houver posts existentes, retornar sucesso parcial (não atualizou, mas há posts)
                print(f"[Instagram] Erro ao buscar novos posts: {str(e)}, mas há {posts_existentes} posts existentes no banco.")
                return posts_existentes
        except:
            pass
        # Re-raise a exceção com mensagem mais clara
        raise Exception(str(e))

# ============================================
# GERENCIAMENTO DA PÁGINA SOBRE
# ============================================

@app.route('/admin/sobre')
@admin_required
def admin_sobre():
    # Buscar conteúdos
    quem_somos = SobreConteudo.query.filter_by(chave='quem_somos').first()
    missao = SobreConteudo.query.filter_by(chave='missao').first()
    valores = SobreConteudo.query.filter_by(chave='valores').first()
    
    # Buscar membros
    membros_diretoria = MembroDiretoria.query.order_by(MembroDiretoria.ordem.asc()).all()
    membros_conselho = MembroConselhoFiscal.query.order_by(MembroConselhoFiscal.ordem.asc()).all()
    
    return render_template('admin/sobre.html',
                         quem_somos=quem_somos,
                         missao=missao,
                         valores=valores,
                         membros_diretoria=membros_diretoria,
                         membros_conselho=membros_conselho)

@app.route('/admin/sobre/conteudo', methods=['POST'])
@admin_required
def admin_sobre_conteudo():
    chave = request.form.get('chave')
    conteudo_pt = request.form.get('conteudo_pt', '')
    conteudo_es = request.form.get('conteudo_es', '')
    conteudo_en = request.form.get('conteudo_en', '')
    
    if not chave:
        flash('Chave inválida!', 'error')
        return redirect(url_for('admin_sobre'))
    
    try:
        conteudo = SobreConteudo.query.filter_by(chave=chave).first()
        if conteudo:
            conteudo.conteudo_pt = conteudo_pt
            conteudo.conteudo_es = conteudo_es
            conteudo.conteudo_en = conteudo_en
            conteudo.updated_at = datetime.utcnow()
        else:
            conteudo = SobreConteudo(
                chave=chave,
                conteudo_pt=conteudo_pt,
                conteudo_es=conteudo_es,
                conteudo_en=conteudo_en
            )
            db.session.add(conteudo)
        
        db.session.commit()
        flash('Conteúdo atualizado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao atualizar conteúdo: {str(e)}', 'error')
    
    return redirect(url_for('admin_sobre'))

@app.route('/admin/sobre/diretoria/novo', methods=['GET', 'POST'])
@admin_required
def admin_sobre_diretoria_novo():
    if request.method == 'POST':
        try:
            cargo = request.form.get('cargo')
            nome_pt = request.form.get('nome_pt')
            nome_es = request.form.get('nome_es', '')
            nome_en = request.form.get('nome_en', '')
            ordem = int(request.form.get('ordem', 0))
            
            if not cargo or not nome_pt:
                flash('Cargo e nome são obrigatórios!', 'error')
                return redirect(url_for('admin_sobre_diretoria_novo'))
            
            # Upload da foto
            foto_path = None
            if 'foto' in request.files:
                file = request.files['foto']
                if file.filename != '':
                    if file and allowed_file(file.filename):
                        upload_folder = 'static/images/diretoria'
                        os.makedirs(upload_folder, exist_ok=True)
                        
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        filepath = os.path.join(upload_folder, unique_filename)
                        file.save(filepath)
                        foto_path = f"images/diretoria/{unique_filename}"
            
            membro = MembroDiretoria(
                cargo=cargo,
                nome_pt=nome_pt,
                nome_es=nome_es,
                nome_en=nome_en,
                foto=foto_path,
                ordem=ordem
            )
            db.session.add(membro)
            db.session.commit()
            flash('Membro da diretoria cadastrado com sucesso!', 'success')
            return redirect(url_for('admin_sobre'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar membro: {str(e)}', 'error')
    
    return render_template('admin/sobre_diretoria_form.html')

@app.route('/admin/sobre/diretoria/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_sobre_diretoria_editar(id):
    membro = MembroDiretoria.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            membro.cargo = request.form.get('cargo')
            membro.nome_pt = request.form.get('nome_pt')
            membro.nome_es = request.form.get('nome_es', '')
            membro.nome_en = request.form.get('nome_en', '')
            membro.ordem = int(request.form.get('ordem', 0))
            
            # Upload da foto se fornecida
            if 'foto' in request.files:
                file = request.files['foto']
                if file.filename != '':
                    if file and allowed_file(file.filename):
                        upload_folder = 'static/images/diretoria'
                        os.makedirs(upload_folder, exist_ok=True)
                        
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        filepath = os.path.join(upload_folder, unique_filename)
                        file.save(filepath)
                        membro.foto = f"images/diretoria/{unique_filename}"
            
            membro.updated_at = datetime.utcnow()
            db.session.commit()
            flash('Membro da diretoria atualizado com sucesso!', 'success')
            return redirect(url_for('admin_sobre'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar membro: {str(e)}', 'error')
    
    return render_template('admin/sobre_diretoria_form.html', membro=membro)

@app.route('/admin/sobre/diretoria/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_sobre_diretoria_excluir(id):
    membro = MembroDiretoria.query.get_or_404(id)
    try:
        db.session.delete(membro)
        db.session.commit()
        flash('Membro da diretoria excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir membro: {str(e)}', 'error')
    return redirect(url_for('admin_sobre'))

@app.route('/admin/sobre/conselho/novo', methods=['GET', 'POST'])
@admin_required
def admin_sobre_conselho_novo():
    if request.method == 'POST':
        try:
            nome_pt = request.form.get('nome_pt')
            nome_es = request.form.get('nome_es', '')
            nome_en = request.form.get('nome_en', '')
            ordem = int(request.form.get('ordem', 0))
            
            if not nome_pt:
                flash('Nome é obrigatório!', 'error')
                return redirect(url_for('admin_sobre_conselho_novo'))
            
            # Upload da foto
            foto_path = None
            if 'foto' in request.files:
                file = request.files['foto']
                if file.filename != '':
                    if file and allowed_file(file.filename):
                        upload_folder = 'static/images/diretoria'
                        os.makedirs(upload_folder, exist_ok=True)
                        
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        filepath = os.path.join(upload_folder, unique_filename)
                        file.save(filepath)
                        foto_path = f"images/diretoria/{unique_filename}"
            
            membro = MembroConselhoFiscal(
                nome_pt=nome_pt,
                nome_es=nome_es,
                nome_en=nome_en,
                foto=foto_path,
                ordem=ordem
            )
            db.session.add(membro)
            db.session.commit()
            flash('Membro do conselho fiscal cadastrado com sucesso!', 'success')
            return redirect(url_for('admin_sobre'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar membro: {str(e)}', 'error')
    
    return render_template('admin/sobre_conselho_form.html')

@app.route('/admin/sobre/conselho/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_sobre_conselho_editar(id):
    membro = MembroConselhoFiscal.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            membro.nome_pt = request.form.get('nome_pt')
            membro.nome_es = request.form.get('nome_es', '')
            membro.nome_en = request.form.get('nome_en', '')
            membro.ordem = int(request.form.get('ordem', 0))
            
            # Upload da foto se fornecida
            if 'foto' in request.files:
                file = request.files['foto']
                if file.filename != '':
                    if file and allowed_file(file.filename):
                        upload_folder = 'static/images/diretoria'
                        os.makedirs(upload_folder, exist_ok=True)
                        
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        filepath = os.path.join(upload_folder, unique_filename)
                        file.save(filepath)
                        membro.foto = f"images/diretoria/{unique_filename}"
            
            membro.updated_at = datetime.utcnow()
            db.session.commit()
            flash('Membro do conselho fiscal atualizado com sucesso!', 'success')
            return redirect(url_for('admin_sobre'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar membro: {str(e)}', 'error')
    
    return render_template('admin/sobre_conselho_form.html', membro=membro)

@app.route('/admin/sobre/conselho/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_sobre_conselho_excluir(id):
    membro = MembroConselhoFiscal.query.get_or_404(id)
    try:
        db.session.delete(membro)
        db.session.commit()
        flash('Membro do conselho fiscal excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir membro: {str(e)}', 'error')
    return redirect(url_for('admin_sobre'))

# ============================================
# GERENCIAMENTO DA COORDENAÇÃO SOCIAL
# ============================================

@app.route('/admin/sobre/coordenacao/novo', methods=['GET', 'POST'])
@admin_required
def admin_sobre_coordenacao_novo():
    if request.method == 'POST':
        try:
            cargo = request.form.get('cargo', '').strip()
            nome_pt = request.form.get('nome_pt', '').strip()
            nome_es = request.form.get('nome_es', '')
            nome_en = request.form.get('nome_en', '')
            ordem = int(request.form.get('ordem', 0))
            
            if not cargo:
                flash('Cargo é obrigatório!', 'error')
                return redirect(url_for('admin_sobre_coordenacao_novo'))
            
            if not nome_pt:
                flash('Nome é obrigatório!', 'error')
                return redirect(url_for('admin_sobre_coordenacao_novo'))
            
            # Upload da foto
            foto_path = None
            if 'foto' in request.files:
                file = request.files['foto']
                if file.filename != '':
                    if file and allowed_file(file.filename):
                        upload_folder = 'static/images/diretoria'
                        os.makedirs(upload_folder, exist_ok=True)
                        
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        filepath = os.path.join(upload_folder, unique_filename)
                        file.save(filepath)
                        foto_path = f"images/diretoria/{unique_filename}"
            
            membro = MembroCoordenacaoSocial(
                cargo=cargo,
                nome_pt=nome_pt,
                nome_es=nome_es,
                nome_en=nome_en,
                foto=foto_path,
                ordem=ordem
            )
            db.session.add(membro)
            db.session.commit()
            flash('Coordenador(a) cadastrado(a) com sucesso!', 'success')
            return redirect(url_for('admin_sobre'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar membro: {str(e)}', 'error')
    
    return render_template('admin/sobre_coordenacao_form.html')

@app.route('/admin/sobre/coordenacao/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_sobre_coordenacao_editar(id):
    membro = MembroCoordenacaoSocial.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            membro.cargo = request.form.get('cargo', '').strip()
            membro.nome_pt = request.form.get('nome_pt')
            membro.nome_es = request.form.get('nome_es', '')
            membro.nome_en = request.form.get('nome_en', '')
            membro.ordem = int(request.form.get('ordem', 0))
            
            if not membro.cargo:
                flash('Cargo é obrigatório!', 'error')
                return redirect(url_for('admin_sobre_coordenacao_editar', id=id))
            
            # Upload da foto se fornecida
            if 'foto' in request.files:
                file = request.files['foto']
                if file.filename != '':
                    if file and allowed_file(file.filename):
                        upload_folder = 'static/images/diretoria'
                        os.makedirs(upload_folder, exist_ok=True)
                        
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        filepath = os.path.join(upload_folder, unique_filename)
                        file.save(filepath)
                        membro.foto = f"images/diretoria/{unique_filename}"
            
            membro.updated_at = datetime.utcnow()
            db.session.commit()
            flash('Coordenador(a) atualizado(a) com sucesso!', 'success')
            return redirect(url_for('admin_sobre'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar membro: {str(e)}', 'error')
    
    return render_template('admin/sobre_coordenacao_form.html', membro=membro)

@app.route('/admin/sobre/coordenacao/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_sobre_coordenacao_excluir(id):
    membro = MembroCoordenacaoSocial.query.get_or_404(id)
    try:
        db.session.delete(membro)
        db.session.commit()
        flash('Coordenador(a) excluído(a) com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir membro: {str(e)}', 'error')
    return redirect(url_for('admin_sobre'))

# ============================================
# GERENCIAMENTO DA PÁGINA TRANSPARÊNCIA
# ============================================

@app.route('/admin/transparencia')
@admin_required
def admin_transparencia():
    # Buscar todos os itens
    relatorios = RelatorioFinanceiro.query.order_by(RelatorioFinanceiro.ordem.asc(), RelatorioFinanceiro.data_relatorio.desc()).all()
    documentos = EstatutoDocumento.query.order_by(EstatutoDocumento.ordem.asc(), EstatutoDocumento.data_documento.desc()).all()
    prestacoes = PrestacaoConta.query.order_by(PrestacaoConta.ordem.asc(), PrestacaoConta.periodo_inicio.desc()).all()
    informacoes_doacao = InformacaoDoacao.query.order_by(InformacaoDoacao.ordem.asc()).all()
    
    return render_template('admin/transparencia.html',
                         relatorios=relatorios,
                         documentos=documentos,
                         prestacoes=prestacoes,
                         informacoes_doacao=informacoes_doacao)

# ============================================
# CRUD - RELATÓRIOS FINANCEIROS
# ============================================

@app.route('/admin/transparencia/relatorio/novo', methods=['GET', 'POST'])
@admin_required
def admin_relatorio_novo():
    if request.method == 'POST':
        try:
            titulo_pt = request.form.get('titulo_pt')
            titulo_es = request.form.get('titulo_es', '')
            titulo_en = request.form.get('titulo_en', '')
            descricao_pt = request.form.get('descricao_pt', '')
            descricao_es = request.form.get('descricao_es', '')
            descricao_en = request.form.get('descricao_en', '')
            tipo = request.form.get('tipo', 'relatorio')
            ordem = int(request.form.get('ordem', 0))
            data_relatorio_str = request.form.get('data_relatorio')
            data_relatorio = datetime.strptime(data_relatorio_str, '%Y-%m-%d').date() if data_relatorio_str else None
            
            if not titulo_pt:
                flash('Título em português é obrigatório!', 'error')
                return redirect(url_for('admin_relatorio_novo'))
            
            # Upload do arquivo
            arquivo_path = None
            if 'arquivo' in request.files:
                file = request.files['arquivo']
                if file.filename != '':
                    if file and allowed_document_file(file.filename):
                        upload_folder = 'static/documents/transparencia'
                        os.makedirs(upload_folder, exist_ok=True)
                        
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        filepath = os.path.join(upload_folder, unique_filename)
                        file.save(filepath)
                        arquivo_path = f"documents/transparencia/{unique_filename}"
            
            relatorio = RelatorioFinanceiro(
                titulo_pt=titulo_pt,
                titulo_es=titulo_es,
                titulo_en=titulo_en,
                descricao_pt=descricao_pt,
                descricao_es=descricao_es,
                descricao_en=descricao_en,
                tipo=tipo,
                ordem=ordem,
                data_relatorio=data_relatorio,
                arquivo=arquivo_path
            )
            db.session.add(relatorio)
            db.session.commit()
            flash('Relatório financeiro cadastrado com sucesso!', 'success')
            return redirect(url_for('admin_transparencia'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar relatório: {str(e)}', 'error')
    
    return render_template('admin/relatorio_form.html')

@app.route('/admin/transparencia/relatorio/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_relatorio_editar(id):
    relatorio = RelatorioFinanceiro.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            relatorio.titulo_pt = request.form.get('titulo_pt')
            relatorio.titulo_es = request.form.get('titulo_es', '')
            relatorio.titulo_en = request.form.get('titulo_en', '')
            relatorio.descricao_pt = request.form.get('descricao_pt', '')
            relatorio.descricao_es = request.form.get('descricao_es', '')
            relatorio.descricao_en = request.form.get('descricao_en', '')
            relatorio.tipo = request.form.get('tipo', 'relatorio')
            relatorio.ordem = int(request.form.get('ordem', 0))
            data_relatorio_str = request.form.get('data_relatorio')
            relatorio.data_relatorio = datetime.strptime(data_relatorio_str, '%Y-%m-%d').date() if data_relatorio_str else None
            
            # Upload do arquivo se fornecido
            if 'arquivo' in request.files:
                file = request.files['arquivo']
                if file.filename != '':
                    if file and allowed_file(file.filename):
                        upload_folder = 'static/documents/transparencia'
                        os.makedirs(upload_folder, exist_ok=True)
                        
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        filepath = os.path.join(upload_folder, unique_filename)
                        file.save(filepath)
                        relatorio.arquivo = f"documents/transparencia/{unique_filename}"
            
            relatorio.updated_at = datetime.utcnow()
            db.session.commit()
            flash('Relatório financeiro atualizado com sucesso!', 'success')
            return redirect(url_for('admin_transparencia'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar relatório: {str(e)}', 'error')
    
    return render_template('admin/relatorio_form.html', relatorio=relatorio)

@app.route('/admin/transparencia/relatorio/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_relatorio_excluir(id):
    relatorio = RelatorioFinanceiro.query.get_or_404(id)
    try:
        db.session.delete(relatorio)
        db.session.commit()
        flash('Relatório financeiro excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir relatório: {str(e)}', 'error')
    return redirect(url_for('admin_transparencia'))

# ============================================
# CRUD - ESTATUTO E DOCUMENTOS
# ============================================

@app.route('/admin/transparencia/documento/novo', methods=['GET', 'POST'])
@admin_required
def admin_documento_novo():
    if request.method == 'POST':
        try:
            titulo_pt = request.form.get('titulo_pt')
            titulo_es = request.form.get('titulo_es', '')
            titulo_en = request.form.get('titulo_en', '')
            descricao_pt = request.form.get('descricao_pt', '')
            descricao_es = request.form.get('descricao_es', '')
            descricao_en = request.form.get('descricao_en', '')
            tipo = request.form.get('tipo', 'documento')
            ordem = int(request.form.get('ordem', 0))
            data_documento_str = request.form.get('data_documento')
            data_documento = datetime.strptime(data_documento_str, '%Y-%m-%d').date() if data_documento_str else None
            
            if not titulo_pt:
                flash('Título em português é obrigatório!', 'error')
                return redirect(url_for('admin_documento_novo'))
            
            # Upload do arquivo
            arquivo_path = None
            if 'arquivo' in request.files:
                file = request.files['arquivo']
                if file.filename != '':
                    if file and allowed_document_file(file.filename):
                        upload_folder = 'static/documents/transparencia'
                        os.makedirs(upload_folder, exist_ok=True)
                        
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        filepath = os.path.join(upload_folder, unique_filename)
                        file.save(filepath)
                        arquivo_path = f"documents/transparencia/{unique_filename}"
            
            documento = EstatutoDocumento(
                titulo_pt=titulo_pt,
                titulo_es=titulo_es,
                titulo_en=titulo_en,
                descricao_pt=descricao_pt,
                descricao_es=descricao_es,
                descricao_en=descricao_en,
                tipo=tipo,
                ordem=ordem,
                data_documento=data_documento,
                arquivo=arquivo_path
            )
            db.session.add(documento)
            db.session.commit()
            flash('Documento cadastrado com sucesso!', 'success')
            return redirect(url_for('admin_transparencia'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar documento: {str(e)}', 'error')
    
    return render_template('admin/documento_form.html')

@app.route('/admin/transparencia/documento/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_documento_editar(id):
    documento = EstatutoDocumento.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            documento.titulo_pt = request.form.get('titulo_pt')
            documento.titulo_es = request.form.get('titulo_es', '')
            documento.titulo_en = request.form.get('titulo_en', '')
            documento.descricao_pt = request.form.get('descricao_pt', '')
            documento.descricao_es = request.form.get('descricao_es', '')
            documento.descricao_en = request.form.get('descricao_en', '')
            documento.tipo = request.form.get('tipo', 'documento')
            documento.ordem = int(request.form.get('ordem', 0))
            data_documento_str = request.form.get('data_documento')
            documento.data_documento = datetime.strptime(data_documento_str, '%Y-%m-%d').date() if data_documento_str else None
            
            # Upload do arquivo se fornecido
            if 'arquivo' in request.files:
                file = request.files['arquivo']
                if file.filename != '':
                    if file and allowed_file(file.filename):
                        upload_folder = 'static/documents/transparencia'
                        os.makedirs(upload_folder, exist_ok=True)
                        
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        filepath = os.path.join(upload_folder, unique_filename)
                        file.save(filepath)
                        documento.arquivo = f"documents/transparencia/{unique_filename}"
            
            documento.updated_at = datetime.utcnow()
            db.session.commit()
            flash('Documento atualizado com sucesso!', 'success')
            return redirect(url_for('admin_transparencia'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar documento: {str(e)}', 'error')
    
    return render_template('admin/documento_form.html', documento=documento)

@app.route('/admin/transparencia/documento/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_documento_excluir(id):
    documento = EstatutoDocumento.query.get_or_404(id)
    try:
        db.session.delete(documento)
        db.session.commit()
        flash('Documento excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir documento: {str(e)}', 'error')
    return redirect(url_for('admin_transparencia'))

# ============================================
# CRUD - PRESTAÇÃO DE CONTAS
# ============================================

@app.route('/admin/transparencia/prestacao/novo', methods=['GET', 'POST'])
@admin_required
def admin_prestacao_novo():
    if request.method == 'POST':
        try:
            titulo_pt = request.form.get('titulo_pt')
            titulo_es = request.form.get('titulo_es', '')
            titulo_en = request.form.get('titulo_en', '')
            descricao_pt = request.form.get('descricao_pt', '')
            descricao_es = request.form.get('descricao_es', '')
            descricao_en = request.form.get('descricao_en', '')
            recursos_recebidos_pt = request.form.get('recursos_recebidos_pt', '')
            recursos_recebidos_es = request.form.get('recursos_recebidos_es', '')
            recursos_recebidos_en = request.form.get('recursos_recebidos_en', '')
            resultados_pt = request.form.get('resultados_pt', '')
            resultados_es = request.form.get('resultados_es', '')
            resultados_en = request.form.get('resultados_en', '')
            ordem = int(request.form.get('ordem', 0))
            periodo_inicio_str = request.form.get('periodo_inicio')
            periodo_fim_str = request.form.get('periodo_fim')
            periodo_inicio = datetime.strptime(periodo_inicio_str, '%Y-%m-%d').date() if periodo_inicio_str else None
            periodo_fim = datetime.strptime(periodo_fim_str, '%Y-%m-%d').date() if periodo_fim_str else None
            
            if not titulo_pt:
                flash('Título em português é obrigatório!', 'error')
                return redirect(url_for('admin_prestacao_novo'))
            
            # Upload do arquivo
            arquivo_path = None
            if 'arquivo' in request.files:
                file = request.files['arquivo']
                if file.filename != '':
                    if file and allowed_document_file(file.filename):
                        upload_folder = 'static/documents/transparencia'
                        os.makedirs(upload_folder, exist_ok=True)
                        
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        filepath = os.path.join(upload_folder, unique_filename)
                        file.save(filepath)
                        arquivo_path = f"documents/transparencia/{unique_filename}"
            
            prestacao = PrestacaoConta(
                titulo_pt=titulo_pt,
                titulo_es=titulo_es,
                titulo_en=titulo_en,
                descricao_pt=descricao_pt,
                descricao_es=descricao_es,
                descricao_en=descricao_en,
                recursos_recebidos_pt=recursos_recebidos_pt,
                recursos_recebidos_es=recursos_recebidos_es,
                recursos_recebidos_en=recursos_recebidos_en,
                resultados_pt=resultados_pt,
                resultados_es=resultados_es,
                resultados_en=resultados_en,
                ordem=ordem,
                periodo_inicio=periodo_inicio,
                periodo_fim=periodo_fim,
                arquivo=arquivo_path
            )
            db.session.add(prestacao)
            db.session.commit()
            flash('Prestação de contas cadastrada com sucesso!', 'success')
            return redirect(url_for('admin_transparencia'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar prestação de contas: {str(e)}', 'error')
    
    return render_template('admin/prestacao_form.html')

@app.route('/admin/transparencia/prestacao/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_prestacao_editar(id):
    prestacao = PrestacaoConta.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            prestacao.titulo_pt = request.form.get('titulo_pt')
            prestacao.titulo_es = request.form.get('titulo_es', '')
            prestacao.titulo_en = request.form.get('titulo_en', '')
            prestacao.descricao_pt = request.form.get('descricao_pt', '')
            prestacao.descricao_es = request.form.get('descricao_es', '')
            prestacao.descricao_en = request.form.get('descricao_en', '')
            prestacao.recursos_recebidos_pt = request.form.get('recursos_recebidos_pt', '')
            prestacao.recursos_recebidos_es = request.form.get('recursos_recebidos_es', '')
            prestacao.recursos_recebidos_en = request.form.get('recursos_recebidos_en', '')
            prestacao.resultados_pt = request.form.get('resultados_pt', '')
            prestacao.resultados_es = request.form.get('resultados_es', '')
            prestacao.resultados_en = request.form.get('resultados_en', '')
            prestacao.ordem = int(request.form.get('ordem', 0))
            periodo_inicio_str = request.form.get('periodo_inicio')
            periodo_fim_str = request.form.get('periodo_fim')
            prestacao.periodo_inicio = datetime.strptime(periodo_inicio_str, '%Y-%m-%d').date() if periodo_inicio_str else None
            prestacao.periodo_fim = datetime.strptime(periodo_fim_str, '%Y-%m-%d').date() if periodo_fim_str else None
            
            # Upload do arquivo se fornecido
            if 'arquivo' in request.files:
                file = request.files['arquivo']
                if file.filename != '':
                    if file and allowed_file(file.filename):
                        upload_folder = 'static/documents/transparencia'
                        os.makedirs(upload_folder, exist_ok=True)
                        
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        filepath = os.path.join(upload_folder, unique_filename)
                        file.save(filepath)
                        prestacao.arquivo = f"documents/transparencia/{unique_filename}"
            
            prestacao.updated_at = datetime.utcnow()
            db.session.commit()
            flash('Prestação de contas atualizada com sucesso!', 'success')
            return redirect(url_for('admin_transparencia'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar prestação de contas: {str(e)}', 'error')
    
    return render_template('admin/prestacao_form.html', prestacao=prestacao)

@app.route('/admin/transparencia/prestacao/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_prestacao_excluir(id):
    prestacao = PrestacaoConta.query.get_or_404(id)
    try:
        db.session.delete(prestacao)
        db.session.commit()
        flash('Prestação de contas excluída com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir prestação de contas: {str(e)}', 'error')
    return redirect(url_for('admin_transparencia'))

# ============================================
# CRUD - INFORMAÇÕES DE DOAÇÕES
# ============================================

@app.route('/admin/transparencia/doacao-info/novo', methods=['GET', 'POST'])
@admin_required
def admin_doacao_info_novo():
    if request.method == 'POST':
        try:
            titulo_pt = request.form.get('titulo_pt')
            titulo_es = request.form.get('titulo_es', '')
            titulo_en = request.form.get('titulo_en', '')
            descricao_pt = request.form.get('descricao_pt', '')
            descricao_es = request.form.get('descricao_es', '')
            descricao_en = request.form.get('descricao_en', '')
            como_contribuir_pt = request.form.get('como_contribuir_pt', '')
            como_contribuir_es = request.form.get('como_contribuir_es', '')
            como_contribuir_en = request.form.get('como_contribuir_en', '')
            ordem = int(request.form.get('ordem', 0))
            
            if not titulo_pt:
                flash('Título em português é obrigatório!', 'error')
                return redirect(url_for('admin_doacao_info_novo'))
            
            info = InformacaoDoacao(
                titulo_pt=titulo_pt,
                titulo_es=titulo_es,
                titulo_en=titulo_en,
                descricao_pt=descricao_pt,
                descricao_es=descricao_es,
                descricao_en=descricao_en,
                como_contribuir_pt=como_contribuir_pt,
                como_contribuir_es=como_contribuir_es,
                como_contribuir_en=como_contribuir_en,
                ordem=ordem
            )
            db.session.add(info)
            db.session.commit()
            flash('Informação de doação cadastrada com sucesso!', 'success')
            return redirect(url_for('admin_transparencia'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar informação: {str(e)}', 'error')
    
    return render_template('admin/doacao_info_form.html')

@app.route('/admin/transparencia/doacao-info/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_doacao_info_editar(id):
    info = InformacaoDoacao.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            info.titulo_pt = request.form.get('titulo_pt')
            info.titulo_es = request.form.get('titulo_es', '')
            info.titulo_en = request.form.get('titulo_en', '')
            info.descricao_pt = request.form.get('descricao_pt', '')
            info.descricao_es = request.form.get('descricao_es', '')
            info.descricao_en = request.form.get('descricao_en', '')
            info.como_contribuir_pt = request.form.get('como_contribuir_pt', '')
            info.como_contribuir_es = request.form.get('como_contribuir_es', '')
            info.como_contribuir_en = request.form.get('como_contribuir_en', '')
            info.ordem = int(request.form.get('ordem', 0))
            
            info.updated_at = datetime.utcnow()
            db.session.commit()
            flash('Informação de doação atualizada com sucesso!', 'success')
            return redirect(url_for('admin_transparencia'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar informação: {str(e)}', 'error')
    
    return render_template('admin/doacao_info_form.html', info=info)

@app.route('/admin/transparencia/doacao-info/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_doacao_info_excluir(id):
    info = InformacaoDoacao.query.get_or_404(id)
    try:
        db.session.delete(info)
        db.session.commit()
        flash('Informação de doação excluída com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir informação: {str(e)}', 'error')
    return redirect(url_for('admin_transparencia'))

# ============================================
# CRUD - ASSOCIADOS
# ============================================

@app.route('/admin/associados')
@admin_required
def admin_associados():
    status_filter = request.args.get('status', 'todos')
    
    if status_filter == 'pendentes':
        associados = Associado.query.filter_by(status='pendente').order_by(Associado.created_at.desc()).all()
    elif status_filter == 'aprovados':
        associados = Associado.query.filter_by(status='aprovado').order_by(Associado.nome_completo.asc()).all()
    elif status_filter == 'negados':
        associados = Associado.query.filter_by(status='negado').order_by(Associado.created_at.desc()).all()
    else:
        associados = Associado.query.order_by(Associado.created_at.desc()).all()
    
    # Contar por status
    pendentes_count = Associado.query.filter_by(status='pendente').count()
    aprovados_count = Associado.query.filter_by(status='aprovado').count()
    negados_count = Associado.query.filter_by(status='negado').count()
    
    return render_template('admin/associados.html', 
                         associados=associados, 
                         status_filter=status_filter,
                         pendentes_count=pendentes_count,
                         aprovados_count=aprovados_count,
                         negados_count=negados_count)

@app.route('/admin/associados/novo', methods=['GET', 'POST'])
@admin_required
def admin_associados_novo():
    if request.method == 'POST':
        try:
            data_nascimento_str = request.form.get('data_nascimento')
            senha = request.form.get('senha')
            valor_mensalidade = request.form.get('valor_mensalidade', '0')
            
            if not senha or len(senha) < 6:
                flash('A senha deve ter no mínimo 6 caracteres', 'error')
                return redirect(url_for('admin_associados_novo'))
            
            # Upload da foto se fornecida
            foto_path = None
            if 'foto' in request.files:
                file = request.files['foto']
                if file.filename != '':
                    if file and allowed_file(file.filename):
                        upload_folder = 'static/images/associados'
                        os.makedirs(upload_folder, exist_ok=True)
                        
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        filepath = os.path.join(upload_folder, unique_filename)
                        file.save(filepath)
                        foto_path = f"images/associados/{unique_filename}"
                    else:
                        flash('Formato de arquivo não permitido. Use JPG, PNG ou GIF.', 'error')
                        return redirect(url_for('admin_associados_novo'))
            
            associado = Associado(
                nome_completo=request.form.get('nome_completo'),
                cpf=request.form.get('cpf'),
                data_nascimento=datetime.strptime(data_nascimento_str, "%Y-%m-%d").date(),
                endereco=request.form.get('endereco'),
                telefone=request.form.get('telefone'),
                valor_mensalidade=float(valor_mensalidade) if valor_mensalidade else 0.0,
                status='aprovado',  # Cadastro pelo admin é aprovado automaticamente
                foto=foto_path,
                created_at=datetime.now()
            )
            associado.set_password(senha)
            db.session.add(associado)
            db.session.commit()
            
            # Gerar primeira mensalidade se o associado tiver valor configurado
            if associado.valor_mensalidade and associado.valor_mensalidade > 0:
                try:
                    gerar_primeira_mensalidade(associado)
                    flash('Associado cadastrado e aprovado com sucesso! Mensalidades geradas automaticamente.', 'success')
                except Exception as e:
                    print(f"Aviso: Erro ao gerar primeira mensalidade: {str(e)}")
                    flash('Associado cadastrado e aprovado com sucesso!', 'success')
            else:
                flash('Associado cadastrado e aprovado com sucesso! Configure o valor da mensalidade para gerar mensalidades automaticamente.', 'success')
            
            return redirect(url_for('admin_associados'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar associado: {str(e)}', 'error')
    
    return render_template('admin/associados_form.html')

@app.route('/admin/associados/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_associados_editar(id):
    associado = Associado.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            data_nascimento_str = request.form.get('data_nascimento')
            senha = request.form.get('senha')
            valor_mensalidade = request.form.get('valor_mensalidade', '0')
            
            associado.nome_completo = request.form.get('nome_completo')
            associado.cpf = request.form.get('cpf')
            associado.data_nascimento = datetime.strptime(data_nascimento_str, "%Y-%m-%d").date()
            associado.endereco = request.form.get('endereco')
            associado.telefone = request.form.get('telefone')
            
            # Upload da foto se fornecida
            if 'foto' in request.files:
                file = request.files['foto']
                if file.filename != '':
                    if file and allowed_file(file.filename):
                        # Deletar foto antiga se existir
                        if associado.foto:
                            old_filepath = os.path.join('static', associado.foto)
                            if os.path.exists(old_filepath):
                                try:
                                    os.remove(old_filepath)
                                except Exception as e:
                                    print(f"Erro ao deletar foto antiga: {str(e)}")
                        
                        upload_folder = 'static/images/associados'
                        os.makedirs(upload_folder, exist_ok=True)
                        
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        filepath = os.path.join(upload_folder, unique_filename)
                        file.save(filepath)
                        associado.foto = f"images/associados/{unique_filename}"
                    else:
                        flash('Formato de arquivo não permitido. Use JPG, PNG ou GIF.', 'error')
                        return redirect(url_for('admin_associados_editar', id=id))
            
            # Atualizar status se fornecido
            status = request.form.get('status')
            if status in ['pendente', 'aprovado', 'negado']:
                associado.status = status
            
            # Atualizar senha apenas se fornecida
            if senha and len(senha) >= 6:
                associado.set_password(senha)
            
            # Atualizar valor da mensalidade
            valor_anterior = associado.valor_mensalidade
            novo_valor_mensalidade = float(valor_mensalidade) if valor_mensalidade else 0.0
            valor_anterior_float = float(valor_anterior) if valor_anterior else 0.0
            valor_alterado = abs(valor_anterior_float - novo_valor_mensalidade) > 0.01
            
            associado.valor_mensalidade = novo_valor_mensalidade
            
            # Se o valor foi alterado, atualizar todas as mensalidades não pagas
            mensalidades_atualizadas = 0
            if valor_alterado and novo_valor_mensalidade > 0:
                # Buscar todas as mensalidades não pagas (pendentes, atrasadas, canceladas)
                mensalidades_nao_pagas = Mensalidade.query.filter_by(
                    associado_id=associado.id
                ).filter(
                    Mensalidade.status != 'paga'
                ).all()
                
                desconto_tipo = associado.desconto_tipo
                desconto_valor_float = float(associado.desconto_valor) if associado.desconto_valor else 0.0
                
                for mensalidade in mensalidades_nao_pagas:
                    # Atualizar valor_base
                    mensalidade.valor_base = novo_valor_mensalidade
                    
                    # Aplicar desconto e recalcular valor_final
                    valor_base = float(mensalidade.valor_base)
                    
                    if desconto_tipo == 'porcentagem' and desconto_valor_float > 0:
                        valor_final = valor_base * (1 - desconto_valor_float / 100)
                        mensalidade.desconto_tipo = desconto_tipo
                        mensalidade.desconto_valor = desconto_valor_float
                    elif desconto_tipo == 'real' and desconto_valor_float > 0:
                        valor_final = valor_base - desconto_valor_float
                        mensalidade.desconto_tipo = desconto_tipo
                        mensalidade.desconto_valor = desconto_valor_float
                    else:
                        # Se não há desconto configurado no associado, usar o desconto individual da mensalidade (se existir)
                        if mensalidade.desconto_tipo == 'porcentagem' and mensalidade.desconto_valor:
                            valor_final = valor_base * (1 - float(mensalidade.desconto_valor) / 100)
                        elif mensalidade.desconto_tipo == 'real' and mensalidade.desconto_valor:
                            valor_final = valor_base - float(mensalidade.desconto_valor)
                        else:
                            valor_final = valor_base
                    
                    valor_final = max(0.0, valor_final)  # Não permite valor negativo
                    mensalidade.valor_final = valor_final
                    mensalidades_atualizadas += 1
            
            db.session.commit()
            
            mensagem = 'Associado atualizado com sucesso!'
            if mensalidades_atualizadas > 0:
                mensagem += f' Valor da mensalidade atualizado em {mensalidades_atualizadas} mensalidade(s) não paga(s).'
            
            flash(mensagem, 'success')
            return redirect(url_for('admin_associados'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar associado: {str(e)}', 'error')
    
    return render_template('admin/associados_form.html', associado=associado)

@app.route('/admin/associados/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_associados_excluir(id):
    associado = Associado.query.get_or_404(id)
    try:
        # Desativar antes de excluir para parar geração de mensalidades
        associado.ativo = False
        db.session.commit()
        
        # Excluir todas as mensalidades do associado antes de excluir o associado
        mensalidades = Mensalidade.query.filter_by(associado_id=associado.id).all()
        for mensalidade in mensalidades:
            db.session.delete(mensalidade)
        
        # Excluir foto do associado se existir
        if associado.foto:
            foto_filepath = os.path.join('static', associado.foto)
            if os.path.exists(foto_filepath):
                try:
                    os.remove(foto_filepath)
                except Exception as e:
                    print(f"Erro ao deletar foto do associado: {str(e)}")
        
        # Excluir carteira PDF se existir
        if associado.carteira_pdf:
            carteira_filepath = os.path.join('static', associado.carteira_pdf)
            if os.path.exists(carteira_filepath):
                try:
                    os.remove(carteira_filepath)
                except Exception as e:
                    print(f"Erro ao deletar carteira PDF: {str(e)}")
        
        # Depois excluir o associado
        db.session.delete(associado)
        db.session.commit()
        flash('Associado excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir associado: {str(e)}', 'error')
    return redirect(url_for('admin_associados'))

# ============================================
# CRUD - CARTEIRAS DE ASSOCIADOS
# ============================================

def draw_rg_border(canvas, doc, border_color, is_front):
    """Desenha a borda azul do RG com design melhorado"""
    # Desenhar borda azul mais espessa
    canvas.setStrokeColor(border_color)
    canvas.setLineWidth(3)
    
    # Retângulo externo com borda azul
    canvas.rect(3*mm, 3*mm, doc.width - 6*mm, doc.height - 6*mm, stroke=1, fill=0)
    
    # Linha horizontal superior decorativa (como no RG)
    canvas.setLineWidth(1.5)
    canvas.line(3*mm, doc.height - 12*mm, doc.width - 3*mm, doc.height - 12*mm)
    
    # Linha horizontal inferior decorativa
    canvas.line(3*mm, 8*mm, doc.width - 3*mm, 8*mm)
    
    # Se for a frente, adicionar texto "BRASIL" no topo com melhor estilo
    if is_front:
        canvas.setFillColor(border_color)
        canvas.setFont("Helvetica-Bold", 10)
        canvas.drawCentredString(doc.width / 2, doc.height - 9*mm, "BRASIL")

def gerar_carteira_pdf(associado):
    """Gera o PDF da carteira de associado no formato RG brasileiro (azul) - UMA PÁGINA com frente e verso"""
    try:
        # Criar diretório se não existir
        upload_folder = 'static/documents/carteiras'
        os.makedirs(upload_folder, exist_ok=True)
        
        # Nome do arquivo
        filename = f"carteira_{associado.cpf.replace('.', '').replace('-', '')}.pdf"
        filepath = os.path.join(upload_folder, filename)
        
        # Tamanho do RG brasileiro (10.5cm x 6.5cm)
        card_width = 10.5 * cm
        card_height = 6.5 * cm
        
        # Buscar dados da associação
        dados_associacao = DadosAssociacao.get_dados()
        
        # Criar PDF usando canvas diretamente
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.pdfgen import canvas as pdfcanvas
        
        page_width, page_height = landscape(A4)
        gap = 10*mm
        total_width = card_width * 2 + gap
        
        # Posições centralizadas
        frente_x = (page_width - total_width) / 2
        frente_y = (page_height - card_height) / 2
        verso_x = frente_x + card_width + gap
        verso_y = frente_y
        
        # Criar canvas
        c = pdfcanvas.Canvas(filepath, pagesize=landscape(A4))
        border_color = colors.HexColor('#1e40af')
        
        # Logo
        logo_path = os.path.join('static', 'images', 'logo.png')
        if not os.path.exists(logo_path):
            logo_path = os.path.join('static', 'images', 'logorodape.png')
        
        def draw_card_front(x, y, width, height):
            """Desenha a frente da carteira"""
            # Borda azul
            c.setStrokeColor(border_color)
            c.setLineWidth(3)
            c.rect(x, y, width, height, stroke=1, fill=0)
            
            # Linhas decorativas
            c.setLineWidth(1.5)
            c.line(x, y + height - 12*mm, x + width, y + height - 12*mm)
            c.line(x, y + 8*mm, x + width, y + 8*mm)
            
            # BRASIL no topo
            c.setFillColor(border_color)
            c.setFont("Helvetica-Bold", 9)
            c.drawCentredString(x + width/2, y + height - 9*mm, "BRASIL")
            
            # Área interna com margem de 4mm
            inner_x = x + 4*mm
            inner_y = y + 4*mm
            inner_w = width - 8*mm
            inner_h = height - 8*mm
            
            # Logo (centro superior)
            if os.path.exists(logo_path):
                try:
                    from PIL import Image as PILImage
                    img = PILImage.open(logo_path)
                    img_w, img_h = img.size
                    aspect = img_w / img_h
                    logo_h = 9*mm
                    logo_w = logo_h * aspect
                    if logo_w > inner_w - 2*mm:
                        logo_w = inner_w - 2*mm
                        logo_h = logo_w / aspect
                    logo_x = x + (width - logo_w) / 2
                    logo_y = y + height - 20*mm
                    c.drawImage(logo_path, logo_x, logo_y, width=logo_w, height=logo_h, preserveAspectRatio=True)
                except:
                    pass
            
            # Título
            c.setFillColor(border_color)
            c.setFont("Helvetica-Bold", 7.5)
            c.drawCentredString(x + width/2, y + height - 32*mm, "CARTEIRA DE ASSOCIADO")
            
            # Foto (esquerda, abaixo do título)
            foto_x = inner_x
            foto_y = y + 20*mm
            foto_w_max = 22*mm
            foto_h_max = 28*mm
            
            if associado.foto:
                foto_path = os.path.join('static', associado.foto)
                if os.path.exists(foto_path):
                    try:
                        from PIL import Image as PILImage
                        img = PILImage.open(foto_path)
                        img_w, img_h = img.size
                        aspect = img_w / img_h
                        foto_h = min(foto_h_max, inner_h - 40*mm)
                        foto_w = foto_h * aspect
                        if foto_w > foto_w_max:
                            foto_w = foto_w_max
                            foto_h = foto_w / aspect
                        c.drawImage(foto_path, foto_x, foto_y, width=foto_w, height=foto_h, preserveAspectRatio=True)
                    except:
                        pass
            
            # Nome e CPF (direita da foto)
            text_x = inner_x + 24*mm
            text_y = y + height - 42*mm
            
            nome = associado.nome_completo.upper()
            c.setFillColor(colors.HexColor('#1f2937'))
            c.setFont("Helvetica-Bold", 7.5)
            
            # Quebrar nome se necessário
            max_chars = 22
            if len(nome) > max_chars:
                palavras = nome.split()
                meio = len(palavras) // 2
                linha1 = ' '.join(palavras[:meio])
                linha2 = ' '.join(palavras[meio:])
                c.drawString(text_x, text_y, linha1[:max_chars])
                c.drawString(text_x, text_y - 6*mm, linha2[:max_chars])
                cpf_y = text_y - 12*mm
            else:
                c.drawString(text_x, text_y, nome[:max_chars])
                cpf_y = text_y - 7*mm
            
            c.setFont("Helvetica", 6)
            c.drawString(text_x, cpf_y, f"CPF: {associado.cpf}")
        
        def draw_card_back(x, y, width, height):
            """Desenha o verso da carteira"""
            # Borda azul
            c.setStrokeColor(border_color)
            c.setLineWidth(3)
            c.rect(x, y, width, height, stroke=1, fill=0)
            
            # Linhas decorativas
            c.setLineWidth(1.5)
            c.line(x, y + height - 12*mm, x + width, y + height - 12*mm)
            c.line(x, y + 8*mm, x + width, y + 8*mm)
            
            # Área interna com margem de 4mm
            inner_x = x + 4*mm
            inner_y = y + 4*mm
            inner_w = width - 8*mm
            inner_h = height - 8*mm
            
            # Título (centro superior, dentro da borda)
            c.setFillColor(border_color)
            c.setFont("Helvetica-Bold", 7.5)
            titulo_y = y + height - 25*mm
            c.drawCentredString(x + width/2, titulo_y, "DADOS DA ASSOCIAÇÃO")
            
            # Dados (abaixo do título, dentro da borda)
            dados_start_y = y + height - 38*mm
            label_x = inner_x
            value_x = inner_x + 14*mm
            line_h = 6*mm
            
            # Layout em duas colunas: esquerda (Nome, CNPJ) e direita (Endereço)
            col_left_x = inner_x
            col_right_x = inner_x + inner_w / 2
            col_width = inner_w / 2 - 2*mm
            
            c.setFillColor(colors.HexColor('#1f2937'))
            
            # Nome (coluna esquerda)
            c.setFont("Helvetica-Bold", 5.5)
            c.drawString(col_left_x, dados_start_y, "Nome:")
            c.setFont("Helvetica", 5.5)
            nome_assoc = dados_associacao.nome
            max_chars = 25
            nome_value_x = col_left_x + 12*mm
            if len(nome_assoc) > max_chars:
                palavras = nome_assoc.split()
                meio = len(palavras) // 2
                linha1 = ' '.join(palavras[:meio])
                linha2 = ' '.join(palavras[meio:])
                c.drawString(nome_value_x, dados_start_y, linha1[:max_chars])
                c.drawString(nome_value_x, dados_start_y - line_h, linha2[:max_chars])
                cnpj_y = dados_start_y - (line_h * 2)
            else:
                c.drawString(nome_value_x, dados_start_y, nome_assoc[:max_chars])
                cnpj_y = dados_start_y - line_h
            
            # Endereço (coluna direita, alinhado verticalmente com Nome)
            end_y = dados_start_y
            c.setFont("Helvetica-Bold", 5.5)
            c.drawString(col_right_x, end_y, "Endereço:")
            c.setFont("Helvetica", 5.5)
            endereco = dados_associacao.endereco
            max_chars_line = 20
            endereco_x = col_right_x + 16*mm
            
            # Quebrar endereço em múltiplas linhas se necessário
            if len(endereco) > max_chars_line:
                partes = endereco.split(', ')
                current = partes[0]
                offset = 0
                for parte in partes[1:]:
                    if len(current + ', ' + parte) <= max_chars_line:
                        current += ', ' + parte
                    else:
                        c.drawString(endereco_x, end_y - offset, current[:max_chars_line])
                        offset += line_h
                        current = parte
                if current:
                    c.drawString(endereco_x, end_y - offset, current[:max_chars_line])
            else:
                c.drawString(endereco_x, end_y, endereco[:max_chars_line])
            
            # CNPJ (coluna esquerda, abaixo do Nome)
            c.setFont("Helvetica-Bold", 5.5)
            c.drawString(col_left_x, cnpj_y, "CNPJ:")
            c.setFont("Helvetica", 5.5)
            c.drawString(col_left_x + 12*mm, cnpj_y, dados_associacao.cnpj)
        
        # Desenhar frente e verso
        draw_card_front(frente_x, frente_y, card_width, card_height)
        draw_card_back(verso_x, verso_y, card_width, card_height)
        
        # Salvar
        c.showPage()
        c.save()
        
        return f"documents/carteiras/{filename}"
        
    except Exception as e:
        print(f"Erro ao gerar carteira PDF: {str(e)}")
        raise

@app.route('/admin/carteiras')
@admin_required
def admin_carteiras():
    """Lista todos os associados para gerenciar carteiras"""
    status_filter = request.args.get('status', 'todos')
    
    if status_filter == 'pendentes':
        associados = Associado.query.filter_by(status='pendente').order_by(Associado.created_at.desc()).all()
    elif status_filter == 'aprovados':
        associados = Associado.query.filter_by(status='aprovado').order_by(Associado.nome_completo.asc()).all()
    elif status_filter == 'negados':
        associados = Associado.query.filter_by(status='negado').order_by(Associado.created_at.desc()).all()
    else:
        associados = Associado.query.order_by(Associado.created_at.desc()).all()
    
    # Contar por status
    pendentes_count = Associado.query.filter_by(status='pendente').count()
    aprovados_count = Associado.query.filter_by(status='aprovado').count()
    negados_count = Associado.query.filter_by(status='negado').count()
    
    return render_template('admin/carteiras.html', 
                         associados=associados, 
                         status_filter=status_filter,
                         pendentes_count=pendentes_count,
                         aprovados_count=aprovados_count,
                         negados_count=negados_count)

@app.route('/admin/carteiras/<int:id>/gerar', methods=['POST'])
@admin_required
def admin_carteira_gerar(id):
    """Gera a carteira PDF para um associado"""
    associado = Associado.query.get_or_404(id)
    
    if associado.status != 'aprovado':
        flash('Apenas associados aprovados podem ter carteiras geradas.', 'error')
        return redirect(url_for('admin_carteiras'))
    
    try:
        # Deletar carteira antiga se existir
        if associado.carteira_pdf:
            old_filepath = os.path.join('static', associado.carteira_pdf)
            if os.path.exists(old_filepath):
                try:
                    os.remove(old_filepath)
                except Exception as e:
                    print(f"Erro ao deletar carteira antiga: {str(e)}")
        
        # Gerar nova carteira
        carteira_path = gerar_carteira_pdf(associado)
        
        # Atualizar no banco de dados
        associado.carteira_pdf = carteira_path
        db.session.commit()
        
        flash(f'Carteira gerada com sucesso para {associado.nome_completo}!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao gerar carteira: {str(e)}', 'error')
    
    return redirect(url_for('admin_carteiras'))

@app.route('/admin/carteiras/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_carteira_excluir(id):
    """Exclui a carteira PDF de um associado"""
    associado = Associado.query.get_or_404(id)
    
    try:
        if associado.carteira_pdf:
            filepath = os.path.join('static', associado.carteira_pdf)
            if os.path.exists(filepath):
                os.remove(filepath)
            
            associado.carteira_pdf = None
            db.session.commit()
            flash(f'Carteira excluída com sucesso para {associado.nome_completo}!', 'success')
        else:
            flash('Este associado não possui carteira cadastrada.', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir carteira: {str(e)}', 'error')
    
    return redirect(url_for('admin_carteiras'))

@app.route('/admin/associados/<int:id>/aprovar', methods=['POST'])
@admin_required
def admin_associados_aprovar(id):
    associado = Associado.query.get_or_404(id)
    try:
        associado.status = 'aprovado'
        db.session.commit()
        
        # Gerar primeira mensalidade se o associado tiver valor configurado
        try:
            gerar_primeira_mensalidade(associado)
        except Exception as e:
            print(f"Aviso: Erro ao gerar primeira mensalidade: {str(e)}")
        
        flash('Associado aprovado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao aprovar associado: {str(e)}', 'error')
    return redirect(url_for('admin_associados', status='pendentes'))

@app.route('/admin/associados/<int:id>/negar', methods=['POST'])
@admin_required
def admin_associados_negar(id):
    associado = Associado.query.get_or_404(id)
    try:
        associado.status = 'negado'
        associado.ativo = False  # Desativar para não gerar mensalidades
        db.session.commit()
        flash('Cadastro negado.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao negar cadastro: {str(e)}', 'error')
    return redirect(url_for('admin_associados', status='pendentes'))

# ============================================
# SISTEMA FINANCEIRO - MENSALIDADES
# ============================================

def calcular_dias_uteis(data_inicial, dias):
    """
    Calcula uma data X dias úteis à frente, excluindo sábados e domingos
    """
    data_atual = data_inicial
    dias_adicionados = 0
    
    while dias_adicionados < dias:
        data_atual += timedelta(days=1)
        # Segunda = 0, Domingo = 6
        if data_atual.weekday() < 5:  # Segunda a Sexta (0-4)
            dias_adicionados += 1
    
    return data_atual

def gerar_primeira_mensalidade(associado):
    """
    Gera mensalidades para 1 ano (12 meses) para um associado recém-cadastrado ou aprovado
    - Primeira mensalidade: vencimento em 3 dias úteis após cadastro/aprovação
    - Próximas 11 mensalidades: vencimento fixo no mesmo dia do mês do cadastro/aprovação
    """
    # Verificar se já existe alguma mensalidade para este associado
    mensalidade_existente = Mensalidade.query.filter_by(associado_id=associado.id).first()
    if mensalidade_existente:
        return  # Já existe mensalidade, não gerar
    
    # Verificar se o associado tem valor de mensalidade configurado
    if not associado.valor_mensalidade or associado.valor_mensalidade <= 0:
        return  # Não tem valor configurado, não gerar
    
    # Calcular valor final
    valor_final = associado.calcular_valor_final()
    
    # Data base: data de criação do associado
    data_base = associado.created_at.date() if isinstance(associado.created_at, datetime) else associado.created_at
    
    # Dia do cadastro/aprovação (será usado para as próximas mensalidades)
    dia_cadastro = data_base.day
    
    # PRIMEIRA MENSALIDADE: 3 dias úteis após cadastro/aprovação
    data_vencimento_primeira = calcular_dias_uteis(data_base, 3)
    mes_referencia_primeira = data_vencimento_primeira.month
    ano_referencia_primeira = data_vencimento_primeira.year
    
    mensalidade_primeira = Mensalidade(
        associado_id=associado.id,
        valor_base=float(associado.valor_mensalidade),
        desconto_tipo=associado.desconto_tipo,
        desconto_valor=float(associado.desconto_valor) if associado.desconto_valor else 0.0,
        valor_final=valor_final,
        mes_referencia=mes_referencia_primeira,
        ano_referencia=ano_referencia_primeira,
        data_vencimento=data_vencimento_primeira,
        status='pendente'
    )
    db.session.add(mensalidade_primeira)
    
    # PRÓXIMAS 11 MENSALIDADES: vencimento fixo no dia do cadastro
    # Começar do mês seguinte ao vencimento da primeira mensalidade
    mes_atual = data_vencimento_primeira.month
    ano_atual = data_vencimento_primeira.year
    
    # Se a primeira mensalidade vence no mesmo mês do cadastro, começar do próximo mês
    if mes_referencia_primeira == data_base.month:
        # Próximo mês
        if mes_atual == 12:
            mes_proximo = 1
            ano_proximo = ano_atual + 1
        else:
            mes_proximo = mes_atual + 1
            ano_proximo = ano_atual
    else:
        # A primeira mensalidade já está no próximo mês, começar do mês seguinte
        if mes_atual == 12:
            mes_proximo = 1
            ano_proximo = ano_atual + 1
        else:
            mes_proximo = mes_atual + 1
            ano_proximo = ano_atual
    
    # Gerar as próximas 11 mensalidades
    for i in range(11):
        # Calcular mês e ano
        mes = mes_proximo + i
        ano = ano_proximo
        
        # Ajustar se passar de dezembro
        while mes > 12:
            mes -= 12
            ano += 1
        
        # Verificar se o dia existe no mês (ex: 31/02 não existe)
        ultimo_dia_mes = monthrange(ano, mes)[1]
        dia_vencimento = min(dia_cadastro, ultimo_dia_mes)
        
        # Data de vencimento
        data_vencimento = date(ano, mes, dia_vencimento)
        
        # Criar mensalidade
        mensalidade = Mensalidade(
            associado_id=associado.id,
            valor_base=float(associado.valor_mensalidade),
            desconto_tipo=associado.desconto_tipo,
            desconto_valor=float(associado.desconto_valor) if associado.desconto_valor else 0.0,
            valor_final=valor_final,
            mes_referencia=mes,
            ano_referencia=ano,
            data_vencimento=data_vencimento,
            status='pendente'
        )
        db.session.add(mensalidade)
    
    db.session.commit()

def gerar_mensalidades_automaticas():
    """Gera mensalidades automaticamente para todos os associados ativos"""
    hoje = date.today()
    mes_atual = hoje.month
    ano_atual = hoje.year
    
    # Buscar todos os associados aprovados e ativos com valor de mensalidade definido
    associados = Associado.query.filter_by(
        status='aprovado',
        ativo=True
    ).filter(Associado.valor_mensalidade > 0).all()
    
    mensalidades_geradas = 0
    
    for associado in associados:
        # Verificar se já existe mensalidade para este mês/ano
        mensalidade_existente = Mensalidade.query.filter_by(
            associado_id=associado.id,
            mes_referencia=mes_atual,
            ano_referencia=ano_atual
        ).first()
        
        if not mensalidade_existente:
            # Calcular valor final
            valor_final = associado.calcular_valor_final()
            
            # Calcular data de vencimento (dia 10 do mês atual)
            dia_vencimento = 10
            data_vencimento = date(ano_atual, mes_atual, dia_vencimento)
            
            # Se o dia 10 já passou, usar o próximo mês
            if hoje > data_vencimento:
                # Próximo mês
                if mes_atual == 12:
                    mes_vencimento = 1
                    ano_vencimento = ano_atual + 1
                else:
                    mes_vencimento = mes_atual + 1
                    ano_vencimento = ano_atual
                
                # Verificar se o dia existe no mês
                ultimo_dia = monthrange(ano_vencimento, mes_vencimento)[1]
                dia_vencimento = min(dia_vencimento, ultimo_dia)
                data_vencimento = date(ano_vencimento, mes_vencimento, dia_vencimento)
            
            # Criar mensalidade
            mensalidade = Mensalidade(
                associado_id=associado.id,
                valor_base=float(associado.valor_mensalidade),
                desconto_tipo=associado.desconto_tipo,
                desconto_valor=float(associado.desconto_valor) if associado.desconto_valor else 0.0,
                valor_final=valor_final,
                mes_referencia=mes_atual,
                ano_referencia=ano_atual,
                data_vencimento=data_vencimento,
                status='pendente'
            )
            db.session.add(mensalidade)
            mensalidades_geradas += 1
    
    if mensalidades_geradas > 0:
        db.session.commit()
    
    return mensalidades_geradas

# ============================================
# SISTEMA DE CONTAS - DOAÇÕES E GASTOS
# ============================================

@app.route('/admin/contas')
@admin_required
def admin_contas():
    # Buscar doações e gastos
    doacoes = Doacao.query.order_by(Doacao.data_doacao.desc()).all()
    gastos = Gasto.query.order_by(Gasto.data_gasto.desc()).all()
    
    # Calcular estatísticas
    # Para doações financeiras: somar valores
    total_doacoes_financeira = db.session.query(db.func.sum(Doacao.valor)).filter_by(tipo='financeira').scalar() or 0.0
    # Para materiais e serviços: contar quantidade total
    total_doacoes_material = db.session.query(db.func.sum(Doacao.quantidade)).filter_by(tipo='material').scalar() or 0
    # Calcular totais de serviços agrupados por unidade
    doacoes_servico = db.session.query(Doacao.unidade, db.func.sum(Doacao.quantidade)).filter_by(tipo='servico').group_by(Doacao.unidade).all()
    total_doacoes_servico_por_unidade = {}
    for unidade, total in doacoes_servico:
        if unidade:
            total_doacoes_servico_por_unidade[unidade] = int(total) if total else 0
    total_gastos = db.session.query(db.func.sum(Gasto.valor)).scalar() or 0.0
    
    return render_template('admin/contas.html',
                         doacoes=doacoes,
                         gastos=gastos,
                         total_doacoes_financeira=float(total_doacoes_financeira),
                         total_doacoes_material=int(total_doacoes_material),
                         total_doacoes_servico_por_unidade=total_doacoes_servico_por_unidade,
                         total_gastos=float(total_gastos))

@app.route('/admin/contas/doacao/novo', methods=['GET', 'POST'])
@admin_required
def admin_doacao_novo():
    if request.method == 'POST':
        try:
            tipo = request.form.get('tipo')
            descricao = request.form.get('descricao')
            valor = request.form.get('valor', '0')
            quantidade = request.form.get('quantidade', '0')
            unidade = request.form.get('unidade', '')
            doador = request.form.get('doador', '')
            pais = request.form.get('pais', '')
            # País agora vem diretamente do select (todos os países estão na lista)
            telefone = request.form.get('telefone', '').strip()
            tipo_documento = request.form.get('tipo_documento', '')
            documento = request.form.get('documento', '').replace('.', '').replace('-', '').replace('/', '').replace(' ', '').upper()
            data_doacao_str = request.form.get('data_doacao')
            observacoes = request.form.get('observacoes', '')
            
            doacao = Doacao(
                tipo=tipo,
                descricao=descricao,
                valor=float(valor) if valor and tipo == 'financeira' else None,
                quantidade=int(quantidade) if quantidade and tipo in ['material', 'servico'] else None,
                unidade=unidade if tipo in ['material', 'servico'] else None,
                doador=doador,
                pais=pais if pais else None,
                telefone=telefone if telefone else None,
                tipo_documento=tipo_documento if tipo_documento else None,
                documento=documento if documento else None,
                data_doacao=datetime.strptime(data_doacao_str, "%Y-%m-%d").date(),
                observacoes=observacoes
            )
            db.session.add(doacao)
            db.session.commit()
            flash('Doação cadastrada com sucesso!', 'success')
            return redirect(url_for('admin_contas'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar doação: {str(e)}', 'error')
    
    return render_template('admin/doacao_form.html')

@app.route('/admin/contas/doacao/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_doacao_editar(id):
    doacao = Doacao.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            doacao.tipo = request.form.get('tipo')
            doacao.descricao = request.form.get('descricao')
            valor = request.form.get('valor', '0')
            quantidade = request.form.get('quantidade', '0')
            unidade = request.form.get('unidade', '')
            doacao.doador = request.form.get('doador', '')
            pais = request.form.get('pais', '')
            # País agora vem diretamente do select (todos os países estão na lista)
            telefone = request.form.get('telefone', '').strip()
            tipo_documento = request.form.get('tipo_documento', '')
            documento = request.form.get('documento', '').replace('.', '').replace('-', '').replace('/', '').replace(' ', '').upper()
            data_doacao_str = request.form.get('data_doacao')
            doacao.observacoes = request.form.get('observacoes', '')
            
            doacao.valor = float(valor) if valor and doacao.tipo == 'financeira' else None
            doacao.quantidade = int(quantidade) if quantidade and doacao.tipo in ['material', 'servico'] else None
            doacao.unidade = unidade if doacao.tipo in ['material', 'servico'] else None
            doacao.pais = pais if pais else None
            doacao.telefone = telefone if telefone else None
            doacao.tipo_documento = tipo_documento if tipo_documento else None
            doacao.documento = documento if documento else None
            doacao.data_doacao = datetime.strptime(data_doacao_str, "%Y-%m-%d").date()
            
            db.session.commit()
            flash('Doação atualizada com sucesso!', 'success')
            return redirect(url_for('admin_contas'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar doação: {str(e)}', 'error')
    
    return render_template('admin/doacao_form.html', doacao=doacao)

@app.route('/admin/contas/doacao/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_doacao_excluir(id):
    doacao = Doacao.query.get_or_404(id)
    try:
        db.session.delete(doacao)
        db.session.commit()
        flash('Doação excluída com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir doação: {str(e)}', 'error')
    return redirect(url_for('admin_contas'))

@app.route('/admin/contas/gasto/novo', methods=['GET', 'POST'])
@admin_required
def admin_gasto_novo():
    if request.method == 'POST':
        try:
            descricao = request.form.get('descricao')
            valor = request.form.get('valor', '0')
            # Usar 'tipo' do formulário como categoria
            tipo_gasto = request.form.get('tipo', request.form.get('categoria', ''))
            fornecedor = request.form.get('fornecedor', '')
            data_gasto_str = request.form.get('data_gasto')
            observacoes = request.form.get('observacoes', '')
            
            gasto = Gasto(
                descricao=descricao,
                valor=float(valor),
                categoria=tipo_gasto,
                fornecedor=fornecedor,
                data_gasto=datetime.strptime(data_gasto_str, "%Y-%m-%d").date(),
                observacoes=observacoes
            )
            db.session.add(gasto)
            db.session.commit()
            flash('Gasto cadastrado com sucesso!', 'success')
            return redirect(url_for('admin_contas'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar gasto: {str(e)}', 'error')
    
    return render_template('admin/gasto_form.html')

@app.route('/admin/contas/gasto/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_gasto_editar(id):
    gasto = Gasto.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            gasto.descricao = request.form.get('descricao')
            gasto.valor = float(request.form.get('valor', '0'))
            # Usar 'tipo' do formulário como categoria
            gasto.categoria = request.form.get('tipo', request.form.get('categoria', ''))
            gasto.fornecedor = request.form.get('fornecedor', '')
            data_gasto_str = request.form.get('data_gasto')
            gasto.observacoes = request.form.get('observacoes', '')
            
            gasto.data_gasto = datetime.strptime(data_gasto_str, "%Y-%m-%d").date()
            
            db.session.commit()
            flash('Gasto atualizado com sucesso!', 'success')
            return redirect(url_for('admin_contas'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar gasto: {str(e)}', 'error')
    
    return render_template('admin/gasto_form.html', gasto=gasto)

@app.route('/admin/contas/gasto/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_gasto_excluir(id):
    gasto = Gasto.query.get_or_404(id)
    try:
        db.session.delete(gasto)
        db.session.commit()
        flash('Gasto excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir gasto: {str(e)}', 'error')
    return redirect(url_for('admin_contas'))

# ============================================
# GERENCIAMENTO DE USUÁRIOS ADMINISTRATIVOS
# ============================================

@app.route('/admin/usuarios')
@admin_required
def admin_usuarios():
    usuarios = Usuario.query.order_by(Usuario.created_at.desc()).all()
    return render_template('admin/usuarios.html', usuarios=usuarios)

@app.route('/admin/usuarios/novo', methods=['GET', 'POST'])
@admin_required
def admin_usuarios_novo():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        nome = request.form.get('nome', '').strip()
        password = request.form.get('password', '').strip()
        password_confirm = request.form.get('password_confirm', '').strip()
        
        # Validações
        if not username or not nome or not password:
            flash('Todos os campos são obrigatórios!', 'error')
            return redirect(url_for('admin_usuarios_novo'))
        
        if password != password_confirm:
            flash('As senhas não coincidem!', 'error')
            return redirect(url_for('admin_usuarios_novo'))
        
        if len(password) < 6:
            flash('A senha deve ter no mínimo 6 caracteres!', 'error')
            return redirect(url_for('admin_usuarios_novo'))
        
        # Verificar se o username já existe
        if Usuario.query.filter_by(username=username).first():
            flash('Este nome de usuário já está em uso!', 'error')
            return redirect(url_for('admin_usuarios_novo'))
        
        try:
            novo_usuario = Usuario(
                username=username,
                nome=nome,
            )
            novo_usuario.set_password(password)
            
            # Verificar se é super admin
            is_super_admin = request.form.get('is_super_admin') == 'on'
            novo_usuario.is_super_admin = is_super_admin
            
            db.session.add(novo_usuario)
            db.session.flush()  # Para obter o ID do usuário
            
            # Processar permissões selecionadas (se não for super admin)
            if not is_super_admin:
                permissoes_selecionadas = request.form.getlist('permissoes')
                if permissoes_selecionadas:
                    permissoes_objs = Permissao.query.filter(Permissao.id.in_([int(pid) for pid in permissoes_selecionadas])).all()
                    novo_usuario.permissoes = permissoes_objs
            
            db.session.commit()
            flash('Usuário cadastrado com sucesso!', 'success')
            return redirect(url_for('admin_usuarios'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar usuário: {str(e)}', 'error')
            return redirect(url_for('admin_usuarios_novo'))
    
    permissoes = Permissao.query.order_by(Permissao.categoria.asc(), Permissao.nome.asc()).all()
    permissoes_por_categoria = {}
    for perm in permissoes:
        if perm.categoria not in permissoes_por_categoria:
            permissoes_por_categoria[perm.categoria] = []
        permissoes_por_categoria[perm.categoria].append(perm)
    
    return render_template('admin/usuario_form.html', permissoes_por_categoria=permissoes_por_categoria)

@app.route('/admin/usuarios/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_usuarios_editar(id):
    usuario = Usuario.query.get_or_404(id)
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        nome = request.form.get('nome', '').strip()
        password = request.form.get('password', '').strip()
        password_confirm = request.form.get('password_confirm', '').strip()
        
        # Validações
        if not username or not nome:
            flash('Nome de usuário e nome completo são obrigatórios!', 'error')
            return redirect(url_for('admin_usuarios_editar', id=id))
        
        # Verificar se o username já existe (exceto o próprio usuário)
        usuario_existente = Usuario.query.filter_by(username=username).first()
        if usuario_existente and usuario_existente.id != id:
            flash('Este nome de usuário já está em uso!', 'error')
            return redirect(url_for('admin_usuarios_editar', id=id))
        
        # Atualizar dados básicos
        usuario.username = username
        usuario.nome = nome
        
        # Verificar se é super admin
        is_super_admin = request.form.get('is_super_admin') == 'on'
        usuario.is_super_admin = is_super_admin
        
        # Atualizar senha se fornecida
        if password:
            if password != password_confirm:
                flash('As senhas não coincidem!', 'error')
                return redirect(url_for('admin_usuarios_editar', id=id))
            if len(password) < 6:
                flash('A senha deve ter no mínimo 6 caracteres!', 'error')
                return redirect(url_for('admin_usuarios_editar', id=id))
            usuario.set_password(password)
        
        # Processar permissões selecionadas (se não for super admin)
        if not is_super_admin:
            permissoes_selecionadas = request.form.getlist('permissoes')
            permissoes_objs = Permissao.query.filter(Permissao.id.in_([int(pid) for pid in permissoes_selecionadas])).all()
            usuario.permissoes = permissoes_objs
        else:
            # Super admin não precisa de permissões específicas
            usuario.permissoes = []
        
        try:
            db.session.commit()
            flash('Usuário atualizado com sucesso!', 'success')
            return redirect(url_for('admin_usuarios'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar usuário: {str(e)}', 'error')
            return redirect(url_for('admin_usuarios_editar', id=id))
    
    permissoes = Permissao.query.order_by(Permissao.categoria.asc(), Permissao.nome.asc()).all()
    permissoes_por_categoria = {}
    for perm in permissoes:
        if perm.categoria not in permissoes_por_categoria:
            permissoes_por_categoria[perm.categoria] = []
        permissoes_por_categoria[perm.categoria].append(perm)
    
    return render_template('admin/usuario_form.html', usuario=usuario, permissoes_por_categoria=permissoes_por_categoria)

@app.route('/admin/usuarios/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_usuarios_excluir(id):
    usuario = Usuario.query.get_or_404(id)
    
    # Não permitir excluir o próprio usuário logado
    if session.get('admin_username') == usuario.username:
        flash('Você não pode excluir seu próprio usuário!', 'error')
        return redirect(url_for('admin_usuarios'))
    
    # Verificar se é o último usuário
    total_usuarios = Usuario.query.count()
    if total_usuarios <= 1:
        flash('Não é possível excluir o último usuário do sistema!', 'error')
        return redirect(url_for('admin_usuarios'))
    
    try:
        db.session.delete(usuario)
        db.session.commit()
        flash('Usuário excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir usuário: {str(e)}', 'error')
    
    return redirect(url_for('admin_usuarios'))

# ============================================
# GERENCIAMENTO DE APOIADORES
# ============================================

@app.route('/admin/apoiadores')
@admin_required
def admin_apoiadores():
    apoiadores = Apoiador.query.order_by(Apoiador.nome.asc()).all()
    return render_template('admin/apoiadores.html', apoiadores=apoiadores)

@app.route('/admin/apoiadores/novo', methods=['GET', 'POST'])
@admin_required
def admin_apoiadores_novo():
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        descricao = request.form.get('descricao', '').strip()
        website = request.form.get('website', '').strip()
        
        # Validações
        if not nome:
            flash('O nome do apoiador é obrigatório!', 'error')
            return redirect(url_for('admin_apoiadores_novo'))
        
        # Processar upload da foto
        logo_path = None
        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename != '' and allowed_file(file.filename):
                upload_folder = app.config['UPLOAD_FOLDER']
                os.makedirs(upload_folder, exist_ok=True)
                
                # Gerar nome único para o arquivo
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4()}_{filename}"
                filepath = os.path.join(upload_folder, unique_filename)
                file.save(filepath)
                
                logo_path = f"images/uploads/{unique_filename}"
            elif file and file.filename != '':
                flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP', 'error')
                return redirect(url_for('admin_apoiadores_novo'))
        
        tipo = request.form.get('tipo', '').strip()
        if not tipo:
            flash('O tipo do apoiador é obrigatório!', 'error')
            return redirect(url_for('admin_apoiadores_novo'))
        
        try:
            novo_apoiador = Apoiador(
                nome=nome,
                tipo=tipo,
                descricao=descricao if descricao else None,
                website=website if website else None,
                logo=logo_path,
                created_at=datetime.now()
            )
            db.session.add(novo_apoiador)
            db.session.commit()
            flash('Apoiador cadastrado com sucesso!', 'success')
            return redirect(url_for('admin_apoiadores'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar apoiador: {str(e)}', 'error')
            return redirect(url_for('admin_apoiadores_novo'))
    
    return render_template('admin/apoiador_form.html')

@app.route('/admin/apoiadores/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_apoiadores_editar(id):
    apoiador = Apoiador.query.get_or_404(id)
    
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        descricao = request.form.get('descricao', '').strip()
        website = request.form.get('website', '').strip()
        
        # Validações
        if not nome:
            flash('O nome do apoiador é obrigatório!', 'error')
            return redirect(url_for('admin_apoiadores_editar', id=id))
        
        # Processar upload da foto (se uma nova foi enviada)
        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename != '' and allowed_file(file.filename):
                # Remover foto antiga se existir
                if apoiador.logo:
                    old_filepath = os.path.join('static', apoiador.logo)
                    if os.path.exists(old_filepath):
                        try:
                            os.remove(old_filepath)
                        except:
                            pass
                
                upload_folder = app.config['UPLOAD_FOLDER']
                os.makedirs(upload_folder, exist_ok=True)
                
                # Gerar nome único para o arquivo
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4()}_{filename}"
                filepath = os.path.join(upload_folder, unique_filename)
                file.save(filepath)
                
                apoiador.logo = f"images/uploads/{unique_filename}"
            elif file and file.filename != '':
                flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP', 'error')
                return redirect(url_for('admin_apoiadores_editar', id=id))
        
        tipo = request.form.get('tipo', '').strip()
        if not tipo:
            flash('O tipo do apoiador é obrigatório!', 'error')
            return redirect(url_for('admin_apoiadores_editar', id=id))
        
        # Atualizar dados
        apoiador.nome = nome
        apoiador.tipo = tipo
        apoiador.descricao = descricao if descricao else None
        apoiador.website = website if website else None
        
        try:
            db.session.commit()
            flash('Apoiador atualizado com sucesso!', 'success')
            return redirect(url_for('admin_apoiadores'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar apoiador: {str(e)}', 'error')
            return redirect(url_for('admin_apoiadores_editar', id=id))
    
    return render_template('admin/apoiador_form.html', apoiador=apoiador)

@app.route('/admin/apoiadores/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_apoiadores_excluir(id):
    apoiador = Apoiador.query.get_or_404(id)
    
    try:
        # Remover logo se existir
        if apoiador.logo:
            filepath = os.path.join('static', apoiador.logo)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception as e:
                    print(f"Erro ao remover arquivo do logo: {str(e)}")
        
        # Excluir do banco de dados
        db.session.delete(apoiador)
        db.session.commit()
        flash('Apoiador excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir apoiador: {str(e)}', 'error')
        import traceback
        traceback.print_exc()
    
    return redirect(url_for('admin_apoiadores'))

# ============================================
# CRUD - SLIDER (HOME)
# ============================================

@app.route('/admin/slider')
@admin_required
def admin_slider():
    slider_images = SliderImage.query.order_by(SliderImage.ordem.asc(), SliderImage.created_at.asc()).all()
    return render_template('admin/slider.html', slider_images=slider_images)

@app.route('/admin/slider/novo', methods=['GET', 'POST'])
@admin_required
def admin_slider_novo():
    if request.method == 'POST':
        titulo = request.form.get('titulo', '').strip()
        link = request.form.get('link', '').strip()
        ordem = request.form.get('ordem', '0')
        ativo = request.form.get('ativo') == 'on'
        
        # Validações
        if not titulo:
            flash('O título da imagem é obrigatório!', 'error')
            return redirect(url_for('admin_slider_novo'))
        
        # Processar upload da imagem
        imagem_path = None
        if 'imagem' in request.files:
            file = request.files['imagem']
            if file and file.filename != '' and allowed_file(file.filename):
                upload_folder = app.config['UPLOAD_FOLDER']
                os.makedirs(upload_folder, exist_ok=True)
                
                # Gerar nome único para o arquivo
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4()}_{filename}"
                filepath = os.path.join(upload_folder, unique_filename)
                file.save(filepath)
                
                imagem_path = f"images/uploads/{unique_filename}"
            elif file and file.filename != '':
                flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP', 'error')
                return redirect(url_for('admin_slider_novo'))
        
        if not imagem_path:
            flash('A imagem é obrigatória!', 'error')
            return redirect(url_for('admin_slider_novo'))
        
        try:
            nova_imagem = SliderImage(
                titulo=titulo,
                imagem=imagem_path,
                link=link if link else None,
                ordem=int(ordem) if ordem else 0,
                ativo=ativo,
                created_at=datetime.now()
            )
            db.session.add(nova_imagem)
            db.session.commit()
            flash('Imagem do slider cadastrada com sucesso!', 'success')
            return redirect(url_for('admin_slider'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar imagem: {str(e)}', 'error')
            return redirect(url_for('admin_slider_novo'))
    
    return render_template('admin/slider_form.html')

@app.route('/admin/slider/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_slider_editar(id):
    slider_image = SliderImage.query.get_or_404(id)
    
    if request.method == 'POST':
        titulo = request.form.get('titulo', '').strip()
        link = request.form.get('link', '').strip()
        ordem = request.form.get('ordem', '0')
        ativo = request.form.get('ativo') == 'on'
        
        # Validações
        if not titulo:
            flash('O título da imagem é obrigatório!', 'error')
            return redirect(url_for('admin_slider_editar', id=id))
        
        # Processar upload da imagem (se uma nova foi enviada)
        if 'imagem' in request.files:
            file = request.files['imagem']
            if file and file.filename != '' and allowed_file(file.filename):
                # Remover imagem antiga se existir
                if slider_image.imagem:
                    old_filepath = os.path.join('static', slider_image.imagem)
                    if os.path.exists(old_filepath):
                        try:
                            os.remove(old_filepath)
                        except:
                            pass
                
                upload_folder = app.config['UPLOAD_FOLDER']
                os.makedirs(upload_folder, exist_ok=True)
                
                # Gerar nome único para o arquivo
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4()}_{filename}"
                filepath = os.path.join(upload_folder, unique_filename)
                file.save(filepath)
                
                slider_image.imagem = f"images/uploads/{unique_filename}"
            elif file and file.filename != '':
                flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP', 'error')
                return redirect(url_for('admin_slider_editar', id=id))
        
        # Atualizar dados
        slider_image.titulo = titulo
        slider_image.link = link if link else None
        slider_image.ordem = int(ordem) if ordem else 0
        slider_image.ativo = ativo
        slider_image.updated_at = datetime.now()
        
        try:
            db.session.commit()
            flash('Imagem do slider atualizada com sucesso!', 'success')
            return redirect(url_for('admin_slider'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar imagem: {str(e)}', 'error')
            return redirect(url_for('admin_slider_editar', id=id))
    
    return render_template('admin/slider_form.html', slider_image=slider_image)

@app.route('/admin/slider/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_slider_excluir(id):
    slider_image = SliderImage.query.get_or_404(id)
    
    try:
        # Remover imagem se existir
        if slider_image.imagem:
            filepath = os.path.join('static', slider_image.imagem)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception as e:
                    print(f"Erro ao remover arquivo da imagem: {str(e)}")
        
        # Excluir do banco de dados
        db.session.delete(slider_image)
        db.session.commit()
        flash('Imagem do slider excluída com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir imagem: {str(e)}', 'error')
        import traceback
        traceback.print_exc()
    
    return redirect(url_for('admin_slider'))

# ============================================
# CRUD - INFORMATIVOS
# ============================================

@app.route('/admin/informativos')
@admin_required
def admin_informativos():
    informativos = Informativo.query.order_by(Informativo.data_publicacao.desc(), Informativo.created_at.desc()).all()
    return render_template('admin/informativos.html', informativos=informativos)

@app.route('/admin/informativos/novo', methods=['GET', 'POST'])
@admin_required
def admin_informativos_novo():
    if request.method == 'POST':
        try:
            tipo = request.form.get('tipo')
            titulo = request.form.get('titulo')
            subtitulo = request.form.get('subtitulo')
            conteudo = request.form.get('conteudo')
            url_soundcloud = request.form.get('url_soundcloud')
            data_publicacao_str = request.form.get('data_publicacao')
            
            # Validações
            if not tipo or tipo not in ['Noticia', 'Podcast']:
                flash('Tipo inválido! Deve ser Noticia ou Podcast.', 'error')
                return redirect(url_for('admin_informativos_novo'))
            
            if not titulo:
                flash('Título é obrigatório!', 'error')
                return redirect(url_for('admin_informativos_novo'))
            
            if tipo == 'Noticia' and not conteudo:
                flash('Conteúdo é obrigatório para notícias!', 'error')
                return redirect(url_for('admin_informativos_novo'))
            
            if tipo == 'Podcast' and not url_soundcloud:
                flash('URL do SoundCloud é obrigatória para podcasts!', 'error')
                return redirect(url_for('admin_informativos_novo'))
            
            # Processar data de publicação
            data_publicacao = datetime.strptime(data_publicacao_str, "%Y-%m-%d").date() if data_publicacao_str else date.today()
            
            # Processar upload da imagem (apenas para notícias)
            imagem_path = None
            if tipo == 'Noticia' and 'imagem' in request.files:
                file = request.files['imagem']
                if file and file.filename != '' and allowed_file(file.filename):
                    upload_folder = app.config['UPLOAD_FOLDER']
                    os.makedirs(upload_folder, exist_ok=True)
                    
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    filepath = os.path.join(upload_folder, unique_filename)
                    file.save(filepath)
                    
                    imagem_path = f"images/uploads/{unique_filename}"
                elif file and file.filename != '':
                    flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP', 'error')
                    return redirect(url_for('admin_informativos_novo'))
            
            informativo = Informativo(
                tipo=tipo,
                titulo=titulo,
                subtitulo=subtitulo if subtitulo else None,
                conteudo=conteudo if tipo == 'Noticia' else None,
                url_soundcloud=url_soundcloud if tipo == 'Podcast' else None,
                imagem=imagem_path,
                data_publicacao=data_publicacao
            )
            db.session.add(informativo)
            db.session.commit()
            flash('Informativo criado com sucesso!', 'success')
            return redirect(url_for('admin_informativos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar informativo: {str(e)}', 'error')
    
    return render_template('admin/informativo_form.html')

@app.route('/admin/informativos/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_informativos_editar(id):
    informativo = Informativo.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            tipo = request.form.get('tipo')
            titulo = request.form.get('titulo')
            subtitulo = request.form.get('subtitulo')
            conteudo = request.form.get('conteudo')
            url_soundcloud = request.form.get('url_soundcloud')
            data_publicacao_str = request.form.get('data_publicacao')
            
            # Validações
            if not tipo or tipo not in ['Noticia', 'Podcast']:
                flash('Tipo inválido! Deve ser Noticia ou Podcast.', 'error')
                return redirect(url_for('admin_informativos_editar', id=id))
            
            if not titulo:
                flash('Título é obrigatório!', 'error')
                return redirect(url_for('admin_informativos_editar', id=id))
            
            if tipo == 'Noticia' and not conteudo:
                flash('Conteúdo é obrigatório para notícias!', 'error')
                return redirect(url_for('admin_informativos_editar', id=id))
            
            if tipo == 'Podcast' and not url_soundcloud:
                flash('URL do SoundCloud é obrigatória para podcasts!', 'error')
                return redirect(url_for('admin_informativos_editar', id=id))
            
            # Processar data de publicação
            data_publicacao = datetime.strptime(data_publicacao_str, "%Y-%m-%d").date() if data_publicacao_str else informativo.data_publicacao
            
            # Processar upload da imagem (apenas para notícias)
            if tipo == 'Noticia' and 'imagem' in request.files:
                file = request.files['imagem']
                if file and file.filename != '' and allowed_file(file.filename):
                    # Remover imagem antiga se existir
                    if informativo.imagem:
                        old_filepath = os.path.join('static', informativo.imagem)
                        if os.path.exists(old_filepath):
                            try:
                                os.remove(old_filepath)
                            except:
                                pass
                    
                    upload_folder = app.config['UPLOAD_FOLDER']
                    os.makedirs(upload_folder, exist_ok=True)
                    
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    filepath = os.path.join(upload_folder, unique_filename)
                    file.save(filepath)
                    
                    informativo.imagem = f"images/uploads/{unique_filename}"
                elif file and file.filename != '':
                    flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP', 'error')
                    return redirect(url_for('admin_informativos_editar', id=id))
            elif tipo == 'Podcast' and informativo.imagem:
                # Remover imagem se mudou de Noticia para Podcast
                old_filepath = os.path.join('static', informativo.imagem)
                if os.path.exists(old_filepath):
                    try:
                        os.remove(old_filepath)
                    except:
                        pass
                informativo.imagem = None
            
            informativo.tipo = tipo
            informativo.titulo = titulo
            informativo.subtitulo = subtitulo if subtitulo else None
            informativo.conteudo = conteudo if tipo == 'Noticia' else None
            informativo.url_soundcloud = url_soundcloud if tipo == 'Podcast' else None
            informativo.data_publicacao = data_publicacao
            
            db.session.commit()
            flash('Informativo atualizado com sucesso!', 'success')
            return redirect(url_for('admin_informativos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar informativo: {str(e)}', 'error')
    
    return render_template('admin/informativo_form.html', informativo=informativo)

@app.route('/admin/informativos/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_informativos_excluir(id):
    informativo = Informativo.query.get_or_404(id)
    try:
        # Remover imagem se existir
        if informativo.imagem:
            filepath = os.path.join('static', informativo.imagem)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception as e:
                    print(f"Erro ao remover arquivo da imagem: {str(e)}")
        
        # Remover PDF se existir (apenas se atributo estiver presente)
        arquivo_pdf = getattr(informativo, 'arquivo_pdf', None)
        if arquivo_pdf:
            pdf_filepath = os.path.join('static', arquivo_pdf)
            if os.path.exists(pdf_filepath):
                try:
                    os.remove(pdf_filepath)
                except Exception as e:
                    print(f"Erro ao remover arquivo PDF: {str(e)}")
        
        # Excluir do banco de dados
        db.session.delete(informativo)
        db.session.commit()
        flash('Informativo excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir informativo: {str(e)}', 'error')
        import traceback
        traceback.print_exc()
    return redirect(url_for('admin_informativos'))

# ============================================
# CRUD - RÁDIO AADVITA
# ============================================

@app.route('/admin/radio')
@admin_required
def admin_radio():
    programas = RadioPrograma.query.order_by(RadioPrograma.ordem.asc(), RadioPrograma.created_at.desc()).all()
    # Buscar configuração da rádio, criar uma padrão se não existir
    radio_config = RadioConfig.query.first()
    if not radio_config:
        radio_config = RadioConfig(url_streaming_principal='https://stream.zeno.fm/tngw1dzf8zquv')
        db.session.add(radio_config)
        db.session.commit()
    return render_template('admin/radio.html', programas=programas, radio_config=radio_config)

@app.route('/admin/radio/novo', methods=['GET', 'POST'])
@admin_required
def admin_radio_novo():
    if request.method == 'POST':
        try:
            nome = request.form.get('nome')
            descricao = request.form.get('descricao')
            apresentador = request.form.get('apresentador')
            horario = request.form.get('horario')
            url_streaming = request.form.get('url_streaming')
            url_arquivo = request.form.get('url_arquivo')
            ativo = request.form.get('ativo') == 'on'
            ordem_str = request.form.get('ordem', '0')
            
            # Validações
            if not nome:
                flash('Nome do programa é obrigatório!', 'error')
                return redirect(url_for('admin_radio_novo'))
            
            ordem = int(ordem_str) if ordem_str.isdigit() else 0
            
            # Processar upload da imagem
            imagem_path = None
            if 'imagem' in request.files:
                file = request.files['imagem']
                if file and file.filename != '' and allowed_file(file.filename):
                    upload_folder = app.config['UPLOAD_FOLDER']
                    os.makedirs(upload_folder, exist_ok=True)
                    
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    filepath = os.path.join(upload_folder, unique_filename)
                    file.save(filepath)
                    
                    imagem_path = f"images/uploads/{unique_filename}"
                elif file and file.filename != '':
                    flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP', 'error')
                    return redirect(url_for('admin_radio_novo'))
            
            programa = RadioPrograma(
                nome=nome,
                descricao=descricao if descricao else None,
                apresentador=apresentador if apresentador else None,
                horario=horario if horario else None,
                url_streaming=url_streaming if url_streaming else None,
                url_arquivo=url_arquivo if url_arquivo else None,
                imagem=imagem_path,
                ativo=ativo,
                ordem=ordem
            )
            db.session.add(programa)
            db.session.commit()
            flash('Programa de rádio criado com sucesso!', 'success')
            return redirect(url_for('admin_radio'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar programa: {str(e)}', 'error')
    
    return render_template('admin/radio_form.html')

@app.route('/admin/radio/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_radio_editar(id):
    programa = RadioPrograma.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            nome = request.form.get('nome')
            descricao = request.form.get('descricao')
            apresentador = request.form.get('apresentador')
            horario = request.form.get('horario')
            url_streaming = request.form.get('url_streaming')
            url_arquivo = request.form.get('url_arquivo')
            ativo = request.form.get('ativo') == 'on'
            ordem_str = request.form.get('ordem', '0')
            
            # Validações
            if not nome:
                flash('Nome do programa é obrigatório!', 'error')
                return redirect(url_for('admin_radio_editar', id=id))
            
            ordem = int(ordem_str) if ordem_str.isdigit() else programa.ordem
            
            # Processar upload da imagem
            if 'imagem' in request.files:
                file = request.files['imagem']
                if file and file.filename != '' and allowed_file(file.filename):
                    # Remover imagem antiga se existir
                    if programa.imagem:
                        old_filepath = os.path.join('static', programa.imagem)
                        if os.path.exists(old_filepath):
                            try:
                                os.remove(old_filepath)
                            except:
                                pass
                    
                    upload_folder = app.config['UPLOAD_FOLDER']
                    os.makedirs(upload_folder, exist_ok=True)
                    
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    filepath = os.path.join(upload_folder, unique_filename)
                    file.save(filepath)
                    
                    programa.imagem = f"images/uploads/{unique_filename}"
                elif file and file.filename != '':
                    flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP', 'error')
                    return redirect(url_for('admin_radio_editar', id=id))
            
            programa.nome = nome
            programa.descricao = descricao if descricao else None
            programa.apresentador = apresentador if apresentador else None
            programa.horario = horario if horario else None
            programa.url_streaming = url_streaming if url_streaming else None
            programa.url_arquivo = url_arquivo if url_arquivo else None
            programa.ativo = ativo
            programa.ordem = ordem
            
            db.session.commit()
            flash('Programa de rádio atualizado com sucesso!', 'success')
            return redirect(url_for('admin_radio'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar programa: {str(e)}', 'error')
    
    return render_template('admin/radio_form.html', programa=programa)

@app.route('/admin/radio/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_radio_excluir(id):
    programa = RadioPrograma.query.get_or_404(id)
    try:
        # Remover imagem se existir
        if programa.imagem:
            filepath = os.path.join('static', programa.imagem)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception as e:
                    print(f"Erro ao remover arquivo da imagem: {str(e)}")
        
        # Excluir do banco de dados
        db.session.delete(programa)
        db.session.commit()
        flash('Programa de rádio excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir programa: {str(e)}', 'error')
        import traceback
        traceback.print_exc()
    return redirect(url_for('admin_radio'))

@app.route('/admin/radio/config', methods=['POST'])
@admin_required
def admin_radio_config():
    try:
        url_streaming_principal = request.form.get('url_streaming_principal')
        
        if not url_streaming_principal:
            flash('URL de streaming é obrigatória!', 'error')
            return redirect(url_for('admin_radio'))
        
        radio_config = RadioConfig.query.first()
        if not radio_config:
            radio_config = RadioConfig(url_streaming_principal=url_streaming_principal)
            db.session.add(radio_config)
        else:
            radio_config.url_streaming_principal = url_streaming_principal
        
        db.session.commit()
        flash('Configuração da rádio atualizada com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao atualizar configuração: {str(e)}', 'error')
    
    return redirect(url_for('admin_radio'))

# ============================================
# CRUD - BANNERS
# ============================================

@app.route('/admin/banners')
@admin_required
def admin_banners():
    banners = Banner.query.order_by(Banner.ordem.asc()).all()
    # Garantir que existam os 3 banners padrão
    tipos_banners = ['Campanhas', 'Apoie-nos', 'Editais']
    cores_padrao = {
        'Campanhas': {'inicio': '#667eea', 'fim': '#764ba2'},
        'Apoie-nos': {'inicio': '#f093fb', 'fim': '#f5576c'},
        'Editais': {'inicio': '#4facfe', 'fim': '#00f2fe'}
    }
    titulos_padrao = {
        'Campanhas': 'Campanhas',
        'Apoie-nos': 'Apoie-nos',
        'Editais': 'Editais'
    }
    descricoes_padrao = {
        'Campanhas': 'Conheça nossas campanhas e participe',
        'Apoie-nos': 'Apoie nossa causa e faça a diferença',
        'Editais': 'Confira nossos editais e oportunidades'
    }
    
    banners_dict = {banner.tipo: banner for banner in banners}
    
    # Criar banners que não existem
    for tipo in tipos_banners:
        if tipo not in banners_dict:
            banner = Banner(
                tipo=tipo,
                titulo=titulos_padrao[tipo],
                descricao=descricoes_padrao[tipo],
                url='',
                cor_gradiente_inicio=cores_padrao[tipo]['inicio'],
                cor_gradiente_fim=cores_padrao[tipo]['fim'],
                ativo=True,
                ordem=tipos_banners.index(tipo)
            )
            db.session.add(banner)
            banners_dict[tipo] = banner
    
    try:
        db.session.commit()
    except:
        db.session.rollback()
    
    # Buscar novamente após criar os que faltam
    banners = Banner.query.order_by(Banner.ordem.asc()).all()
    
    return render_template('admin/banners.html', banners=banners)

@app.route('/admin/banners/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_banners_editar(id):
    banner = Banner.query.get_or_404(id)
    conteudos = BannerConteudo.query.filter_by(banner_id=id).order_by(BannerConteudo.ordem.asc()).all()
    
    if request.method == 'POST':
        try:
            titulo = request.form.get('titulo')
            descricao = request.form.get('descricao')
            url = request.form.get('url')
            cor_gradiente_inicio = request.form.get('cor_gradiente_inicio')
            cor_gradiente_fim = request.form.get('cor_gradiente_fim')
            ativo = request.form.get('ativo') == 'on'
            ordem_str = request.form.get('ordem', '0')
            
            # Validações
            if not titulo:
                flash('Título é obrigatório!', 'error')
                return redirect(url_for('admin_banners_editar', id=id))
            
            ordem = int(ordem_str) if ordem_str.isdigit() else banner.ordem
            
            # Validar cores hexadecimais
            if not cor_gradiente_inicio or not cor_gradiente_inicio.startswith('#'):
                cor_gradiente_inicio = banner.cor_gradiente_inicio
            if not cor_gradiente_fim or not cor_gradiente_fim.startswith('#'):
                cor_gradiente_fim = banner.cor_gradiente_fim
            
            # Processar upload da imagem
            if 'imagem' in request.files:
                file = request.files['imagem']
                if file and file.filename != '' and allowed_file(file.filename):
                    # Remover imagem antiga se existir
                    if banner.imagem:
                        old_filepath = os.path.join('static', banner.imagem)
                        if os.path.exists(old_filepath):
                            try:
                                os.remove(old_filepath)
                            except:
                                pass
                    
                    upload_folder = app.config['UPLOAD_FOLDER']
                    os.makedirs(upload_folder, exist_ok=True)
                    
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    filepath = os.path.join(upload_folder, unique_filename)
                    file.save(filepath)
                    
                    banner.imagem = f"images/uploads/{unique_filename}"
                elif file and file.filename != '':
                    flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP', 'error')
                    return redirect(url_for('admin_banners_editar', id=id))
            
            # Remover imagem se solicitado
            if request.form.get('remover_imagem') == '1':
                if banner.imagem:
                    old_filepath = os.path.join('static', banner.imagem)
                    if os.path.exists(old_filepath):
                        try:
                            os.remove(old_filepath)
                        except:
                            pass
                banner.imagem = None
            
            banner.titulo = titulo
            banner.descricao = descricao if descricao else None
            banner.url = url if url else None
            banner.cor_gradiente_inicio = cor_gradiente_inicio
            banner.cor_gradiente_fim = cor_gradiente_fim
            banner.ativo = ativo
            banner.ordem = ordem
            
            db.session.commit()
            flash('Banner atualizado com sucesso!', 'success')
            return redirect(url_for('admin_banners'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar banner: {str(e)}', 'error')
    
    return render_template('admin/banner_form.html', banner=banner, conteudos=conteudos)

# ============================================
# CRUD - BANNER CONTEUDOS
# ============================================

@app.route('/admin/banners/<int:banner_id>/conteudos/novo', methods=['GET', 'POST'])
@admin_required
def admin_banner_conteudo_novo(banner_id):
    banner = Banner.query.get_or_404(banner_id)
    
    if request.method == 'POST':
        try:
            titulo = request.form.get('titulo')
            conteudo = request.form.get('conteudo')
            ordem_str = request.form.get('ordem', '0')
            ativo = request.form.get('ativo') == 'on'
            
            if not titulo:
                flash('Título é obrigatório!', 'error')
                return redirect(url_for('admin_banner_conteudo_novo', banner_id=banner_id))
            
            ordem = int(ordem_str) if ordem_str.isdigit() else 0
            
            # Processar upload da imagem
            imagem_path = None
            if 'imagem' in request.files:
                file = request.files['imagem']
                if file and file.filename != '' and allowed_file(file.filename):
                    upload_folder = app.config['UPLOAD_FOLDER']
                    os.makedirs(upload_folder, exist_ok=True)
                    
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    filepath = os.path.join(upload_folder, unique_filename)
                    file.save(filepath)
                    
                    imagem_path = f"images/uploads/{unique_filename}"
                elif file and file.filename != '':
                    flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP', 'error')
                    return redirect(url_for('admin_banner_conteudo_novo', banner_id=banner_id))
            
            # Processar upload do PDF
            pdf_path = None
            if 'arquivo_pdf' in request.files:
                file = request.files['arquivo_pdf']
                if file and file.filename != '' and allowed_pdf_file(file.filename):
                    # Criar pasta para PDFs se não existir
                    upload_folder_pdf = os.path.join('static', 'documents', 'banners')
                    os.makedirs(upload_folder_pdf, exist_ok=True)
                    
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    filepath = os.path.join(upload_folder_pdf, unique_filename)
                    file.save(filepath)
                    
                    pdf_path = f"documents/banners/{unique_filename}"
                elif file and file.filename != '':
                    flash('Tipo de arquivo não permitido para PDF. Use apenas arquivos .pdf', 'error')
                    return redirect(url_for('admin_banner_conteudo_novo', banner_id=banner_id))
            
            novo_conteudo = BannerConteudo(
                banner_id=banner_id,
                titulo=titulo,
                conteudo=conteudo if conteudo else None,
                imagem=imagem_path,
                arquivo_pdf=pdf_path,
                ordem=ordem,
                ativo=ativo
            )
            
            db.session.add(novo_conteudo)
            db.session.commit()
            flash('Conteúdo cadastrado com sucesso!', 'success')
            return redirect(url_for('admin_banners_editar', id=banner_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar conteúdo: {str(e)}', 'error')
    
    return render_template('admin/banner_conteudo_form.html', banner=banner, conteudo=None)

@app.route('/admin/banners/conteudos/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_banner_conteudo_editar(id):
    conteudo = BannerConteudo.query.get_or_404(id)
    banner = conteudo.banner
    
    if request.method == 'POST':
        try:
            titulo = request.form.get('titulo')
            conteudo_text = request.form.get('conteudo')
            ordem_str = request.form.get('ordem', '0')
            ativo = request.form.get('ativo') == 'on'
            
            if not titulo:
                flash('Título é obrigatório!', 'error')
                return redirect(url_for('admin_banner_conteudo_editar', id=id))
            
            ordem = int(ordem_str) if ordem_str.isdigit() else conteudo.ordem
            
            # Processar upload da imagem
            if 'imagem' in request.files:
                file = request.files['imagem']
                if file and file.filename != '' and allowed_file(file.filename):
                    # Remover imagem antiga se existir
                    if conteudo.imagem:
                        old_filepath = os.path.join('static', conteudo.imagem)
                        if os.path.exists(old_filepath):
                            try:
                                os.remove(old_filepath)
                            except:
                                pass
                    
                    upload_folder = app.config['UPLOAD_FOLDER']
                    os.makedirs(upload_folder, exist_ok=True)
                    
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    filepath = os.path.join(upload_folder, unique_filename)
                    file.save(filepath)
                    
                    conteudo.imagem = f"images/uploads/{unique_filename}"
                elif file and file.filename != '':
                    flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP', 'error')
                    return redirect(url_for('admin_banner_conteudo_editar', id=id))
            
            # Remover imagem se solicitado
            if request.form.get('remover_imagem') == '1':
                if conteudo.imagem:
                    old_filepath = os.path.join('static', conteudo.imagem)
                    if os.path.exists(old_filepath):
                        try:
                            os.remove(old_filepath)
                        except:
                            pass
                conteudo.imagem = None
            
            # Processar upload do PDF
            if 'arquivo_pdf' in request.files:
                file = request.files['arquivo_pdf']
                if file and file.filename != '' and allowed_pdf_file(file.filename):
                    # Remover PDF antigo se existir
                    if conteudo.arquivo_pdf:
                        old_filepath = os.path.join('static', conteudo.arquivo_pdf)
                        if os.path.exists(old_filepath):
                            try:
                                os.remove(old_filepath)
                            except:
                                pass
                    
                    # Criar pasta para PDFs se não existir
                    upload_folder_pdf = os.path.join('static', 'documents', 'banners')
                    os.makedirs(upload_folder_pdf, exist_ok=True)
                    
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    filepath = os.path.join(upload_folder_pdf, unique_filename)
                    file.save(filepath)
                    
                    conteudo.arquivo_pdf = f"documents/banners/{unique_filename}"
                elif file and file.filename != '':
                    flash('Tipo de arquivo não permitido para PDF. Use apenas arquivos .pdf', 'error')
                    return redirect(url_for('admin_banner_conteudo_editar', id=id))
            
            # Remover PDF se solicitado
            if request.form.get('remover_pdf') == '1':
                if conteudo.arquivo_pdf:
                    old_filepath = os.path.join('static', conteudo.arquivo_pdf)
                    if os.path.exists(old_filepath):
                        try:
                            os.remove(old_filepath)
                        except:
                            pass
                conteudo.arquivo_pdf = None
            
            conteudo.titulo = titulo
            conteudo.conteudo = conteudo_text if conteudo_text else None
            conteudo.ordem = ordem
            conteudo.ativo = ativo
            
            db.session.commit()
            flash('Conteúdo atualizado com sucesso!', 'success')
            return redirect(url_for('admin_banners_editar', id=banner.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar conteúdo: {str(e)}', 'error')
    
    return render_template('admin/banner_conteudo_form.html', banner=banner, conteudo=conteudo)

@app.route('/admin/banners/conteudos/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_banner_conteudo_excluir(id):
    conteudo = BannerConteudo.query.get_or_404(id)
    banner_id = conteudo.banner_id
    
    try:
        # Remover imagem se existir
        if conteudo.imagem:
            filepath = os.path.join('static', conteudo.imagem)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except:
                    pass
        
        # Remover PDF se existir
        if conteudo.arquivo_pdf:
            pdf_filepath = os.path.join('static', conteudo.arquivo_pdf)
            if os.path.exists(pdf_filepath):
                try:
                    os.remove(pdf_filepath)
                except Exception as e:
                    print(f"Erro ao remover arquivo PDF: {str(e)}")
        
        # Excluir do banco de dados
        db.session.delete(conteudo)
        db.session.commit()
        flash('Conteúdo excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir conteúdo: {str(e)}', 'error')
        import traceback
        traceback.print_exc()
    
    return redirect(url_for('admin_banners_editar', id=banner_id))

@app.route('/admin/financeiro')
@admin_required
def admin_financeiro():
    # Gerar mensalidades automaticamente antes de exibir (verifica se faltam)
    try:
        gerar_mensalidades_automaticas()
    except Exception as e:
        print(f"Aviso: Erro ao verificar/gerar mensalidades: {str(e)}")
    
    # Verificar se foi solicitado ver mensalidades de um associado específico
    associado_id = request.args.get('associado_id', type=int)
    
    if associado_id:
        # Mostrar mensalidades do associado específico
        associado = Associado.query.get_or_404(associado_id)
        mensalidades = Mensalidade.query.filter_by(
            associado_id=associado_id
        ).order_by(
            Mensalidade.data_vencimento.asc()
        ).all()
        
        # Estatísticas para o associado
        mensalidades_pendentes = Mensalidade.query.filter_by(associado_id=associado_id, status='pendente').count()
        mensalidades_pagas = Mensalidade.query.filter_by(associado_id=associado_id, status='paga').count()
        total_pendente = db.session.query(db.func.sum(Mensalidade.valor_final)).filter_by(associado_id=associado_id, status='pendente').scalar() or 0
        total_pago = db.session.query(db.func.sum(Mensalidade.valor_final)).filter_by(associado_id=associado_id, status='paga').scalar() or 0
        
        # Buscar mensalidades atrasadas (pendentes com vencimento < hoje)
        hoje = date.today()
        mensalidades_atrasadas = Mensalidade.query.filter(
            Mensalidade.associado_id == associado_id,
            Mensalidade.status == 'pendente',
            Mensalidade.data_vencimento < hoje
        ).all()
        total_atrasadas = len(mensalidades_atrasadas)
        total_valor_atrasadas = sum(float(m.valor_final) for m in mensalidades_atrasadas)
        associados_atrasados = list(set([m.associado for m in mensalidades_atrasadas]))
        
        stats = {
            'mensalidades_pendentes': mensalidades_pendentes,
            'mensalidades_pagas': mensalidades_pagas,
            'total_pendente': float(total_pendente),
            'total_pago': float(total_pago),
            'mensalidades_atrasadas': total_atrasadas,
            'total_atrasadas': total_valor_atrasadas,
            'associados_atrasados': associados_atrasados
        }
        
        return render_template('admin/financeiro.html', 
                             mensalidades=mensalidades, 
                             stats=stats, 
                             associado=associado,
                             view_mode='mensalidades')
    else:
        # Mostrar lista de associados
        associados = Associado.query.filter_by(status='aprovado').order_by(Associado.nome_completo.asc()).all()
        
        # Estatísticas gerais
        mensalidades_pendentes = Mensalidade.query.filter_by(status='pendente').count()
        mensalidades_pagas = Mensalidade.query.filter_by(status='paga').count()
        total_pendente = db.session.query(db.func.sum(Mensalidade.valor_final)).filter_by(status='pendente').scalar() or 0
        total_pago = db.session.query(db.func.sum(Mensalidade.valor_final)).filter_by(status='paga').scalar() or 0
        
        # Buscar mensalidades atrasadas (pendentes com vencimento < hoje)
        hoje = date.today()
        mensalidades_atrasadas_query = Mensalidade.query.filter(
            Mensalidade.status == 'pendente',
            Mensalidade.data_vencimento < hoje
        ).all()
        total_atrasadas = len(mensalidades_atrasadas_query)
        total_valor_atrasadas = sum(float(m.valor_final) for m in mensalidades_atrasadas_query)
        # Obter associados únicos com mensalidades atrasadas
        associados_ids_atrasados = list(set([m.associado_id for m in mensalidades_atrasadas_query]))
        associados_atrasados = Associado.query.filter(Associado.id.in_(associados_ids_atrasados)).all() if associados_ids_atrasados else []
        
        stats = {
            'mensalidades_pendentes': mensalidades_pendentes,
            'mensalidades_pagas': mensalidades_pagas,
            'total_pendente': float(total_pendente),
            'total_pago': float(total_pago),
            'mensalidades_atrasadas': total_atrasadas,
            'total_atrasadas': total_valor_atrasadas,
            'associados_atrasados': associados_atrasados
        }
        
        return render_template('admin/financeiro.html', 
                             associados=associados, 
                             stats=stats,
                             view_mode='associados')

@app.route('/admin/financeiro/associado/<int:id>/configurar', methods=['GET', 'POST'])
@admin_required
def admin_financeiro_configurar_associado(id):
    associado = Associado.query.get_or_404(id)
    
    if request.method == 'POST':
        # Verificar se é para aplicar desconto em mensalidades selecionadas
        if 'aplicar_desconto' in request.form:
            try:
                mensalidades_ids = request.form.getlist('mensalidades_selecionadas')
                desconto_tipo = request.form.get('desconto_tipo') or None
                desconto_valor = float(request.form.get('desconto_valor', '0') or '0')
                
                if not mensalidades_ids:
                    flash('Selecione pelo menos uma mensalidade para aplicar o desconto.', 'warning')
                    return redirect(url_for('admin_financeiro_configurar_associado', id=id))
                
                mensalidades_atualizadas = 0
                for mensalidade_id in mensalidades_ids:
                    mensalidade = Mensalidade.query.get(int(mensalidade_id))
                    if mensalidade and mensalidade.associado_id == associado.id:
                        # Aplicar desconto
                        valor_base = float(mensalidade.valor_base)
                        
                        if desconto_tipo == 'porcentagem':
                            valor_final = valor_base * (1 - desconto_valor / 100)
                        elif desconto_tipo == 'real':
                            valor_final = valor_base - desconto_valor
                        else:
                            valor_final = valor_base
                        
                        valor_final = max(0.0, valor_final)  # Não permite valor negativo
                        
                        mensalidade.desconto_tipo = desconto_tipo
                        mensalidade.desconto_valor = desconto_valor if desconto_tipo else 0.0
                        mensalidade.valor_final = valor_final
                        mensalidades_atualizadas += 1
                
                db.session.commit()
                flash(f'Desconto aplicado em {mensalidades_atualizadas} mensalidade(s) com sucesso!', 'success')
                return redirect(url_for('admin_financeiro_configurar_associado', id=id))
            except Exception as e:
                db.session.rollback()
                flash(f'Erro ao aplicar desconto: {str(e)}', 'error')
        else:
            # Salvar configuração geral
            try:
                valor_mensalidade = request.form.get('valor_mensalidade', '0')
                desconto_tipo = request.form.get('desconto_tipo') or None
                desconto_valor = request.form.get('desconto_valor', '0') or '0'
                ativo = request.form.get('ativo') == 'on'
                novo_dia_vencimento = int(request.form.get('dia_vencimento', '0'))
                
                valor_anterior = associado.valor_mensalidade
                novo_valor_mensalidade = float(valor_mensalidade) if valor_mensalidade else 0.0
                
                # Verificar se o valor foi alterado (comparar valores numéricos, tratando None como 0)
                valor_anterior_float = float(valor_anterior) if valor_anterior else 0.0
                valor_alterado = abs(valor_anterior_float - novo_valor_mensalidade) > 0.01  # Usar tolerância para comparação de float
                
                # Verificar se o dia de vencimento foi alterado
                # Obter dia atual (da primeira mensalidade pendente ou do cadastro)
                dia_atual = None
                primeira_mensalidade = Mensalidade.query.filter_by(
                    associado_id=associado.id
                ).order_by(
                    Mensalidade.data_vencimento.asc()
                ).first()
                
                if primeira_mensalidade:
                    dia_atual = primeira_mensalidade.data_vencimento.day
                elif associado.created_at:
                    data_base = associado.created_at.date() if isinstance(associado.created_at, datetime) else associado.created_at
                    dia_atual = data_base.day
                
                # Detectar se o dia foi alterado
                # Se não há dia atual definido e foi fornecido um novo dia, considera alterado
                # Se há dia atual e é diferente do novo dia fornecido, considera alterado
                dia_alterado = False
                if novo_dia_vencimento > 0:
                    if dia_atual is None:
                        dia_alterado = True
                    elif novo_dia_vencimento != dia_atual:
                        dia_alterado = True
                
                associado.valor_mensalidade = novo_valor_mensalidade
                associado.desconto_tipo = desconto_tipo
                associado.desconto_valor = float(desconto_valor) if desconto_valor else 0.0
                associado.ativo = ativo
                
                # Obter mensalidades selecionadas (se houver)
                mensalidades_ids = request.form.getlist('mensalidades_selecionadas')
                mensalidades_atualizadas = 0
                
                # Se há mensalidades selecionadas
                if mensalidades_ids:
                    # Atualizar apenas as mensalidades selecionadas (mas nunca as pagas)
                    for mensalidade_id in mensalidades_ids:
                        mensalidade = Mensalidade.query.get(int(mensalidade_id))
                        if mensalidade and mensalidade.associado_id == associado.id and mensalidade.status != 'paga':
                            # Atualizar valor_base se o valor foi alterado
                            if valor_alterado:
                                mensalidade.valor_base = novo_valor_mensalidade
                            
                            # Atualizar dia de vencimento se o dia foi alterado
                            if dia_alterado and novo_dia_vencimento > 0:
                                ano = mensalidade.ano_referencia
                                mes = mensalidade.mes_referencia
                                
                                # Verificar se o dia existe no mês
                                ultimo_dia_mes = monthrange(ano, mes)[1]
                                dia_vencimento = min(novo_dia_vencimento, ultimo_dia_mes)
                                
                                # Atualizar data de vencimento
                                nova_data_vencimento = date(ano, mes, dia_vencimento)
                                mensalidade.data_vencimento = nova_data_vencimento
                            
                            # Aplicar desconto e recalcular valor_final
                            valor_base = float(mensalidade.valor_base)
                            desconto_valor_float = float(desconto_valor) if desconto_valor else 0.0
                            
                            if desconto_tipo == 'porcentagem' and desconto_valor_float > 0:
                                valor_final = valor_base * (1 - desconto_valor_float / 100)
                                mensalidade.desconto_tipo = desconto_tipo
                                mensalidade.desconto_valor = desconto_valor_float
                            elif desconto_tipo == 'real' and desconto_valor_float > 0:
                                valor_final = valor_base - desconto_valor_float
                                mensalidade.desconto_tipo = desconto_tipo
                                mensalidade.desconto_valor = desconto_valor_float
                            else:
                                valor_final = valor_base
                                mensalidade.desconto_tipo = None
                                mensalidade.desconto_valor = 0.0
                            
                            valor_final = max(0.0, valor_final)  # Não permite valor negativo
                            mensalidade.valor_final = valor_final
                            mensalidades_atualizadas += 1
                
                # Se NÃO há mensalidades selecionadas mas o valor foi alterado OU o dia foi alterado
                if not mensalidades_ids and ((valor_alterado and novo_valor_mensalidade > 0) or (dia_alterado and novo_dia_vencimento > 0)):
                    # Atualizar todas as mensalidades não pagas (pendentes, atrasadas, canceladas)
                    mensalidades_nao_pagas = Mensalidade.query.filter_by(
                        associado_id=associado.id
                    ).filter(
                        Mensalidade.status != 'paga'
                    ).all()
                    
                    desconto_valor_float = float(desconto_valor) if desconto_valor else 0.0
                    
                    for mensalidade in mensalidades_nao_pagas:
                        # Atualizar valor_base se o valor foi alterado
                        if valor_alterado:
                            mensalidade.valor_base = novo_valor_mensalidade
                        
                        # Atualizar dia de vencimento se o dia foi alterado
                        if dia_alterado and novo_dia_vencimento > 0:
                            ano = mensalidade.ano_referencia
                            mes = mensalidade.mes_referencia
                            
                            # Verificar se o dia existe no mês
                            ultimo_dia_mes = monthrange(ano, mes)[1]
                            dia_vencimento = min(novo_dia_vencimento, ultimo_dia_mes)
                            
                            # Atualizar data de vencimento
                            nova_data_vencimento = date(ano, mes, dia_vencimento)
                            mensalidade.data_vencimento = nova_data_vencimento
                        
                        # Aplicar desconto e recalcular valor_final
                        valor_base = float(mensalidade.valor_base)
                        
                        if desconto_tipo == 'porcentagem' and desconto_valor_float > 0:
                            valor_final = valor_base * (1 - desconto_valor_float / 100)
                            mensalidade.desconto_tipo = desconto_tipo
                            mensalidade.desconto_valor = desconto_valor_float
                        elif desconto_tipo == 'real' and desconto_valor_float > 0:
                            valor_final = valor_base - desconto_valor_float
                            mensalidade.desconto_tipo = desconto_tipo
                            mensalidade.desconto_valor = desconto_valor_float
                        else:
                            valor_final = valor_base
                            mensalidade.desconto_tipo = None
                            mensalidade.desconto_valor = 0.0
                        
                        valor_final = max(0.0, valor_final)  # Não permite valor negativo
                        mensalidade.valor_final = valor_final
                        mensalidades_atualizadas += 1
                
                db.session.commit()
                
                # Se o associado não tinha valor anterior e agora tem, gerar primeira mensalidade
                if (not valor_anterior or valor_anterior <= 0) and associado.valor_mensalidade > 0:
                    try:
                        gerar_primeira_mensalidade(associado)
                    except Exception as e:
                        print(f"Aviso: Erro ao gerar primeira mensalidade: {str(e)}")
                
                mensagem = 'Configuração de mensalidade salva com sucesso!'
                if mensalidades_atualizadas > 0:
                    partes_mensagem = []
                    if valor_alterado and not mensalidades_ids:
                        partes_mensagem.append(f'Valor atualizado em {mensalidades_atualizadas} mensalidade(s) não paga(s)')
                    if dia_alterado and not mensalidades_ids:
                        partes_mensagem.append(f'Dia de vencimento atualizado em {mensalidades_atualizadas} mensalidade(s) não paga(s)')
                    if mensalidades_ids:
                        partes_mensagem.append(f'{mensalidades_atualizadas} mensalidade(s) selecionada(s) atualizada(s)')
                    
                    if partes_mensagem:
                        mensagem += ' ' + '. '.join(partes_mensagem) + '.'
                elif (valor_alterado or dia_alterado) and not mensalidades_ids:
                    # Verificar se há mensalidades não pagas que não foram atualizadas
                    total_nao_pagas = Mensalidade.query.filter_by(
                        associado_id=associado.id
                    ).filter(
                        Mensalidade.status != 'paga'
                    ).count()
                    if total_nao_pagas == 0:
                        mensagem += ' Nenhuma mensalidade não paga encontrada para atualizar.'
                    elif dia_alterado and novo_dia_vencimento > 0:
                        mensagem += f' Atenção: {total_nao_pagas} mensalidade(s) não paga(s) encontrada(s), mas não foram atualizadas. Verifique o sistema.'
                    elif valor_alterado and novo_valor_mensalidade > 0:
                        mensagem += f' Atenção: {total_nao_pagas} mensalidade(s) não paga(s) encontrada(s), mas não foram atualizadas. Verifique o sistema.'
                
                flash(mensagem, 'success')
                return redirect(url_for('admin_financeiro_configurar_associado', id=id))
            except Exception as e:
                db.session.rollback()
                flash(f'Erro ao salvar configuração: {str(e)}', 'error')
    
    # Buscar mensalidades do associado (pendentes e futuras)
    mensalidades = Mensalidade.query.filter_by(
        associado_id=associado.id
    ).filter(
        Mensalidade.status.in_(['pendente', 'paga'])
    ).order_by(
        Mensalidade.data_vencimento.asc()
    ).all()
    
    # Determinar o dia de vencimento atual (prioridade: mensalidades não pagas, depois pagas, depois dia do cadastro)
    dia_vencimento_atual = None
    
    # Primeiro, buscar dia de mensalidades não pagas
    mensalidade_nao_paga = Mensalidade.query.filter_by(
        associado_id=associado.id
    ).filter(
        Mensalidade.status != 'paga'
    ).order_by(
        Mensalidade.data_vencimento.asc()
    ).first()
    
    if mensalidade_nao_paga:
        dia_vencimento_atual = mensalidade_nao_paga.data_vencimento.day
    else:
        # Se não há mensalidades não pagas, buscar das pagas
        mensalidade_paga = Mensalidade.query.filter_by(
            associado_id=associado.id,
            status='paga'
        ).order_by(
            Mensalidade.data_vencimento.asc()
        ).first()
        
        if mensalidade_paga:
            dia_vencimento_atual = mensalidade_paga.data_vencimento.day
        elif associado.created_at:
            # Se não há mensalidades, usar o dia do cadastro
            data_base = associado.created_at.date() if isinstance(associado.created_at, datetime) else associado.created_at
            dia_vencimento_atual = data_base.day
        else:
            dia_vencimento_atual = 5  # Valor padrão
    
    return render_template('admin/financeiro_configurar.html', 
                         associado=associado, 
                         mensalidades=mensalidades,
                         dia_vencimento_atual=dia_vencimento_atual)

@app.route('/admin/financeiro/mensalidade/<int:id>/pagar', methods=['POST'])
@admin_required
def admin_financeiro_marcar_paga(id):
    mensalidade = Mensalidade.query.get_or_404(id)
    associado_id = request.args.get('associado_id', type=int)
    
    try:
        data_pagamento_str = request.form.get('data_pagamento')
        observacoes = request.form.get('observacoes', '')
        
        if data_pagamento_str:
            mensalidade.data_pagamento = datetime.strptime(data_pagamento_str, "%Y-%m-%d").date()
        else:
            mensalidade.data_pagamento = date.today()
        
        mensalidade.status = 'paga'
        mensalidade.observacoes = observacoes
        db.session.commit()
        flash('Mensalidade marcada como paga!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao marcar mensalidade como paga: {str(e)}', 'error')
    
    # Redirecionar mantendo o associado_id se estiver visualizando mensalidades de um associado
    if associado_id:
        return redirect(url_for('admin_financeiro', associado_id=associado_id))
    return redirect(url_for('admin_financeiro'))

def gerar_mensalidades_anuais(associado):
    """
    Gera mensalidades anuais (12 meses) para um associado, começando após a última mensalidade existente.
    Retorna (sucesso, mensagem, ano_gerado)
    """
    # Verificar se o associado tem valor de mensalidade configurado
    if not associado.valor_mensalidade or associado.valor_mensalidade <= 0:
        return False, 'Associado não possui valor de mensalidade configurado.', None
    
    # Buscar a última mensalidade do associado
    ultima_mensalidade = Mensalidade.query.filter_by(
        associado_id=associado.id
    ).order_by(
        Mensalidade.ano_referencia.desc(),
        Mensalidade.mes_referencia.desc()
    ).first()
    
    if not ultima_mensalidade:
        return False, 'Associado não possui mensalidades cadastradas. Use o botão "Gerar Mensalidades do Mês" primeiro.', None
    
    ano_atual = date.today().year
    ultimo_ano = ultima_mensalidade.ano_referencia
    ultimo_mes = ultima_mensalidade.mes_referencia
    
    # Determinar o próximo ano e mês a partir da última mensalidade
    if ultimo_mes == 12:
        proximo_ano = ultimo_ano + 1
        mes_inicio = 1
    else:
        proximo_ano = ultimo_ano
        mes_inicio = ultimo_mes + 1
    
    # Verificar se há mensalidades PENDENTES ou ATRASADAS do associado (qualquer ano)
    # O botão só pode gerar se NÃO houver mensalidades pendentes/atrasadas
    hoje = date.today()
    
    # Buscar todas as mensalidades pendentes do associado
    mensalidades_pendentes = Mensalidade.query.filter_by(
        associado_id=associado.id,
        status='pendente'
    ).all()
    
    # Verificar se há mensalidades atrasadas (pendentes com vencimento passado)
    mensalidades_atrasadas = [m for m in mensalidades_pendentes if m.data_vencimento < hoje]
    
    # Se houver pelo menos 1 mensalidade pendente ou atrasada, bloquear
    if len(mensalidades_pendentes) > 0:
        return False, f'O Associado selecionado tem mensalidades pendentes ou atrasadas, deve pagar todas as mensalidades para poder emitir novas.', None
    
    # Calcular valor final
    valor_final = associado.calcular_valor_final()
    
    # Obter dia base para vencimento (dia do cadastro ou dia da última mensalidade)
    data_base = associado.created_at.date() if isinstance(associado.created_at, datetime) else associado.created_at
    dia_cadastro = data_base.day
    
    # Gerar 12 mensalidades
    mensalidades_geradas = 0
    for i in range(12):
        mes = mes_inicio + i
        ano = proximo_ano
        
        # Ajustar se passar de dezembro
        while mes > 12:
            mes -= 12
            ano += 1
        
        # Verificar se já existe mensalidade para este mês/ano
        mensalidade_existente = Mensalidade.query.filter_by(
            associado_id=associado.id,
            mes_referencia=mes,
            ano_referencia=ano
        ).first()
        
        if mensalidade_existente:
            continue  # Pular se já existe
        
        # Verificar se o dia existe no mês
        ultimo_dia_mes = monthrange(ano, mes)[1]
        dia_vencimento = min(dia_cadastro, ultimo_dia_mes)
        
        # Data de vencimento
        data_vencimento = date(ano, mes, dia_vencimento)
        
        # Criar mensalidade
        mensalidade = Mensalidade(
            associado_id=associado.id,
            valor_base=float(associado.valor_mensalidade),
            desconto_tipo=associado.desconto_tipo,
            desconto_valor=float(associado.desconto_valor) if associado.desconto_valor else 0.0,
            valor_final=valor_final,
            mes_referencia=mes,
            ano_referencia=ano,
            data_vencimento=data_vencimento,
            status='pendente'
        )
        db.session.add(mensalidade)
        mensalidades_geradas += 1
    
    if mensalidades_geradas > 0:
        db.session.commit()
        return True, f'{mensalidades_geradas} mensalidade(s) gerada(s) com sucesso para o associado {associado.nome_completo}!', proximo_ano
    else:
        return False, 'Todas as mensalidades do período já foram geradas.', None

@app.route('/admin/financeiro/gerar', methods=['POST'])
@admin_required
def admin_financeiro_gerar():
    associados_ids = request.form.getlist('associados_selecionados')
    
    try:
        mensalidades_geradas = 0
        associados_com_mensalidade = []
        associados_processados = 0
        hoje = date.today()
        mes_atual = hoje.month
        ano_atual = hoje.year
        
        # Se não há associados selecionados, buscar todos os associados aprovados
        if not associados_ids:
            associados = Associado.query.filter_by(
                status='aprovado',
                ativo=True
            ).filter(Associado.valor_mensalidade > 0).all()
            
            associados_ids = [str(a.id) for a in associados]
        
        for associado_id_str in associados_ids:
            associado = Associado.query.get(int(associado_id_str))
            if associado and associado.status == 'aprovado' and associado.valor_mensalidade and associado.valor_mensalidade > 0:
                associados_processados += 1
                
                # Verificar se já existe mensalidade para este mês/ano
                mensalidade_existente = Mensalidade.query.filter_by(
                    associado_id=associado.id,
                    mes_referencia=mes_atual,
                    ano_referencia=ano_atual
                ).first()
                
                if mensalidade_existente:
                    associados_com_mensalidade.append(associado.nome_completo)
                    continue  # Pular este associado, já tem mensalidade do mês
                
                # Calcular valor final
                valor_final = associado.calcular_valor_final()
                
                # Obter dia base para vencimento (dia do cadastro)
                data_base = associado.created_at.date() if isinstance(associado.created_at, datetime) else associado.created_at
                dia_cadastro = data_base.day
                
                # Verificar se o dia existe no mês
                ultimo_dia_mes = monthrange(ano_atual, mes_atual)[1]
                dia_vencimento = min(dia_cadastro, ultimo_dia_mes)
                
                # Data de vencimento
                data_vencimento = date(ano_atual, mes_atual, dia_vencimento)
                
                # Se a data já passou, usar o próximo mês
                if hoje > data_vencimento:
                    if mes_atual == 12:
                        mes_vencimento = 1
                        ano_vencimento = ano_atual + 1
                    else:
                        mes_vencimento = mes_atual + 1
                        ano_vencimento = ano_atual
                    
                    ultimo_dia_prox_mes = monthrange(ano_vencimento, mes_vencimento)[1]
                    dia_vencimento = min(dia_cadastro, ultimo_dia_prox_mes)
                    data_vencimento = date(ano_vencimento, mes_vencimento, dia_vencimento)
                
                # Criar mensalidade
                mensalidade = Mensalidade(
                    associado_id=associado.id,
                    valor_base=float(associado.valor_mensalidade),
                    desconto_tipo=associado.desconto_tipo,
                    desconto_valor=float(associado.desconto_valor) if associado.desconto_valor else 0.0,
                    valor_final=valor_final,
                    mes_referencia=mes_atual,
                    ano_referencia=ano_atual,
                    data_vencimento=data_vencimento,
                    status='pendente'
                )
                db.session.add(mensalidade)
                mensalidades_geradas += 1
        
        if mensalidades_geradas > 0:
            db.session.commit()
            if associados_com_mensalidade:
                flash(f'{mensalidades_geradas} mensalidade(s) gerada(s) com sucesso!', 'success')
                for nome in associados_com_mensalidade:
                    flash(f'Já existe mensalidade deste mês para o Associado {nome}.', 'warning')
            else:
                flash(f'{mensalidades_geradas} mensalidade(s) gerada(s) com sucesso para {associados_processados} associado(s)!', 'success')
        else:
            if associados_com_mensalidade:
                if len(associados_com_mensalidade) == 1:
                    flash('Já existe mensalidade deste mês para o Associado selecionado.', 'warning')
                else:
                    for nome in associados_com_mensalidade:
                        flash(f'Já existe mensalidade deste mês para o Associado {nome}.', 'warning')
            else:
                flash('Nenhum associado válido encontrado para gerar mensalidades.', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao gerar mensalidades: {str(e)}', 'error')
    
    return redirect(url_for('admin_financeiro'))

@app.route('/admin/financeiro/gerar-anual', methods=['POST'])
@admin_required
def admin_financeiro_gerar_anual():
    associados_ids = request.form.getlist('associados_selecionados')
    
    if not associados_ids:
        flash('Selecione pelo menos um associado para gerar mensalidades anuais.', 'warning')
        return redirect(url_for('admin_financeiro'))
    
    if len(associados_ids) > 1:
        flash('Selecione apenas um associado por vez para gerar mensalidades anuais.', 'warning')
        return redirect(url_for('admin_financeiro'))
    
    associado_id = int(associados_ids[0])
    associado = Associado.query.get_or_404(associado_id)
    
    if associado.status != 'aprovado':
        flash('Apenas associados aprovados podem ter mensalidades geradas.', 'error')
        return redirect(url_for('admin_financeiro'))
    
    try:
        sucesso, mensagem, ano_gerado = gerar_mensalidades_anuais(associado)
        
        if sucesso:
            flash(mensagem, 'success')
        else:
            # Mensagem em laranja (warning) se há mensalidades pendentes/atrasadas
            if 'mensalidades pendentes ou atrasadas' in mensagem.lower():
                flash(mensagem, 'warning')
            elif 'já antecipou' in mensagem.lower():
                flash(mensagem, 'warning')
            else:
                flash(mensagem, 'error')
    except Exception as e:
        flash(f'Erro ao gerar mensalidades anuais: {str(e)}', 'error')
    
    return redirect(url_for('admin_financeiro'))

# Rota para cron job ou tarefa agendada (geração automática mensal)
@app.route('/api/gerar-mensalidades/<token>')
def api_gerar_mensalidades(token):
    """
    Rota para ser chamada por cron job ou tarefa agendada
    Token de segurança: 'aadvita-gerar-mensalidades-2025'
    """
    # Token de segurança simples (em produção, use algo mais seguro)
    if token != 'aadvita-gerar-mensalidades-2025':
        return jsonify({'error': 'Token inválido'}), 401
    
    try:
        mensalidades_geradas = gerar_mensalidades_automaticas()
        return jsonify({
            'success': True,
            'mensalidades_geradas': mensalidades_geradas,
            'data': date.today().strftime('%d/%m/%Y'),
            'mensagem': f'{mensalidades_geradas} mensalidade(s) gerada(s) com sucesso!'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/admin/financeiro/mensalidade/<int:id>/cancelar', methods=['POST'])
@admin_required
def admin_financeiro_cancelar(id):
    mensalidade = Mensalidade.query.get_or_404(id)
    associado_id = request.args.get('associado_id', type=int)
    
    try:
        mensalidade.status = 'cancelada'
        db.session.commit()
        flash('Mensalidade cancelada!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao cancelar mensalidade: {str(e)}', 'error')
    
    # Redirecionar mantendo o associado_id se estiver visualizando mensalidades de um associado
    if associado_id:
        return redirect(url_for('admin_financeiro', associado_id=associado_id))
    return redirect(url_for('admin_financeiro'))

@app.route('/admin/financeiro/mensalidade/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_financeiro_excluir(id):
    mensalidade = Mensalidade.query.get_or_404(id)
    associado_id = request.args.get('associado_id', type=int)
    
    try:
        db.session.delete(mensalidade)
        db.session.commit()
        flash('Mensalidade excluída com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir mensalidade: {str(e)}', 'error')
    
    # Redirecionar mantendo o associado_id se estiver visualizando mensalidades de um associado
    if associado_id:
        return redirect(url_for('admin_financeiro', associado_id=associado_id))
    return redirect(url_for('admin_financeiro'))

@app.route('/admin/financeiro/mensalidades/marcar-paga-lote', methods=['POST'])
@admin_required
def admin_financeiro_marcar_paga_lote():
    associado_id = request.args.get('associado_id', type=int)
    mensalidades_ids = request.form.getlist('mensalidades_selecionadas')
    
    if not mensalidades_ids:
        flash('Selecione pelo menos uma mensalidade.', 'warning')
        if associado_id:
            return redirect(url_for('admin_financeiro', associado_id=associado_id))
        return redirect(url_for('admin_financeiro'))
    
    try:
        data_pagamento_str = request.form.get('data_pagamento')
        observacoes = request.form.get('observacoes', '')
        
        if data_pagamento_str:
            data_pagamento = datetime.strptime(data_pagamento_str, "%Y-%m-%d").date()
        else:
            data_pagamento = date.today()
        
        mensalidades_atualizadas = 0
        for mensalidade_id in mensalidades_ids:
            mensalidade = Mensalidade.query.get(int(mensalidade_id))
            if mensalidade and mensalidade.status != 'paga':
                mensalidade.data_pagamento = data_pagamento
                mensalidade.status = 'paga'
                if observacoes:
                    mensalidade.observacoes = observacoes
                mensalidades_atualizadas += 1
        
        db.session.commit()
        flash(f'{mensalidades_atualizadas} mensalidade(s) marcada(s) como paga(s)!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao marcar mensalidades como pagas: {str(e)}', 'error')
    
    if associado_id:
        return redirect(url_for('admin_financeiro', associado_id=associado_id))
    return redirect(url_for('admin_financeiro'))

@app.route('/admin/financeiro/mensalidades/cancelar-lote', methods=['POST'])
@admin_required
def admin_financeiro_cancelar_lote():
    associado_id = request.args.get('associado_id', type=int)
    mensalidades_ids = request.form.getlist('mensalidades_selecionadas')
    
    if not mensalidades_ids:
        flash('Selecione pelo menos uma mensalidade.', 'warning')
        if associado_id:
            return redirect(url_for('admin_financeiro', associado_id=associado_id))
        return redirect(url_for('admin_financeiro'))
    
    try:
        mensalidades_canceladas = 0
        for mensalidade_id in mensalidades_ids:
            mensalidade = Mensalidade.query.get(int(mensalidade_id))
            if mensalidade and mensalidade.status != 'paga' and mensalidade.status != 'cancelada':
                mensalidade.status = 'cancelada'
                mensalidades_canceladas += 1
        
        db.session.commit()
        flash(f'{mensalidades_canceladas} mensalidade(s) cancelada(s)!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao cancelar mensalidades: {str(e)}', 'error')
    
    if associado_id:
        return redirect(url_for('admin_financeiro', associado_id=associado_id))
    return redirect(url_for('admin_financeiro'))

@app.route('/admin/financeiro/mensalidades/excluir-lote', methods=['POST'])
@admin_required
def admin_financeiro_excluir_lote():
    associado_id = request.args.get('associado_id', type=int)
    mensalidades_ids = request.form.getlist('mensalidades_selecionadas')
    
    if not mensalidades_ids:
        flash('Selecione pelo menos uma mensalidade.', 'warning')
        if associado_id:
            return redirect(url_for('admin_financeiro', associado_id=associado_id))
        return redirect(url_for('admin_financeiro'))
    
    try:
        mensalidades_excluidas = 0
        for mensalidade_id in mensalidades_ids:
            mensalidade = Mensalidade.query.get(int(mensalidade_id))
            if mensalidade and mensalidade.status != 'paga':
                db.session.delete(mensalidade)
                mensalidades_excluidas += 1
        
        db.session.commit()
        flash(f'{mensalidades_excluidas} mensalidade(s) excluída(s) com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir mensalidades: {str(e)}', 'error')
    
    if associado_id:
        return redirect(url_for('admin_financeiro', associado_id=associado_id))
    return redirect(url_for('admin_financeiro'))

# ============================================
# ROTAS PÚBLICAS
# ============================================

@app.route('/')
def index():
    # Buscar as reuniões presenciais ordenadas pela data mais atual primeiro
    reuniones_presenciales = ReunionPresencial.query.order_by(
        ReunionPresencial.fecha.desc()
    ).limit(3).all()
    
    # Buscar as próximas reuniões virtuais ordenadas pela mais recente cadastrada primeiro
    reuniones_virtuales = ReunionVirtual.query.order_by(
        ReunionVirtual.created_at.desc()
    ).limit(3).all()
    
    projetos = Projeto.query.order_by(Projeto.created_at.desc()).limit(3).all()
    acoes = Acao.query.order_by(Acao.data.desc()).limit(3).all()
    videos = Video.query.order_by(Video.ordem.desc(), Video.created_at.desc()).limit(3).all()
    # Buscar eventos ordenados pela data do evento (mais recentes primeiro)
    eventos = Evento.query.order_by(Evento.data.desc()).limit(3).all()
    # Buscar apoiadores com logo
    apoiadores = Apoiador.query.filter(Apoiador.logo != None, Apoiador.logo != '').order_by(Apoiador.nome.asc()).all()
    
    # Buscar banners ativos
    banners = Banner.query.filter_by(ativo=True).order_by(Banner.ordem.asc()).all()
    # Criar dicionário para facilitar acesso
    banners_dict = {banner.tipo: banner for banner in banners}
    
    # Buscar serviços "O que fazemos" ativos, organizados por coluna e ordem
    servicos_o_que_fazemos = OQueFazemosServico.query.filter_by(ativo=True).order_by(
        OQueFazemosServico.coluna.asc(), 
        OQueFazemosServico.ordem.asc()
    ).all()
    # Organizar serviços por coluna
    servicos_por_coluna = {1: [], 2: [], 3: []}
    for servico in servicos_o_que_fazemos:
        if servico.coluna in servicos_por_coluna:
            servicos_por_coluna[servico.coluna].append(servico)
    
    # Buscar imagens do slider ativas, ordenadas por ordem
    slider_images = SliderImage.query.filter_by(ativo=True).order_by(SliderImage.ordem.asc(), SliderImage.created_at.asc()).all()
    
    # Buscar URL do Instagram para widget
    footer_configs = {}
    for config in Configuracao.query.filter(Configuracao.chave.like('footer_%')).all():
        footer_configs[config.chave] = config.valor
    instagram_url = footer_configs.get('footer_instagram', '')
    
    # Extrair username do Instagram para o widget
    instagram_username = ''
    if instagram_url:
        username_match = re.search(r'instagram\.com/([^/?]+)', instagram_url)
        if username_match:
            instagram_username = username_match.group(1)
    
    # Buscar posts do Instagram ativos (últimos 6)
    instagram_posts = InstagramPost.query.filter_by(ativo=True).order_by(InstagramPost.data_post.desc(), InstagramPost.ordem.asc()).limit(6).all()
    
    # Se houver URL do Instagram configurada, tentar atualizar posts periodicamente
    if instagram_url and instagram_username:
        # Se não houver posts OU se os posts são antigos (mais de 3 dias), tentar atualizar
        precisa_atualizar = False
        if not instagram_posts or len(instagram_posts) == 0:
            precisa_atualizar = True
        elif instagram_posts and len(instagram_posts) > 0:
            # Verificar se o post mais recente tem mais de 3 dias
            try:
                post_mais_recente = instagram_posts[0]
                if post_mais_recente.data_post and post_mais_recente.data_post < datetime.utcnow() - timedelta(days=3):
                    precisa_atualizar = True
            except:
                # Se houver erro ao verificar data, tentar atualizar
                precisa_atualizar = True
        
        # Tentar atualizar em background (não bloquear a página)
        if precisa_atualizar:
            try:
                # Buscar posts do Instagram automaticamente
                print(f"[Instagram] Atualizando posts para @{instagram_username}...")
                posts_cadastrados = buscar_posts_instagram(instagram_username, instagram_url)
                print(f"[Instagram] Posts atualizados: {posts_cadastrados}")
                # Buscar novamente após atualizar
                instagram_posts = InstagramPost.query.filter_by(ativo=True).order_by(InstagramPost.data_post.desc(), InstagramPost.ordem.asc()).limit(6).all()
                print(f"[Instagram] Total de posts recuperados: {len(instagram_posts)}")
            except Exception as e:
                # Log do erro mas não bloquear a página - usar posts existentes
                error_msg = str(e)
                print(f"[Instagram] ERRO ao atualizar posts: {error_msg}")
                import traceback
                traceback.print_exc()
                # Garantir que sempre tenha posts para exibir (mesmo que antigos)
                if not instagram_posts or len(instagram_posts) == 0:
                    instagram_posts = InstagramPost.query.filter_by(ativo=True).order_by(InstagramPost.data_post.desc(), InstagramPost.ordem.asc()).limit(6).all()
                    print(f"[Instagram] Usando posts existentes: {len(instagram_posts)} posts")
    
    return render_template('index.html',
                         reuniones_presenciales=reuniones_presenciales,
                         reuniones_virtuales=reuniones_virtuales,
                         projetos=projetos,
                         eventos=eventos,
                         acoes=acoes,
                         instagram_url=instagram_url,
                         instagram_username=instagram_username,
                         instagram_posts=instagram_posts,
                         videos=videos,
                         apoiadores=apoiadores,
                         banners=banners_dict,
                         servicos_o_que_fazemos=servicos_por_coluna,
                         slider_images=slider_images)

@app.route('/agenda-presencial')
def agenda_presencial():
    reuniones = ReunionPresencial.query.order_by(ReunionPresencial.fecha.desc()).all()
    return render_template('agenda_presencial.html', reuniones=reuniones)

@app.route('/agenda-virtual')
def agenda_virtual():
    reuniones = ReunionVirtual.query.order_by(ReunionVirtual.fecha.desc()).all()
    return render_template('agenda_virtual.html', reuniones=reuniones)

@app.route('/projetos')
def projetos():
    projetos = Projeto.query.order_by(Projeto.data_inicio.desc(), Projeto.created_at.desc()).all()
    return render_template('projetos.html', projetos=projetos)

@app.route('/projetos/<int:id>')
def projeto(id):
    projeto = Projeto.query.get_or_404(id)
    return render_template('projeto.html', projeto=projeto)

@app.route('/acoes')
def acoes():
    current_lang = session.get('language', 'pt')
    acoes = Acao.query.order_by(Acao.data.desc()).all()
    
    # Função auxiliar para obter título do álbum no idioma correto
    def get_titulo_album(album):
        if current_lang == 'es' and album.titulo_es:
            return album.titulo_es
        elif current_lang == 'en' and album.titulo_en:
            return album.titulo_en
        return album.titulo_pt
    
    return render_template('acoes.html', acoes=acoes, get_titulo_album=get_titulo_album, current_lang=current_lang)

@app.route('/apoiadores')
def apoiadores():
    apoiadores = Apoiador.query.order_by(Apoiador.nome.asc()).all()
    return render_template('apoiadores.html', apoiadores=apoiadores)

@app.route('/informativo')
def informativo():
    tipo_filtro = request.args.get('tipo', 'todos')  # 'todos', 'Noticia', 'Podcast'
    
    query = Informativo.query.order_by(Informativo.data_publicacao.desc(), Informativo.created_at.desc())
    
    if tipo_filtro != 'todos':
        query = query.filter_by(tipo=tipo_filtro)
    
    informativos = query.all()
    
    # Separar notícias e podcasts
    noticias = [info for info in informativos if info.tipo == 'Noticia']
    podcasts = [info for info in informativos if info.tipo == 'Podcast']
    
    return render_template('informativo.html', informativos=informativos, noticias=noticias, podcasts=podcasts, tipo_filtro=tipo_filtro)

@app.route('/informativo/<int:id>')
def informativo_detalhe(id):
    informativo = Informativo.query.get_or_404(id)
    return render_template('informativo_detalhe.html', informativo=informativo)

@app.route('/radio')
def radio():
    programas = RadioPrograma.query.filter_by(ativo=True).order_by(RadioPrograma.ordem.asc(), RadioPrograma.created_at.desc()).all()
    # Buscar configuração da rádio, criar uma padrão se não existir
    radio_config = RadioConfig.query.first()
    if not radio_config:
        radio_config = RadioConfig(url_streaming_principal='https://stream.zeno.fm/tngw1dzf8zquv')
        db.session.add(radio_config)
        db.session.commit()
    return render_template('radio.html', programas=programas, radio_config=radio_config)

@app.route('/campanhas')
def campanhas():
    banner = Banner.query.filter_by(tipo='Campanhas', ativo=True).first()
    conteudos = []
    if banner:
        conteudos = BannerConteudo.query.filter_by(banner_id=banner.id, ativo=True).order_by(BannerConteudo.ordem.asc()).all()
    return render_template('campanhas.html', banner=banner, conteudos=conteudos)

@app.route('/apoie')
def apoie():
    banner = Banner.query.filter_by(tipo='Apoie-nos', ativo=True).first()
    conteudos = []
    if banner:
        conteudos = BannerConteudo.query.filter_by(banner_id=banner.id, ativo=True).order_by(BannerConteudo.ordem.asc()).all()
    return render_template('apoie.html', banner=banner, conteudos=conteudos)

@app.route('/editais')
def editais():
    banner = Banner.query.filter_by(tipo='Editais', ativo=True).first()
    conteudos = []
    if banner:
        conteudos = BannerConteudo.query.filter_by(banner_id=banner.id, ativo=True).order_by(BannerConteudo.ordem.asc()).all()
    return render_template('editais.html', banner=banner, conteudos=conteudos)

@app.route('/videos')
def videos():
    videos = Video.query.order_by(Video.created_at.desc()).all()
    return render_template('videos.html', videos=videos)

@app.route('/galeria')
def galeria():
    current_lang = session.get('language', 'pt')
    
    # Buscar álbuns ordenados por ordem e data
    albuns = Album.query.order_by(Album.ordem.asc(), Album.created_at.desc()).all()
    
    # Função auxiliar para obter título no idioma correto
    def get_titulo(album):
        if current_lang == 'es' and album.titulo_es:
            return album.titulo_es
        elif current_lang == 'en' and album.titulo_en:
            return album.titulo_en
        return album.titulo_pt
    
    # Função auxiliar para obter descrição no idioma correto
    def get_descricao(album):
        if current_lang == 'es' and album.descricao_es:
            return album.descricao_es
        elif current_lang == 'en' and album.descricao_en:
            return album.descricao_en
        return album.descricao_pt
    
    return render_template('galeria.html', 
                         albuns=albuns,
                         get_titulo=get_titulo,
                         get_descricao=get_descricao,
                         current_lang=current_lang)

@app.route('/galeria/album/<int:id>')
def galeria_album(id):
    current_lang = session.get('language', 'pt')
    album = Album.query.get_or_404(id)
    fotos = AlbumFoto.query.filter_by(album_id=id).order_by(AlbumFoto.ordem.asc(), AlbumFoto.created_at.desc()).all()
    
    # Função auxiliar para obter título no idioma correto
    def get_titulo_foto(foto):
        if current_lang == 'es' and foto.titulo_es:
            return foto.titulo_es
        elif current_lang == 'en' and foto.titulo_en:
            return foto.titulo_en
        return foto.titulo_pt or ''
    
    # Função auxiliar para obter descrição no idioma correto
    def get_descricao_foto(foto):
        if current_lang == 'es' and foto.descricao_es:
            return foto.descricao_es
        elif current_lang == 'en' and foto.descricao_en:
            return foto.descricao_en
        return foto.descricao_pt or ''
    
    # Função auxiliar para obter título do álbum no idioma correto
    def get_titulo_album(album):
        if current_lang == 'es' and album.titulo_es:
            return album.titulo_es
        elif current_lang == 'en' and album.titulo_en:
            return album.titulo_en
        return album.titulo_pt
    
    # Função auxiliar para obter descrição do álbum no idioma correto
    def get_descricao_album(album):
        if current_lang == 'es' and album.descricao_es:
            return album.descricao_es
        elif current_lang == 'en' and album.descricao_en:
            return album.descricao_en
        return album.descricao_pt or ''
    
    return render_template('galeria_album.html',
                         album=album,
                         fotos=fotos,
                         get_titulo_foto=get_titulo_foto,
                         get_descricao_foto=get_descricao_foto,
                         get_titulo_album=get_titulo_album,
                         get_descricao_album=get_descricao_album,
                         current_lang=current_lang)

@app.route('/sobre')
def sobre():
    # Buscar conteúdos do banco
    current_lang = session.get('language', 'pt')
    
    quem_somos = SobreConteudo.query.filter_by(chave='quem_somos').first()
    missao = SobreConteudo.query.filter_by(chave='missao').first()
    valores = SobreConteudo.query.filter_by(chave='valores').first()
    
    # Buscar membros da diretoria e ordenar por hierarquia de cargos
    membros_diretoria_raw = MembroDiretoria.query.all()
    
    # Definir ordem hierárquica dos cargos
    ordem_cargos = {
        'Presidente': 1,
        'Vice-Presidente': 2,
        'Vice Presidente': 2,  # Compatibilidade com nome antigo
        'Primeiro Secretário(a)': 3,
        'Primeiro(a) Secretário(a)': 3,  # Compatibilidade com nome antigo
        'Segundo Secretário(a)': 4,
        'Segundo(a) Secretário(a)': 4,  # Compatibilidade com nome antigo
        'Primeiro Tesoureiro(a)': 5,
        'Tesoureiro(a)': 5,  # Compatibilidade com nome antigo
        'Segundo Tesoureiro(a)': 6,
        'Diretor de Comunicação': 7
    }
    
    # Ordenar membros: primeiro por hierarquia de cargo, depois por ordem de cadastro
    def get_ordem_cargo(membro):
        return ordem_cargos.get(membro.cargo, 99)  # Cargos não listados vão para o final
    
    membros_diretoria = sorted(membros_diretoria_raw, key=lambda m: (get_ordem_cargo(m), m.ordem, m.created_at))
    
    # Buscar membros do conselho fiscal ordenados
    membros_conselho = MembroConselhoFiscal.query.order_by(MembroConselhoFiscal.ordem.asc()).all()
    
    # Função auxiliar para obter conteúdo no idioma correto
    def get_conteudo(conteudo_obj):
        if not conteudo_obj:
            return None
        if current_lang == 'es' and conteudo_obj.conteudo_es:
            return conteudo_obj.conteudo_es
        elif current_lang == 'en' and conteudo_obj.conteudo_en:
            return conteudo_obj.conteudo_en
        return conteudo_obj.conteudo_pt
    
    # Função auxiliar para obter nome no idioma correto
    def get_nome(membro):
        if current_lang == 'es' and membro.nome_es:
            return membro.nome_es
        elif current_lang == 'en' and membro.nome_en:
            return membro.nome_en
        return membro.nome_pt
    
    return render_template('sobre.html',
                         quem_somos_texto=get_conteudo(quem_somos),
                         missao_texto=get_conteudo(missao),
                         valores_texto=get_conteudo(valores),
                         membros_diretoria=membros_diretoria,
                         membros_conselho=membros_conselho,
                         get_nome=get_nome)

@app.route('/transparencia')
def transparencia():
    current_lang = session.get('language', 'pt')
    
    # Buscar dados do banco
    relatorios = RelatorioFinanceiro.query.order_by(RelatorioFinanceiro.ordem.asc(), RelatorioFinanceiro.data_relatorio.desc()).all()
    documentos = EstatutoDocumento.query.order_by(EstatutoDocumento.ordem.asc(), EstatutoDocumento.data_documento.desc()).all()
    prestacoes = PrestacaoConta.query.order_by(PrestacaoConta.ordem.asc(), PrestacaoConta.periodo_inicio.desc()).all()
    informacoes_doacao = InformacaoDoacao.query.order_by(InformacaoDoacao.ordem.asc()).all()
    
    # Função auxiliar para obter texto no idioma correto
    def get_text(obj, field):
        if not obj:
            return None
        if current_lang == 'es' and getattr(obj, f'{field}_es', None):
            return getattr(obj, f'{field}_es')
        elif current_lang == 'en' and getattr(obj, f'{field}_en', None):
            return getattr(obj, f'{field}_en')
        return getattr(obj, f'{field}_pt', None)
    
    return render_template('transparencia.html',
                         relatorios=relatorios,
                         documentos=documentos,
                         prestacoes=prestacoes,
                         informacoes_doacao=informacoes_doacao,
                         get_text=get_text,
                         current_lang=current_lang)

@app.route('/transparencia/relatorios-financeiros')
def relatorios_financeiros():
    current_lang = session.get('language', 'pt')
    
    # Buscar relatórios financeiros cadastrados no admin
    relatorios = RelatorioFinanceiro.query.order_by(RelatorioFinanceiro.ordem.asc(), RelatorioFinanceiro.data_relatorio.desc()).all()
    
    # Função auxiliar para obter texto no idioma correto
    def get_text(obj, field):
        if not obj:
            return None
        if current_lang == 'es' and getattr(obj, f'{field}_es', None):
            return getattr(obj, f'{field}_es')
        elif current_lang == 'en' and getattr(obj, f'{field}_en', None):
            return getattr(obj, f'{field}_en')
        return getattr(obj, f'{field}_pt', None)
    
    return render_template('relatorios_financeiros.html',
                         relatorios=relatorios,
                         get_text=get_text,
                         current_lang=current_lang)

@app.route('/transparencia/estatuto-documentos')
def estatuto_documentos():
    current_lang = session.get('language', 'pt')
    
    # Buscar documentos cadastrados no admin
    documentos = EstatutoDocumento.query.order_by(EstatutoDocumento.ordem.asc(), EstatutoDocumento.data_documento.desc()).all()
    
    # Função auxiliar para obter texto no idioma correto
    def get_text(obj, field):
        if not obj:
            return None
        if current_lang == 'es' and getattr(obj, f'{field}_es', None):
            return getattr(obj, f'{field}_es')
        elif current_lang == 'en' and getattr(obj, f'{field}_en', None):
            return getattr(obj, f'{field}_en')
        return getattr(obj, f'{field}_pt', None)
    
    return render_template('estatuto_documentos.html',
                         documentos=documentos,
                         get_text=get_text,
                         current_lang=current_lang)

@app.route('/transparencia/prestacao-contas')
def prestacao_contas():
    current_lang = session.get('language', 'pt')
    
    # Buscar prestações de contas cadastradas no admin
    prestacoes = PrestacaoConta.query.order_by(PrestacaoConta.ordem.asc(), PrestacaoConta.periodo_inicio.desc()).all()
    
    # Função auxiliar para obter texto no idioma correto
    def get_text(obj, field):
        if not obj:
            return None
        if current_lang == 'es' and getattr(obj, f'{field}_es', None):
            return getattr(obj, f'{field}_es')
        elif current_lang == 'en' and getattr(obj, f'{field}_en', None):
            return getattr(obj, f'{field}_en')
        return getattr(obj, f'{field}_pt', None)
    
    return render_template('prestacao_contas.html',
                         prestacoes=prestacoes,
                         get_text=get_text,
                         current_lang=current_lang)

@app.route('/transparencia/doacoes-recursos')
def doacoes_recursos():
    current_lang = session.get('language', 'pt')
    
    # Buscar informações de doação cadastradas no admin
    informacoes_doacao = InformacaoDoacao.query.order_by(InformacaoDoacao.ordem.asc()).all()
    
    # Função auxiliar para obter texto no idioma correto
    def get_text(obj, field):
        if not obj:
            return None
        if current_lang == 'es' and getattr(obj, f'{field}_es', None):
            return getattr(obj, f'{field}_es')
        elif current_lang == 'en' and getattr(obj, f'{field}_en', None):
            return getattr(obj, f'{field}_en')
        return getattr(obj, f'{field}_pt', None)
    
    return render_template('doacoes_recursos.html',
                         informacoes_doacao=informacoes_doacao,
                         get_text=get_text,
                         current_lang=current_lang)

@app.route('/eventos')
def eventos():
    current_lang = session.get('language', 'pt')
    eventos = Evento.query.order_by(Evento.data.asc()).all()
    
    # Função auxiliar para obter título do álbum no idioma correto
    def get_titulo_album(album):
        if current_lang == 'es' and album.titulo_es:
            return album.titulo_es
        elif current_lang == 'en' and album.titulo_en:
            return album.titulo_en
        return album.titulo_pt
    
    return render_template('eventos.html', eventos=eventos, get_titulo_album=get_titulo_album, current_lang=current_lang)

@app.route('/associe-se', methods=['GET', 'POST'])
def associe_se():
    if request.method == 'POST':
        try:
            data_nascimento_str = request.form.get('data_nascimento')
            senha = request.form.get('senha')
            
            if not senha or len(senha) < 6:
                flash('A senha deve ter no mínimo 6 caracteres', 'error')
                return redirect(url_for('associe_se'))
            
            # Verificar se CPF já existe
            cpf = request.form.get('cpf')
            associado_existente = Associado.query.filter_by(cpf=cpf).first()
            if associado_existente:
                flash('Este CPF já está cadastrado. Entre em contato conosco se precisar de ajuda.', 'error')
                return redirect(url_for('associe_se'))
            
            associado = Associado(
                nome_completo=request.form.get('nome_completo'),
                cpf=cpf,
                data_nascimento=datetime.strptime(data_nascimento_str, "%Y-%m-%d").date(),
                endereco=request.form.get('endereco'),
                telefone=request.form.get('telefone'),
                status='pendente',  # Cadastro público fica pendente de aprovação
                created_at=datetime.now()
            )
            associado.set_password(senha)
            db.session.add(associado)
            db.session.commit()
            flash('Cadastro enviado com sucesso! Seu cadastro será analisado pela administração. Você receberá uma notificação quando for aprovado.', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao realizar cadastro: {str(e)}', 'error')
    
    return render_template('associe_se.html')

@app.route('/entrar', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        tipo = request.form.get('tipo')
        
        if tipo == 'associado':
            cpf = request.form.get('cpf')
            senha = request.form.get('senha')
            
            # Remover formatação do CPF para busca
            cpf_limpo = cpf.replace('.', '').replace('-', '')
            
            associado = Associado.query.filter_by(cpf=cpf).first()
            
            if associado and associado.check_password(senha):
                # Verificar status do associado
                if associado.status == 'pendente':
                    flash('Seu cadastro está aguardando aprovação. Entre em contato com a administração para mais informações.', 'warning')
                    return redirect(url_for('login'))
                elif associado.status == 'negado':
                    flash('Seu cadastro foi negado. Entre em contato com a administração para mais informações.', 'error')
                    return redirect(url_for('login'))
                elif associado.status == 'aprovado':
                    session['associado_logged_in'] = True
                    session['associado_id'] = associado.id
                    session['associado_nome'] = associado.nome_completo
                    session['associado_cpf'] = associado.cpf
                    flash('Login realizado com sucesso!', 'success')
                    return redirect(url_for('associado_dashboard'))
            else:
                flash('CPF ou senha incorretos', 'error')
        else:
            # Redireciona para login do admin
            return redirect(url_for('admin_login'))
    
    return render_template('login.html')

@app.route('/associado/logout')
def associado_logout():
    session.pop('associado_logged_in', None)
    session.pop('associado_id', None)
    session.pop('associado_nome', None)
    session.pop('associado_cpf', None)
    flash('Logout realizado com sucesso!', 'success')
    return redirect(url_for('index'))

@app.route('/associado')
@associado_required
def associado_dashboard():
    associado = Associado.query.get_or_404(session.get('associado_id'))
    
    # Buscar mensalidades do associado ordenadas por vencimento
    mensalidades = Mensalidade.query.filter_by(
        associado_id=associado.id
    ).order_by(
        Mensalidade.data_vencimento.asc()
    ).all()
    
    return render_template('associado/dashboard.html', associado=associado, mensalidades=mensalidades)

@app.route('/associado/perfil', methods=['GET', 'POST'])
@associado_required
def associado_perfil():
    associado = Associado.query.get_or_404(session.get('associado_id'))
    
    if request.method == 'POST':
        try:
            senha = request.form.get('senha')
            senha_atual = request.form.get('senha_atual')
            
            # Verificar senha atual se for alterar senha
            if senha:
                if not senha_atual or not associado.check_password(senha_atual):
                    flash('Senha atual incorreta', 'error')
                    return redirect(url_for('associado_perfil'))
                
                if len(senha) < 6:
                    flash('A nova senha deve ter no mínimo 6 caracteres', 'error')
                    return redirect(url_for('associado_perfil'))
                
                associado.set_password(senha)
            
            # Atualizar outros campos
            data_nascimento_str = request.form.get('data_nascimento')
            associado.nome_completo = request.form.get('nome_completo')
            associado.data_nascimento = datetime.strptime(data_nascimento_str, "%Y-%m-%d").date()
            associado.endereco = request.form.get('endereco')
            associado.telefone = request.form.get('telefone')
            
            db.session.commit()
            session['associado_nome'] = associado.nome_completo
            flash('Perfil atualizado com sucesso!', 'success')
            return redirect(url_for('associado_perfil'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar perfil: {str(e)}', 'error')
    
    return render_template('associado/perfil.html', associado=associado)

@app.route('/associado/carteira')
@associado_required
def associado_carteira():
    associado = Associado.query.get_or_404(session.get('associado_id'))
    
    if not associado.carteira_pdf:
        flash('Carteira de associado não disponível. Entre em contato com o administrador.', 'error')
        return redirect(url_for('associado_dashboard'))
    
    filepath = os.path.join('static', associado.carteira_pdf)
    if not os.path.exists(filepath):
        flash('Arquivo da carteira não encontrado. Entre em contato com o administrador.', 'error')
        return redirect(url_for('associado_dashboard'))
    
    return send_from_directory('static', associado.carteira_pdf, as_attachment=False)

@app.route('/associado/carteira/download')
@associado_required
def associado_carteira_download():
    associado = Associado.query.get_or_404(session.get('associado_id'))
    
    if not associado.carteira_pdf:
        flash('Carteira de associado não disponível. Entre em contato com o administrador.', 'error')
        return redirect(url_for('associado_dashboard'))
    
    filepath = os.path.join('static', associado.carteira_pdf)
    if not os.path.exists(filepath):
        flash('Arquivo da carteira não encontrado. Entre em contato com o administrador.', 'error')
        return redirect(url_for('associado_dashboard'))
    
    return send_from_directory('static', associado.carteira_pdf, as_attachment=True, download_name=f'carteira_associado_{associado.cpf}.pdf')

# Funções auxiliares para upload de imagens
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def allowed_document_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_DOCUMENT_EXTENSIONS']

def allowed_pdf_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'pdf'

# Rota para upload de imagens
@app.route('/upload-imagem', methods=['POST'])
def upload_imagem():
    if 'file' not in request.files:
        flash('Nenhum arquivo selecionado', 'error')
        return redirect(url_for('index'))
    
    file = request.files['file']
    if file.filename == '':
        flash('Nenhum arquivo selecionado', 'error')
        return redirect(url_for('index'))
    
    if file and allowed_file(file.filename):
        # Criar diretório se não existir
        upload_folder = app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        
        # Gerar nome único para o arquivo
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"
        filepath = os.path.join(upload_folder, unique_filename)
        file.save(filepath)
        
        # Salvar no banco de dados
        titulo = request.form.get('titulo', '')
        descricao = request.form.get('descricao', '')
        
        imagem = Imagem(
            titulo=titulo if titulo else filename,
            descricao=descricao,
            filename=unique_filename,
            caminho=f"images/uploads/{unique_filename}"
        )
        db.session.add(imagem)
        db.session.commit()
        
        flash('Imagem enviada com sucesso!', 'success')
    else:
        flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP', 'error')
    
    return redirect(url_for('index'))

# Rota para servir imagens (não necessária se usar static, mas mantida para compatibilidade)
@app.route('/images/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Rota para mudança de idioma
@app.route('/set-language/<lang>')
def set_language(lang):
    if lang in app.config['LANGUAGES'].keys():
        session['language'] = lang
    return redirect(request.referrer or url_for('index'))

# Context processor para disponibilizar variáveis em todos os templates
@app.context_processor
def inject_conf():
    def user_tem_permissao(codigo_permissao):
        """Função helper para verificar permissões nos templates"""
        if not session.get('admin_logged_in'):
            return False
        if session.get('admin_is_super'):
            return True
        usuario_id = session.get('admin_user_id')
        if usuario_id:
            usuario = Usuario.query.get(usuario_id)
            if usuario:
                return usuario.tem_permissao(codigo_permissao)
        return False
    
    # Buscar dados da associação
    try:
        dados_associacao = DadosAssociacao.get_dados()
    except:
        dados_associacao = None
    
    # Buscar configurações do rodapé
    try:
        footer_configs = {}
        for config in Configuracao.query.filter(Configuracao.chave.like('footer_%')).all():
            footer_configs[config.chave] = config.valor
    except:
        footer_configs = {}
    
    return dict(
        current_user=session.get('admin_username'),
        current_language=session.get('language', 'pt'),
        languages=app.config['LANGUAGES'],
        _=_,
        date=date,  # Disponibilizar date para templates
        user_tem_permissao=user_tem_permissao,
        is_super_admin=session.get('admin_is_super', False),
        dados_associacao=dados_associacao,  # Dados da associação para uso nos templates
        footer_configs=footer_configs  # Configurações do rodapé
    )

# API endpoints para obtener datos
@app.route('/api/reuniones-presenciales')
def api_reuniones_presenciales():
    reuniones = ReunionPresencial.query.order_by(ReunionPresencial.fecha.asc()).all()
    return jsonify([{
        'id': r.id,
        'titulo': r.titulo,
        'descripcion': r.descripcion,
        'fecha': r.fecha.strftime('%Y-%m-%d'),
        'hora': r.hora,
        'lugar': r.lugar,
        'direccion': r.direccion
    } for r in reuniones])

@app.route('/api/reuniones-virtuales')
def api_reuniones_virtuales():
    reuniones = ReunionVirtual.query.order_by(ReunionVirtual.fecha.asc()).all()
    return jsonify([{
        'id': r.id,
        'titulo': r.titulo,
        'descripcion': r.descripcion,
        'fecha': r.fecha.strftime('%Y-%m-%d'),
        'hora': r.hora,
        'plataforma': r.plataforma,
        'link': r.link
    } for r in reuniones])

def init_permissoes():
    """Inicializa as permissões do sistema"""
    permissoes_data = [
        # Dashboard
        {'codigo': 'dashboard', 'nome': 'Dashboard', 'descricao': 'Acessar o painel principal', 'categoria': 'Geral'},
        
        # Reuniões
        {'codigo': 'reuniones_presenciales', 'nome': 'Reuniões Presenciais', 'descricao': 'Gerenciar reuniões presenciais', 'categoria': 'Reuniões'},
        {'codigo': 'reuniones_virtuales', 'nome': 'Reuniões Virtuais', 'descricao': 'Gerenciar reuniões virtuais', 'categoria': 'Reuniões'},
        
        # Conteúdo
        {'codigo': 'projetos', 'nome': 'Projetos', 'descricao': 'Gerenciar projetos', 'categoria': 'Conteúdo'},
        {'codigo': 'eventos', 'nome': 'Eventos', 'descricao': 'Gerenciar eventos', 'categoria': 'Conteúdo'},
        {'codigo': 'acoes', 'nome': 'Ações', 'descricao': 'Gerenciar ações', 'categoria': 'Conteúdo'},
        {'codigo': 'albuns', 'nome': 'Álbuns', 'descricao': 'Gerenciar álbuns da galeria', 'categoria': 'Conteúdo'},
        {'codigo': 'imagens', 'nome': 'Imagens', 'descricao': 'Gerenciar imagens', 'categoria': 'Conteúdo'},
        {'codigo': 'videos', 'nome': 'Vídeos', 'descricao': 'Gerenciar vídeos', 'categoria': 'Conteúdo'},
        {'codigo': 'apoiadores', 'nome': 'Apoiadores', 'descricao': 'Gerenciar apoiadores', 'categoria': 'Conteúdo'},
        
        # Associados
        {'codigo': 'associados', 'nome': 'Associados', 'descricao': 'Gerenciar associados', 'categoria': 'Associados'},
        
        # Financeiro
        {'codigo': 'financeiro', 'nome': 'Sistema Financeiro', 'descricao': 'Acessar sistema financeiro', 'categoria': 'Financeiro'},
        {'codigo': 'contas', 'nome': 'Contas - Doações e Gastos', 'descricao': 'Gerenciar doações e gastos', 'categoria': 'Financeiro'},
        
        # Transparência
        {'codigo': 'transparencia', 'nome': 'Transparência', 'descricao': 'Gerenciar página de transparência', 'categoria': 'Transparência'},
        
        # Configurações
        {'codigo': 'sobre', 'nome': 'Página Sobre', 'descricao': 'Gerenciar página sobre', 'categoria': 'Configurações'},
        {'codigo': 'usuarios', 'nome': 'Usuários Administrativos', 'descricao': 'Gerenciar usuários do admin', 'categoria': 'Configurações'},
        {'codigo': 'configuracao', 'nome': 'Configurações Gerais', 'descricao': 'Acessar configurações gerais', 'categoria': 'Configurações'},
    ]
    
    for perm_data in permissoes_data:
        permissao = Permissao.query.filter_by(codigo=perm_data['codigo']).first()
        if not permissao:
            permissao = Permissao(**perm_data)
            db.session.add(permissao)
    
    db.session.commit()

def init_db():
    """Inicializa a base de dados com dados de exemplo"""
    with app.app_context():
        db.create_all()
        
        # Inicializar permissões
        init_permissoes()
        
        # Tentar verificar usuários (pode falhar se a coluna não existir ainda)
        try:
            usuario_count = Usuario.query.count()
        except Exception:
            # Se falhar, provavelmente a coluna is_super_admin não existe
            # Tentar adicionar via SQL direto
            from sqlalchemy import text
            try:
                with db.engine.connect() as conn:
                    # Verificar se a coluna existe
                    result = conn.execute(text("PRAGMA table_info(usuario)"))
                    columns = [row[1] for row in result]
                    if 'is_super_admin' not in columns:
                        conn.execute(text("ALTER TABLE usuario ADD COLUMN is_super_admin BOOLEAN DEFAULT 0"))
                        conn.commit()
                        print("Coluna is_super_admin adicionada ao banco de dados.")
            except Exception as e:
                print(f"Aviso: Não foi possível adicionar coluna automaticamente: {e}")
                print("Execute o script migrate_permissoes.py manualmente.")
            usuario_count = 0
        
        # Se não houver usuários, criar um super admin padrão
        if usuario_count == 0:
            admin = Usuario(
                username='admin',
                nome='Administrador',
                is_super_admin=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print('Usuário admin criado (username: admin, senha: admin123) - ALTERE A SENHA!')
        
        # Marcar o primeiro usuário como super admin se não houver nenhum super admin
        try:
            super_admin_count = Usuario.query.filter_by(is_super_admin=True).count()
            if super_admin_count == 0:
                primeiro_usuario = Usuario.query.first()
                if primeiro_usuario:
                    primeiro_usuario.is_super_admin = True
                    db.session.commit()
                    print(f'Usuário {primeiro_usuario.username} marcado como super admin automaticamente.')
        except Exception as e:
            print(f"Aviso: Não foi possível verificar/atualizar super admins: {e}")
        
        # Verificar se já existem dados no banco (primeira inicialização)
        # Se já houver qualquer dado, não criar dados de exemplo
        has_any_data = (
            ReunionPresencial.query.count() > 0 or
            ReunionVirtual.query.count() > 0 or
            Projeto.query.count() > 0 or
            Acao.query.count() > 0 or
            Evento.query.count() > 0
        )
        
        # Criar dados de exemplo APENAS se não houver NENHUM dado no banco
        if not has_any_data:
            # Reuniones presenciales de ejemplo
            r1 = ReunionPresencial(
                titulo="Assembleia Geral Mensal",
                descripcion="Reunião mensal para discutir atividades e projetos da associação",
                fecha=datetime(2025, 2, 15, 14, 0),
                hora="14:00",
                lugar="Sede da AADVITA",
                direccion="Rua das Flores, 123, Centro"
            )
            db.session.add(r1)
            
            r2 = ReunionPresencial(
                titulo="Workshop de Acessibilidade",
                descripcion="Workshop sobre tecnologias assistivas e acessibilidade para deficientes visuais",
                fecha=datetime(2025, 2, 20, 15, 0),
                hora="15:00",
                lugar="Centro Comunitário",
                direccion="Avenida Principal, 456, Bairro Novo"
            )
            db.session.add(r2)
            
            r3 = ReunionPresencial(
                titulo="Reunião de Planejamento",
                descripcion="Reunião para planejar as próximas atividades e eventos da associação",
                fecha=datetime(2025, 3, 5, 10, 0),
                hora="10:00",
                lugar="Sede da AADVITA",
                direccion="Rua das Flores, 123, Centro"
            )
            db.session.add(r3)
            
            r4 = ReunionPresencial(
                titulo="Palestra sobre Inclusão Digital",
                descripcion="Palestra sobre como a tecnologia pode promover inclusão para pessoas com deficiência visual",
                fecha=datetime(2025, 3, 15, 16, 0),
                hora="16:00",
                lugar="Auditório Municipal",
                direccion="Praça Central, s/n, Centro"
            )
            db.session.add(r4)
            
            # Reuniones virtuales de ejemplo
            rv1 = ReunionVirtual(
                titulo="Workshop de Tecnologia Assistiva",
                descripcion="Workshop sobre ferramentas tecnológicas para deficientes visuais",
                fecha=datetime(2025, 2, 18, 19, 0),
                hora="19:00",
                plataforma="Google Meet",
                link="https://meet.google.com/abc-defg-hij"
            )
            db.session.add(rv1)
            
            rv2 = ReunionVirtual(
                titulo="Oficina de Leitura Digital",
                descripcion="Aprenda a usar leitores de tela e ferramentas de leitura digital",
                fecha=datetime(2025, 2, 25, 20, 0),
                hora="20:00",
                plataforma="Google Meet",
                link="https://meet.google.com/xyz-uvw-rst"
            )
            db.session.add(rv2)
            
            rv3 = ReunionVirtual(
                titulo="Reunião de Acolhimento",
                descripcion="Reunião para acolher novos membros e apresentar a associação",
                fecha=datetime(2025, 3, 8, 18, 30),
                hora="18:30",
                plataforma="Google Meet",
                link="https://meet.google.com/mno-pqr-stu"
            )
            db.session.add(rv3)
            
            rv4 = ReunionVirtual(
                titulo="Palestra sobre Direitos das Pessoas com Deficiência",
                descripcion="Palestra sobre direitos e legislação para pessoas com deficiência visual",
                fecha=datetime(2025, 3, 20, 19, 0),
                hora="19:00",
                plataforma="Google Meet",
                link="https://meet.google.com/ghi-jkl-mno"
            )
            db.session.add(rv4)
            
            # Projetos de exemplo
            p1 = Projeto(
                titulo="Inclusão Digital",
                descripcion="Projeto para capacitar pessoas com deficiência visual no uso de tecnologias assistivas",
                estado="Ativo",
                data_inicio=datetime(2024, 1, 1).date()
            )
            db.session.add(p1)
            
            p2 = Projeto(
                titulo="Acessibilidade em Espaços Públicos",
                descripcion="Projeto voltado para promover melhorias na acessibilidade de espaços públicos para pessoas com deficiência visual",
                estado="Ativo",
                data_inicio=datetime(2024, 3, 1).date()
            )
            db.session.add(p2)
            
            p3 = Projeto(
                titulo="Formação Profissional",
                descripcion="Iniciativa para oferecer cursos e treinamentos profissionais para pessoas com deficiência visual",
                estado="Em Andamento",
                data_inicio=datetime(2024, 5, 1).date()
            )
            db.session.add(p3)
            
            p4 = Projeto(
                titulo="Apoio Educacional",
                descripcion="Projeto de apoio educacional e inclusão escolar para crianças e jovens com deficiência visual",
                estado="Ativo",
                data_inicio=datetime(2024, 2, 1).date()
            )
            db.session.add(p4)
            
            # Ações de ejemplo
            a1 = Acao(
                titulo="Campanha de Conscientização",
                descricao="Campanha para aumentar a conscientização sobre acessibilidade",
                data=datetime(2024, 3, 15).date(),
                categoria="Conscientização"
            )
            db.session.add(a1)
            
            a2 = Acao(
                titulo="Doação de Materiais Educativos",
                descricao="Ação de doação de materiais educativos em braille para escolas da região",
                data=datetime(2024, 4, 10).date(),
                categoria="Educação"
            )
            db.session.add(a2)
            
            a3 = Acao(
                titulo="Parceria com Empresas Locais",
                descricao="Iniciativa para estabelecer parcerias com empresas locais para inclusão de pessoas com deficiência visual",
                data=datetime(2024, 5, 20).date(),
                categoria="Parcerias"
            )
            db.session.add(a3)
            
            a4 = Acao(
                titulo="Workshop de Mobilidade Urbana",
                descricao="Workshop prático sobre técnicas de mobilidade urbana para pessoas com deficiência visual",
                data=datetime(2024, 6, 5).date(),
                categoria="Capacitação"
            )
            db.session.add(a4)
            
            # Apoiadores de ejemplo
            ap1 = Apoiador(
                nome="Empresa Solidária",
                tipo="Empresa",
                website="https://exemplo.com",
                descricao="Empresa parceira que apoia nossos projetos"
            )
            db.session.add(ap1)
            
            # Vídeos de exemplo
            v1 = Video(
                titulo="Apresentação da AADVITA",
                descricao="Conheça mais sobre a Associação de Deficientes Visuais AADVITA e nossos projetos",
                url_youtube="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                categoria="Institucional",
                ordem=1
            )
            db.session.add(v1)
            
            v2 = Video(
                titulo="Tecnologias Assistivas para Deficientes Visuais",
                descricao="Vídeo educativo sobre tecnologias assistivas que facilitam o dia a dia de pessoas com deficiência visual",
                url_youtube="https://www.youtube.com/watch?v=jNQXAC9IVRw",
                categoria="Educacional",
                ordem=2
            )
            db.session.add(v2)
            
            v3 = Video(
                titulo="Inclusão e Acessibilidade",
                descricao="Palestra sobre inclusão e acessibilidade para pessoas com deficiência visual na sociedade",
                url_youtube="https://www.youtube.com/watch?v=9bZkp7q19f0",
                categoria="Conscientização",
                ordem=3
            )
            db.session.add(v3)
            
            # Imagens de exemplo - usando logo existente como placeholder
            img1 = Imagem(
                titulo="Atividade com Membros",
                descricao="Membros da AADVITA participando de uma atividade comunitária",
                filename="logo.png",
                caminho="images/logo.png"
            )
            db.session.add(img1)
            
            img2 = Imagem(
                titulo="Workshop de Tecnologia",
                descricao="Workshop sobre tecnologias assistivas realizado pela associação",
                filename="logo.png",
                caminho="images/logo.png"
            )
            db.session.add(img2)
            
            img3 = Imagem(
                titulo="Evento de Conscientização",
                descricao="Evento público para conscientização sobre deficiência visual",
                filename="logo.png",
                caminho="images/logo.png"
            )
            db.session.add(img3)
            
            img4 = Imagem(
                titulo="Reunião de Planejamento",
                descricao="Equipe da AADVITA em reunião de planejamento de atividades",
                filename="logo.png",
                caminho="images/logo.png"
            )
            db.session.add(img4)
            
            # Eventos de exemplo
            e1 = Evento(
                titulo="Dia da Conscientização sobre Deficiência Visual",
                descricao="Evento especial para promover a conscientização sobre deficiência visual e inclusão",
                data=datetime(2025, 4, 15, 14, 0),
                hora="14:00",
                local="Praça Central",
                endereco="Centro da cidade",
                tipo="Presencial"
            )
            db.session.add(e1)
            
            e2 = Evento(
                titulo="Feira de Inclusão e Acessibilidade",
                descricao="Feira com exposição de tecnologias assistivas e produtos para pessoas com deficiência visual",
                data=datetime(2025, 5, 10, 9, 0),
                hora="09:00",
                local="Centro de Convenções",
                endereco="Avenida das Flores, 500, Centro",
                tipo="Presencial"
            )
            db.session.add(e2)
            
            e3 = Evento(
                titulo="Seminário sobre Tecnologias Assistivas",
                descricao="Seminário online sobre as mais recentes tecnologias assistivas para deficiência visual",
                data=datetime(2025, 6, 20, 19, 0),
                hora="19:00",
                local="Online",
                endereco="Plataforma Google Meet",
                tipo="Virtual",
                link="https://meet.google.com/event-tech"
            )
            db.session.add(e3)
            
            e4 = Evento(
                titulo="Caminhada pela Inclusão",
                descricao="Caminhada comunitária para promover a inclusão e acessibilidade no município",
                data=datetime(2025, 7, 12, 8, 0),
                hora="08:00",
                local="Parque Municipal",
                endereco="Rua da Natureza, s/n",
                tipo="Presencial"
            )
            db.session.add(e4)
            
            db.session.commit()
        
        # NOTA: Código que recriava automaticamente reuniões, projetos, ações, eventos, imagens e vídeos
        # foi removido para garantir que exclusões sejam permanentes.
        # Dados de exemplo são criados apenas na primeira inicialização do banco (quando não há nenhum registro).
        
        # Criar usuário admin padrão se não existir
        if Usuario.query.count() == 0:
            admin = Usuario(
                username='admin',
                nome='Administrador',
            )
            admin.set_password('admin123')  # Senha padrão - altere depois!
            db.session.add(admin)
            db.session.commit()
        
        # Criar configurações padrão do rodapé se não existirem
        configs_default = {
            'footer_email': 'contato@aadvita.org.br',
            'footer_telefone': '(00) 0000-0000',
            'footer_whatsapp': '(00) 00000-0000',
            'footer_whatsapp_link': 'https://wa.me/5500000000000',
            'footer_instagram': 'https://www.instagram.com/aadvita',
            'footer_facebook': 'https://www.facebook.com/aadvita',
            'footer_youtube': '',
            'footer_qrcode': 'images/qrcode.png',
            'footer_copyright_year': '2025'
        }
        
        for chave, valor in configs_default.items():
            if not Configuracao.query.filter_by(chave=chave).first():
                config = Configuracao(chave=chave, valor=valor, tipo='texto')
                db.session.add(config)
        
        db.session.commit()
        
        # Gerar mensalidades automaticamente ao iniciar (se não existirem)
        try:
            gerar_mensalidades_automaticas()
        except Exception as e:
            print(f"Aviso: Erro ao gerar mensalidades automaticamente: {str(e)}")

# Função para inicializar o banco de dados quando necessário
def ensure_db_initialized():
    """Garante que o banco de dados está inicializado"""
    try:
        with app.app_context():
            # Criar todas as tabelas (idempotente - não recria se já existirem)
            db.create_all()
            
            # Verificar se há usuários, se não houver, inicializar dados
            try:
                from sqlalchemy import inspect
                inspector = inspect(db.engine)
                tables = inspector.get_table_names()
                
                if tables and 'usuario' in tables:
                    try:
                        usuario_count = Usuario.query.count()
                        if usuario_count == 0:
                            # Se não houver usuários, inicializar o banco completamente
                            print("Nenhum usuário encontrado. Inicializando banco de dados...")
                            init_db()
                    except Exception as e:
                        print(f"Nota: Erro ao verificar usuários: {e}")
                        # Se não conseguir verificar, tentar inicializar
                        try:
                            init_db()
                        except:
                            pass
            except Exception as e:
                print(f"Nota: Erro ao verificar tabelas: {e}")
                # Tentar inicializar de qualquer forma
                try:
                    init_db()
                except:
                    pass
    except Exception as e:
        print(f"Aviso: Erro ao inicializar banco de dados: {e}")
        # Não falhar a importação se houver erro no banco
        # O banco será inicializado na primeira requisição

# Inicializar banco quando o módulo for importado (para gunicorn)
# Isso garante que as tabelas existam antes do servidor iniciar
# Mas não falha a importação se houver problemas
try:
    ensure_db_initialized()
except Exception as e:
    print(f"Nota: Banco será inicializado na primeira requisição: {e}")
    pass

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)

