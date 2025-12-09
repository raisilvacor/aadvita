from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime, date, timedelta
from calendar import monthrange
import os
import uuid
import qrcode
import re
import base64
import requests
import unicodedata
import threading
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
        database_url = database_url.replace('postgres://', 'postgresql+psycopg://', 1)
    elif database_url.startswith('postgresql://') and '+psycopg' not in database_url:
        # Garantir que usa psycopg (versão 3) ao invés de psycopg2
        database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    print(f"✅ Usando PostgreSQL: {database_url[:50]}...")  # Log parcial da URL por segurança
else:
    # SQLite local - usar caminho absoluto para persistência no Render
    # AVISO: SQLite não persiste no Render! Use PostgreSQL em produção.
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'aadvita.db')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    print("⚠️ AVISO: Usando SQLite local - dados NÃO persistirão no Render!")
    print("⚠️ Configure DATABASE_URL no Render para usar PostgreSQL!")
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

# Safety-net startup migration: ensure certain Postgres columns exist even when
# the process is started directly with `gunicorn app:app` (some hosts ignore
# the Procfile start wrapper). This tries to run the existing migration module
# and — as a fallback — issues an `ALTER TABLE ... IF NOT EXISTS` using the
# SQLAlchemy engine. It runs here before model classes are defined.
def _ensure_associado_foto_base64():
    try:
        # Only attempt for Postgres-like DBs
        uri = app.config.get('SQLALCHEMY_DATABASE_URI', '') or ''
        if uri.startswith('sqlite') or uri == '':
            return

        # First, try to reuse the existing migration script if available
        try:
            import migrate_postgres_associado as _mig_ass
            try:
                print('Startup: running migrate_postgres_associado.migrate()')
                _mig_ass.migrate()
            except Exception as e:
                print('Startup: migrate_postgres_associado.migrate() failed:', e)
        except Exception:
            # migration module not present or import failed — fall back
            pass

        # Reflect columns and add the column if it is missing
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        if 'associado' in tables:
            cols = [c['name'] for c in inspector.get_columns('associado')]
            if 'foto_base64' not in cols:
                print('Startup: foto_base64 column missing — issuing ALTER TABLE')
                with db.engine.connect() as conn:
                    conn.execute(text('ALTER TABLE associado ADD COLUMN IF NOT EXISTS foto_base64 TEXT'))
                    # commit if using transactional DDL
                    try:
                        conn.commit()
                    except Exception:
                        pass
                print('Startup: foto_base64 column ensured')
    except Exception as e:
        print('Startup: error while ensuring associado.foto_base64:', e)


def _ensure_associado_tipo_associado():
    try:
        # Only attempt for Postgres-like DBs
        uri = app.config.get('SQLALCHEMY_DATABASE_URI', '') or ''
        if uri.startswith('sqlite') or uri == '':
            return

        # Reflect columns and add the column if it is missing
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        if 'associado' in tables:
            cols = [c['name'] for c in inspector.get_columns('associado')]
            if 'tipo_associado' not in cols:
                print('Startup: tipo_associado column missing — issuing ALTER TABLE')
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE associado ADD COLUMN IF NOT EXISTS tipo_associado VARCHAR(20) DEFAULT 'contribuinte'"))
                    # commit if using transactional DDL
                    try:
                        conn.commit()
                    except Exception:
                        pass
                print('Startup: tipo_associado column ensured')
    except Exception as e:
        print('Startup: error while ensuring associado.tipo_associado:', e)


def _ensure_descricao_imagem_columns():
    """Garante que a coluna descricao_imagem existe em todas as tabelas que têm imagens"""
    try:
        # Only attempt for Postgres-like DBs
        uri = app.config.get('SQLALCHEMY_DATABASE_URI', '') or ''
        if uri.startswith('sqlite') or uri == '':
            return

        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        # Tabelas que precisam da coluna descricao_imagem
        tables_with_images = [
            'slider_image',
            'acao',
            'evento',
            'projeto',
            'informativo',
            'radio_programa',
            'banner',
            'banner_conteudo',
            'apoiador',
            'acao_foto',
            'evento_foto',
            'album_foto'
        ]
        
        for table_name in tables_with_images:
            if table_name in tables:
                cols = [c['name'] for c in inspector.get_columns(table_name)]
                if 'descricao_imagem' not in cols:
                    print(f'Startup: descricao_imagem column missing in {table_name} — issuing ALTER TABLE')
                    with db.engine.connect() as conn:
                        conn.execute(text(f'ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS descricao_imagem TEXT'))
                        try:
                            conn.commit()
                        except Exception:
                            pass
                    print(f'Startup: descricao_imagem column ensured in {table_name}')
    except Exception as e:
        print('Startup: error while ensuring descricao_imagem columns:', e)


# Run safety-net migration now (before model classes are declared)
try:
    with app.app_context():
        _ensure_associado_foto_base64()
        _ensure_associado_tipo_associado()
        _ensure_descricao_imagem_columns()
except Exception as _:
    # Swallow errors to avoid preventing app import — errors logged above
    pass

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
        'Relatório de Atividades': 'Relatório de Atividades',
        'Acompanhe as atividades realizadas pela associação e os resultados alcançados.': 'Acompanhe as atividades realizadas pela associação e os resultados alcançados.',
        'Nenhum relatório de atividades cadastrado no momento.': 'Nenhum relatório de atividades cadastrado no momento.',
        'Atividades Realizadas:': 'Atividades Realizadas:',
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
        'Nenhum relatório de atividades cadastrado no momento.': 'Nenhum relatório de atividades cadastrado no momento.',
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
        'Relatório de Atividades': 'Informe de Actividades',
        'Acompanhe as atividades realizadas pela associação e os resultados alcançados.': 'Consulta las actividades realizadas por la asociación y los resultados alcanzados.',
        'Nenhum relatório de atividades cadastrado no momento.': 'No hay informes de actividades registrados en este momento.',
        'Atividades Realizadas:': 'Actividades Realizadas:',
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
        'Nenhum relatório de atividades cadastrado no momento.': 'No hay informes de actividades registrados en este momento.',
        'Período:': 'Período:',
        'A partir de': 'A partir de',
        'Recursos Recebidos:': 'Recursos Recibidos:',
        'Resultados Alcançados:': 'Resultados Alcanzados:',
        'Atividades Realizadas:': 'Actividades Realizadas:',
        'Relatório de Atividades': 'Informe de Actividades',
        'Acompanhe as atividades realizadas pela associação e os resultados alcançados.': 'Consulta las actividades realizadas por la asociación y los resultados alcanzados.',
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
        'Radar de Acessibilidade': 'Radar de Accesibilidad',
        'Validar Certificados': 'Validar Certificados',
        'Reciclagem': 'Reciclaje',
        'O que fazemos': 'Lo que hacemos',
        'Associação dos Deficientes Visuais Tapuienses': 'Asociación de Deficientes Visuales Tapuienses',
        'Conheça nossas campanhas e participe.': 'Conoce nuestras campañas y participa.',
        'Sua contribuição transforma vidas!': '¡Tu contribución transforma vidas!',
        'Confira nossos editais e oportunidades.': 'Consulta nuestros editales y oportunidades.',
        'Seja Voluntário': 'Sé Voluntario',
        'Ações principais': 'Acciones principales',
        'Imagem anterior': 'Imagen anterior',
        'Próxima imagem': 'Siguiente imagen',
        'Ir para imagem': 'Ir a imagen',
        'Solicitar Coleta de Reciclagem': 'Solicitar Recolección de Reciclaje',
        'Preencha o formulário abaixo para solicitar a coleta de materiais recicláveis. Nossa equipe entrará em contato em breve.': 'Complete el formulario a continuación para solicitar la recolección de materiales reciclables. Nuestro equipo se pondrá en contacto pronto.',
        'Tipo de Material': 'Tipo de Material',
        'Selecione o tipo de material': 'Seleccione el tipo de material',
        'Ferro': 'Hierro',
        'Alumínio': 'Aluminio',
        'Cobre': 'Cobre',
        'Plástico': 'Plástico',
        'Papel': 'Papel',
        'Papelão': 'Cartón',
        'Nome Completo': 'Nombre Completo',
        'Digite seu nome completo': 'Ingrese su nombre completo',
        'Telefone/WhatsApp': 'Teléfono/WhatsApp',
        'Endereço de Retirada do Material': 'Dirección de Recolección del Material',
        'Digite o endereço completo onde o material deve ser coletado': 'Ingrese la dirección completa donde se debe recolectar el material',
        'Observações': 'Observaciones',
        'Informações adicionais sobre o material ou horários preferenciais para coleta': 'Información adicional sobre el material u horarios preferenciales para la recolección',
        'Enviar Solicitação': 'Enviar Solicitud',
        'Validar Certificado': 'Validar Certificado',
        'Informe o número do certificado (ex: <strong>CERT-7B062C2604</strong>) para verificar a autenticidade.': 'Ingrese el número del certificado (ej: <strong>CERT-7B062C2604</strong>) para verificar la autenticidad.',
        'Número do Certificado': 'Número del Certificado',
        'Validar': 'Validar',
        'Voltar': 'Volver',
        'Certificado válido': 'Certificado válido',
        'O certificado': 'El certificado',
        'é autêntico': 'es auténtico',
        'Beneficiário:': 'Beneficiario:',
        'Curso/Atividade:': 'Curso/Actividad:',
        'Descrição:': 'Descripción:',
        'Data de emissão:': 'Fecha de emisión:',
        'Validade:': 'Validez:',
        'Vitalício': 'Vitalicio',
        'Certificado inválido': 'Certificado inválido',
        'Não encontramos um certificado válido para o código informado.': 'No encontramos un certificado válido para el código proporcionado.',
        'Validar outro certificado': 'Validar otro certificado',
        'Registrar Problema de Acessibilidade': 'Registrar Problema de Accesibilidad',
        'Ajude-nos a mapear os problemas de acessibilidade na cidade. Sua denúncia é importante para cobrarmos melhorias dos órgãos públicos.': 'Ayúdanos a mapear los problemas de accesibilidad en la ciudad. Tu denuncia es importante para exigir mejoras a los órganos públicos.',
        'Tipo de Problema': 'Tipo de Problema',
        'Selecione o tipo de problema': 'Seleccione el tipo de problema',
        'Acessibilidade Urbana': 'Accesibilidad Urbana',
        'Calçada': 'Acera',
        'Faixa de Pedestre': 'Cruce de Peatones',
        'Sinal Sonoro': 'Señal Sonora',
        'Rampa de Acesso': 'Rampa de Acceso',
        'Piso Tátil': 'Piso Táctil',
        'Transporte Público': 'Transporte Público',
        'Estabelecimento Comercial': 'Establecimiento Comercial',
        'Outro': 'Otro',
        'Localização (Endereço)': 'Ubicación (Dirección)',
        'Descrição do Problema': 'Descripción del Problema',
        'Descreva detalhadamente o problema encontrado...': 'Describe detalladamente el problema encontrado...',
        'Seu Nome Completo': 'Tu Nombre Completo',
        'Nome completo': 'Nombre completo',
        'Email (opcional)': 'Correo (opcional)',
        'Anexos (Fotos, documentos) - opcional': 'Anexos (Fotos, documentos) - opcional',
        'Envie fotos ou documentos que ajudem a ilustrar o problema. Tamanho máximo por arquivo: 16MB.': 'Envía fotos o documentos que ayuden a ilustrar el problema. Tamaño máximo por archivo: 16MB.',
        'Enviar Denúncia': 'Enviar Denuncia',
        'Cancelar': 'Cancelar',
        'Fique por dentro das novidades da AADVITA.': 'Mantente al tanto de las novedades de AADVITA.',
        'Ouça nossos podcasts e conteúdos em áudio.': 'Escucha nuestros podcasts y contenidos en audio.',
        'Nenhum serviço cadastrado no momento.': 'Ningún servicio registrado en este momento.',
        'Acessibilidade': 'Accesibilidad',
        'Opções de acessibilidade': 'Opciones de accesibilidad',
        'Tamanho da Fonte': 'Tamaño de la Fuente',
        'Diminuir fonte': 'Disminuir fuente',
        'Aumentar fonte': 'Aumentar fuente',
        'Diminuir': 'Disminuir',
        'Aumentar': 'Aumentar',
        'Contraste': 'Contraste',
        'Alternar contraste': 'Alternar contraste',
        'Alto Contraste': 'Alto Contraste',
        'Alto Contraste Ativo': 'Alto Contraste Activo',
        'Áudio Descrição': 'Descripción de Audio',
        'Áudio Descrição Ativa': 'Descripción de Audio Activa',
        'Alternar áudio descrição': 'Alternar descripción de audio',
        'Redefinir': 'Restablecer',
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
        'Nenhum relatório de atividades cadastrado no momento.': 'No activity reports registered at this time.',
        'Período:': 'Period:',
        'A partir de': 'From',
        'Recursos Recebidos:': 'Resources Received:',
        'Resultados Alcançados:': 'Results Achieved:',
        'Atividades Realizadas:': 'Activities Carried Out:',
        'Relatório de Atividades': 'Activity Report',
        'Acompanhe as atividades realizadas pela associação e os resultados alcançados.': 'Follow the activities carried out by the association and the results achieved.',
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
        'Radar de Acessibilidade': 'Accessibility Radar',
        'Validar Certificados': 'Validate Certificates',
        'Reciclagem': 'Recycling',
        'O que fazemos': 'What We Do',
        'Associação dos Deficientes Visuais Tapuienses': 'Association of Visually Impaired Tapuienses',
        'Conheça nossas campanhas e participe.': 'Learn about our campaigns and participate.',
        'Sua contribuição transforma vidas!': 'Your contribution transforms lives!',
        'Confira nossos editais e oportunidades.': 'Check our public notices and opportunities.',
        'Seja Voluntário': 'Be a Volunteer',
        'Ações principais': 'Main actions',
        'Imagem anterior': 'Previous image',
        'Próxima imagem': 'Next image',
        'Ir para imagem': 'Go to image',
        'Solicitar Coleta de Reciclagem': 'Request Recycling Collection',
        'Preencha o formulário abaixo para solicitar a coleta de materiais recicláveis. Nossa equipe entrará em contato em breve.': 'Fill out the form below to request collection of recyclable materials. Our team will contact you soon.',
        'Tipo de Material': 'Material Type',
        'Selecione o tipo de material': 'Select the material type',
        'Ferro': 'Iron',
        'Alumínio': 'Aluminum',
        'Cobre': 'Copper',
        'Plástico': 'Plastic',
        'Papel': 'Paper',
        'Papelão': 'Cardboard',
        'Nome Completo': 'Full Name',
        'Digite seu nome completo': 'Enter your full name',
        'Telefone/WhatsApp': 'Phone/WhatsApp',
        'Endereço de Retirada do Material': 'Material Pickup Address',
        'Digite o endereço completo onde o material deve ser coletado': 'Enter the complete address where the material should be collected',
        'Observações': 'Observations',
        'Informações adicionais sobre o material ou horários preferenciais para coleta': 'Additional information about the material or preferred collection times',
        'Enviar Solicitação': 'Submit Request',
        'Validar Certificado': 'Validate Certificate',
        'Informe o número do certificado (ex: <strong>CERT-7B062C2604</strong>) para verificar a autenticidade.': 'Enter the certificate number (e.g., <strong>CERT-7B062C2604</strong>) to verify authenticity.',
        'Número do Certificado': 'Certificate Number',
        'Validar': 'Validate',
        'Voltar': 'Back',
        'Certificado válido': 'Valid certificate',
        'O certificado': 'The certificate',
        'é autêntico': 'is authentic',
        'Beneficiário:': 'Beneficiary:',
        'Curso/Atividade:': 'Course/Activity:',
        'Descrição:': 'Description:',
        'Data de emissão:': 'Issue date:',
        'Validade:': 'Validity:',
        'Vitalício': 'Lifetime',
        'Certificado inválido': 'Invalid certificate',
        'Não encontramos um certificado válido para o código informado.': 'We did not find a valid certificate for the code provided.',
        'Validar outro certificado': 'Validate another certificate',
        'Registrar Problema de Acessibilidade': 'Register Accessibility Problem',
        'Ajude-nos a mapear os problemas de acessibilidade na cidade. Sua denúncia é importante para cobrarmos melhorias dos órgãos públicos.': 'Help us map accessibility problems in the city. Your report is important to demand improvements from public agencies.',
        'Tipo de Problema': 'Problem Type',
        'Selecione o tipo de problema': 'Select the problem type',
        'Acessibilidade Urbana': 'Urban Accessibility',
        'Calçada': 'Sidewalk',
        'Faixa de Pedestre': 'Crosswalk',
        'Sinal Sonoro': 'Audio Signal',
        'Rampa de Acesso': 'Access Ramp',
        'Piso Tátil': 'Tactile Floor',
        'Transporte Público': 'Public Transportation',
        'Estabelecimento Comercial': 'Commercial Establishment',
        'Outro': 'Other',
        'Localização (Endereço)': 'Location (Address)',
        'Descrição do Problema': 'Problem Description',
        'Descreva detalhadamente o problema encontrado...': 'Describe in detail the problem found...',
        'Seu Nome Completo': 'Your Full Name',
        'Nome completo': 'Full name',
        'Email (opcional)': 'Email (optional)',
        'Anexos (Fotos, documentos) - opcional': 'Attachments (Photos, documents) - optional',
        'Envie fotos ou documentos que ajudem a ilustrar o problema. Tamanho máximo por arquivo: 16MB.': 'Send photos or documents that help illustrate the problem. Maximum file size: 16MB.',
        'Enviar Denúncia': 'Submit Report',
        'Cancelar': 'Cancel',
        'Fique por dentro das novidades da AADVITA.': 'Stay up to date with AADVITA news.',
        'Ouça nossos podcasts e conteúdos em áudio.': 'Listen to our podcasts and audio content.',
        'Nenhum serviço cadastrado no momento.': 'No services registered at this time.',
        'Acessibilidade': 'Accessibility',
        'Opções de acessibilidade': 'Accessibility options',
        'Tamanho da Fonte': 'Font Size',
        'Diminuir fonte': 'Decrease font',
        'Aumentar fonte': 'Increase font',
        'Diminuir': 'Decrease',
        'Aumentar': 'Increase',
        'Contraste': 'Contrast',
        'Alternar contraste': 'Toggle contrast',
        'Alto Contraste': 'High Contrast',
        'Alto Contraste Ativo': 'High Contrast Active',
        'Áudio Descrição': 'Audio Description',
        'Áudio Descrição Ativa': 'Audio Description Active',
        'Alternar áudio descrição': 'Toggle audio description',
        'Redefinir': 'Reset',
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

# Filtro para limpar tags <br> e converter para quebras de linha, depois aplicar nl2br
@app.template_filter('limpar_br_nl2br')
def limpar_br_nl2br_filter(text):
    """Remove tags <br> e converte para quebras de linha, depois aplica nl2br"""
    from markupsafe import Markup
    if not text:
        return Markup('')
    # Converter todas as variações de <br> para quebras de linha
    import re
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    # Remover outras tags HTML que possam ter sido inseridas
    text = re.sub(r'<[^>]+>', '', text)
    # Aplicar nl2br e marcar como seguro para renderização HTML
    return Markup(text.replace('\n', '<br>'))

# Filtro para converter HTML de volta para texto simples (para edição)
@app.template_filter('html_para_texto')
def html_para_texto_filter(html):
    """Converte HTML de volta para texto simples para edição em textarea"""
    if not html:
        return ''
    import re
    # Remover tags <p> e </p>, substituindo por quebras duplas
    texto = html.replace('</p>', '\n\n').replace('<p>', '')
    # Remover tags <br> e substituir por quebras simples
    texto = re.sub(r'<br\s*/?>', '\n', texto, flags=re.IGNORECASE)
    # Remover outras tags HTML
    texto = re.sub(r'<[^>]+>', '', texto)
    # Limpar espaços extras e quebras de linha
    linhas = [p.strip() for p in texto.split('\n\n') if p.strip()]
    return '\n\n'.join(linhas)

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
    slug = db.Column(db.String(250), unique=True, nullable=True)  # URL amigável
    descripcion = db.Column(db.Text)
    fecha = db.Column(db.DateTime, nullable=False)
    hora = db.Column(db.String(10), nullable=False)
    lugar = db.Column(db.String(300), nullable=False)
    direccion = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ReunionVirtual(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(250), unique=True, nullable=True)  # URL amigável
    descripcion = db.Column(db.Text)
    fecha = db.Column(db.DateTime, nullable=False)
    hora = db.Column(db.String(10), nullable=False)
    plataforma = db.Column(db.String(100), nullable=False)
    link = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Projeto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(250), unique=True, nullable=True)  # URL amigável
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
    imagen = db.Column(db.String(300))  # Caminho da imagem ou 'base64:...'
    imagen_base64 = db.Column(db.Text, nullable=True)  # Imagem em base64 para persistência no Render (opcional)
    descricao_imagem = db.Column(db.Text, nullable=True)  # Descrição da imagem para acessibilidade
    arquivo_pdf = db.Column(db.String(300))  # Caminho do arquivo PDF ou 'base64:application/pdf'
    arquivo_pdf_base64 = db.Column(db.Text, nullable=True)  # PDF em base64 para persistência no Render (opcional)
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
    slug = db.Column(db.String(250), unique=True, nullable=True)  # URL amigável
    descricao = db.Column(db.Text, nullable=False)
    data = db.Column(db.Date, nullable=False)
    categoria = db.Column(db.String(100))
    imagem = db.Column(db.String(300))  # Caminho da imagem ou 'base64:...'
    imagem_base64 = db.Column(db.Text, nullable=True)  # Imagem em base64 para persistência no Render (opcional)
    descricao_imagem = db.Column(db.Text, nullable=True)  # Descrição da imagem para acessibilidade
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
    descricao_imagem = db.Column(db.Text, nullable=True)  # Descrição da imagem para acessibilidade
    ordem = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Apoiador(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(100))  # Empresa, Individual, Instituição
    logo = db.Column(db.String(300))  # Caminho da imagem ou 'base64:...'
    logo_base64 = db.Column(db.Text, nullable=True)  # Imagem em base64 para persistência no Render (opcional)
    descricao_imagem = db.Column(db.Text, nullable=True)  # Descrição da imagem (logo) para acessibilidade
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
    __tablename__ = 'slider_image'
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200))
    imagem = db.Column(db.String(300), nullable=False)  # Caminho da imagem ou 'base64:...'
    imagem_base64 = db.Column(db.Text, nullable=True)  # Imagem em base64 para persistência no Render (opcional)
    descricao_imagem = db.Column(db.Text, nullable=True)  # Descrição da imagem para acessibilidade
    link = db.Column(db.String(500))  # Link clicável (opcional)
    ordem = db.Column(db.Integer, default=0)  # Ordem de exibição
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __mapper_args__ = {
        'confirm_deleted_rows': False
    }
    
    def get_imagem_url(self):
        """Retorna a URL da imagem, seja base64 ou arquivo"""
        try:
            from flask import url_for
            # Verificar se tem imagem_base64 usando getattr (seguro se coluna não existir)
            imagem_base64 = getattr(self, 'imagem_base64', None)
            if imagem_base64:
                return f"/slider/{self.id}/imagem"
            elif self.imagem and 'base64:' in str(self.imagem):
                return f"/slider/{self.id}/imagem"
            elif self.imagem:
                return url_for('static', filename=self.imagem)
            return None
        except Exception as e:
            print(f"Erro em get_imagem_url: {e}")
            try:
                if self.imagem:
                    from flask import url_for
                    return url_for('static', filename=self.imagem)
            except:
                pass
            return None
    
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
    slug = db.Column(db.String(250), unique=True, nullable=True)  # URL amigável
    descricao = db.Column(db.Text)
    data = db.Column(db.DateTime, nullable=False)
    hora = db.Column(db.String(10))
    local = db.Column(db.String(300))
    endereco = db.Column(db.Text)
    tipo = db.Column(db.String(100))  # Presencial, Virtual, Híbrido
    link = db.Column(db.String(500))
    imagem = db.Column(db.String(300))  # Caminho da imagem ou 'base64:...'
    imagem_base64 = db.Column(db.Text, nullable=True)  # Imagem em base64 para persistência no Render (opcional)
    descricao_imagem = db.Column(db.Text, nullable=True)  # Descrição da imagem para acessibilidade
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
    descricao_imagem = db.Column(db.Text, nullable=True)  # Descrição da imagem para acessibilidade
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
    tipo_associado = db.Column(db.String(20), nullable=False, default='contribuinte')  # 'regular' ou 'contribuinte'
    # Campos para mensalidade
    valor_mensalidade = db.Column(db.Numeric(10, 2), default=0.00)
    desconto_tipo = db.Column(db.String(10), default=None)  # 'real' ou 'porcentagem'
    desconto_valor = db.Column(db.Numeric(10, 2), default=0.00)
    ativo = db.Column(db.Boolean, default=True)  # Controla se gera mensalidades automaticamente
    carteira_pdf = db.Column(db.String(300))  # Caminho do PDF da carteira de associado
    carteira_pdf_base64 = db.Column(db.Text, nullable=True)  # PDF da carteira em base64 para persistência no Render
    foto = db.Column(db.String(300))  # Caminho da foto do associado
    foto_base64 = db.Column(db.Text, nullable=True)  # salvar imagem em base64 para persistência no Render
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

class Reciclagem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo_material = db.Column(db.String(50), nullable=False)  # Ferro, Aluminio, Cobre, Plastico, Papel, Papelao
    nome_completo = db.Column(db.String(200), nullable=False)
    telefone = db.Column(db.String(20), nullable=False)
    endereco_retirada = db.Column(db.Text, nullable=False)
    observacoes = db.Column(db.Text)
    status = db.Column(db.String(20), default='pendente')  # pendente, em_andamento, coletado, cancelado
    observacoes_admin = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now())
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now())

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
    foto_base64 = db.Column(db.Text, nullable=True)  # salvar imagem em base64 para persistência no Render
    ordem = db.Column(db.Integer, default=0)  # Para ordenar os cargos
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class MembroConselhoFiscal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome_pt = db.Column(db.String(200), nullable=False)
    nome_es = db.Column(db.String(200))
    nome_en = db.Column(db.String(200))
    foto = db.Column(db.String(500))
    foto_base64 = db.Column(db.Text, nullable=True)  # salvar imagem em base64 para persistência no Render
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

class RelatorioAtividade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo_pt = db.Column(db.String(200), nullable=False)
    titulo_es = db.Column(db.String(200))
    titulo_en = db.Column(db.String(200))
    descricao_pt = db.Column(db.Text)
    descricao_es = db.Column(db.Text)
    descricao_en = db.Column(db.Text)
    atividades_realizadas_pt = db.Column(db.Text)
    atividades_realizadas_es = db.Column(db.Text)
    atividades_realizadas_en = db.Column(db.Text)
    resultados_pt = db.Column(db.Text)
    resultados_es = db.Column(db.Text)
    resultados_en = db.Column(db.Text)
    periodo_inicio = db.Column(db.Date)
    periodo_fim = db.Column(db.Date)
    arquivo = db.Column(db.String(500))  # Caminho do arquivo PDF/documento ou 'base64:application/pdf'
    arquivo_base64 = db.Column(db.Text, nullable=True)  # Arquivo em base64 para persistência no Render
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
    slug = db.Column(db.String(250), unique=True, nullable=True)  # URL amigável
    subtitulo = db.Column(db.String(300))  # Subtítulo opcional
    conteudo = db.Column(db.Text)  # Texto para notícias
    url_soundcloud = db.Column(db.String(500))  # URL do SoundCloud para podcasts
    imagem = db.Column(db.String(300))  # Caminho da imagem ou 'base64:...'
    imagem_base64 = db.Column(db.Text, nullable=True)  # Imagem em base64 para persistência no Render (opcional)
    descricao_imagem = db.Column(db.Text, nullable=True)  # Descrição da imagem para acessibilidade
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
    imagem = db.Column(db.String(300))  # Caminho da imagem ou 'base64:...'
    imagem_base64 = db.Column(db.Text, nullable=True)  # Imagem em base64 para persistência no Render (opcional)
    descricao_imagem = db.Column(db.Text, nullable=True)  # Descrição da imagem para acessibilidade
    ativo = db.Column(db.Boolean, default=True)
    ordem = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class RadioConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url_streaming_principal = db.Column(db.String(500))  # URL principal de streaming da rádio
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Voluntario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome_completo = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    telefone = db.Column(db.String(50))
    cpf = db.Column(db.String(20))
    password_hash = db.Column(db.String(255), nullable=True)
    endereco = db.Column(db.Text)
    cidade = db.Column(db.String(100))
    estado = db.Column(db.String(50))
    cep = db.Column(db.String(20))
    data_nascimento = db.Column(db.Date)
    profissao = db.Column(db.String(200))
    habilidades = db.Column(db.Text)  # Habilidades e competências do voluntário
    disponibilidade = db.Column(db.Text)  # Dias e horários disponíveis
    area_interesse = db.Column(db.String(200))  # Área de interesse para voluntariado
    observacoes = db.Column(db.Text)
    status = db.Column(db.String(50), default='pendente')  # pendente, aprovado, inativo
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    ofertas_horas = db.relationship('OfertaHoras', backref='voluntario', lazy=True, cascade='all, delete-orphan')
    agendamentos = db.relationship('AgendamentoVoluntario', backref='voluntario', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        try:
            self.password_hash = generate_password_hash(password)
        except Exception:
            # If DB column doesn't exist, set attribute anyway; commit will fail and should be handled by caller
            self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not getattr(self, 'password_hash', None):
            return False
        return check_password_hash(self.password_hash, password)

class OfertaHoras(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    voluntario_id = db.Column(db.Integer, db.ForeignKey('voluntario.id'), nullable=False)
    data_inicio = db.Column(db.Date, nullable=False)
    data_fim = db.Column(db.Date)  # Opcional, se for um período
    hora_inicio = db.Column(db.String(10))  # Ex: "08:00"
    hora_fim = db.Column(db.String(10))  # Ex: "12:00"
    dias_semana = db.Column(db.String(100))  # Ex: "Segunda, Quarta, Sexta" ou "Todos os dias"
    horas_totais = db.Column(db.Float)  # Total de horas oferecidas
    descricao = db.Column(db.Text)  # Descrição da oferta
    area_atividade = db.Column(db.String(200))  # Área de atividade oferecida
    status = db.Column(db.String(50), default='disponivel')  # disponivel, agendada, concluida, cancelada
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamento com agendamentos
    agendamentos = db.relationship('AgendamentoVoluntario', backref='oferta_horas', lazy=True, cascade='all, delete-orphan')

class AgendamentoVoluntario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    voluntario_id = db.Column(db.Integer, db.ForeignKey('voluntario.id'), nullable=False)
    oferta_horas_id = db.Column(db.Integer, db.ForeignKey('oferta_horas.id'), nullable=True)  # Opcional, pode agendar sem oferta específica
    data_agendamento = db.Column(db.Date, nullable=False)
    hora_inicio = db.Column(db.String(10), nullable=False)
    hora_fim = db.Column(db.String(10), nullable=False)
    atividade = db.Column(db.String(200), nullable=False)  # Tipo de atividade/ajuda
    descricao = db.Column(db.Text)  # Descrição detalhada do que será feito
    responsavel = db.Column(db.String(200))  # Nome da pessoa que está agendando
    contato_responsavel = db.Column(db.String(100))  # Telefone/email do responsável
    local = db.Column(db.String(300))  # Local onde será a atividade
    observacoes = db.Column(db.Text)
    status = db.Column(db.String(50), default='agendado')  # agendado, confirmado, em_andamento, concluido, cancelado
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProblemaAcessibilidade(db.Model):
    __tablename__ = 'problema_acessibilidade'
    id = db.Column(db.Integer, primary_key=True)
    tipo_problema = db.Column(db.String(100), nullable=False)  # Ex: "acessibilidade urbana", "calçada", "faixa de pedestre", "sinal sonoro"
    descricao = db.Column(db.Text, nullable=False)
    localizacao = db.Column(db.String(500), nullable=False)  # Endereço ou localização
    nome_denunciante = db.Column(db.String(200), nullable=False)
    telefone = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(200))
    anexos = db.Column(db.Text)  # caminhos separados por vírgula
    status = db.Column(db.String(50), default='novo')  # novo, em_analise, encaminhado, resolvido
    observacoes_admin = db.Column(db.Text)  # Observações internas da associação
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Certificado(db.Model):
    __tablename__ = 'certificado'
    id = db.Column(db.Integer, primary_key=True)
    numero_validacao = db.Column(db.String(50), unique=True, nullable=False)
    nome_pessoa = db.Column(db.String(200), nullable=False)
    documento = db.Column(db.String(100), nullable=True)
    descricao = db.Column(db.Text, nullable=True)
    curso = db.Column(db.String(200), nullable=True)
    data_emissao = db.Column(db.DateTime, default=datetime.utcnow)
    data_validade = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(50), default='valido')  # valido, revogado, expirado
    qr_code_path = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Banner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(50), nullable=False, unique=True)  # 'Campanhas', 'Apoie-nos', 'Editais'
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.String(300))
    url = db.Column(db.String(500))  # URL de destino
    imagem = db.Column(db.String(300))  # Caminho da imagem ou 'base64:...'
    imagem_base64 = db.Column(db.Text, nullable=True)  # Imagem em base64 para persistência no Render (opcional)
    descricao_imagem = db.Column(db.Text, nullable=True)  # Descrição da imagem para acessibilidade
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
    imagem = db.Column(db.String(300))  # Caminho da imagem ou 'base64:...'
    imagem_base64 = db.Column(db.Text, nullable=True)  # Imagem em base64 para persistência no Render (opcional)
    descricao_imagem = db.Column(db.Text, nullable=True)  # Descrição da imagem para acessibilidade
    arquivo_pdf = db.Column(db.String(300))  # Arquivo PDF opcional
    ordem = db.Column(db.Integer, default=0)
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ModeloDocumento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text)
    arquivo = db.Column(db.String(500), nullable=False)  # Caminho do arquivo Word
    nome_arquivo_original = db.Column(db.String(300))  # Nome original do arquivo
    tamanho_arquivo = db.Column(db.Integer)  # Tamanho em bytes
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


def voluntario_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('voluntario_logged_in'):
            flash('Você precisa fazer login como voluntário para acessar esta página', 'error')
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
        'problemas_acessibilidade_novos': ProblemaAcessibilidade.query.filter_by(status='novo').count(),
        'problemas_acessibilidade_total': ProblemaAcessibilidade.query.count(),
        'certificados_total': Certificado.query.count(),
        'associados': Associado.query.count(),
        'associados_pendentes': Associado.query.filter_by(status='pendente').count(),
        'voluntarios': Voluntario.query.count(),
        'voluntarios_pendentes': Voluntario.query.filter_by(status='pendente').count(),
        'ofertas_horas': OfertaHoras.query.count(),
        'agendamentos': AgendamentoVoluntario.query.count(),
        'reciclagem_pendentes': Reciclagem.query.filter_by(status='pendente').count(),
        'reciclagem_total': Reciclagem.query.count(),
    }
    return render_template('admin/dashboard.html', stats=stats)


@app.route('/problema-acessibilidade/registrar', methods=['GET', 'POST'])
def problema_acessibilidade_registrar():
    """Formulário público para registro de problemas de acessibilidade"""
    if request.method == 'POST':
        tipo_problema = request.form.get('tipo_problema', '').strip()
        descricao = request.form.get('descricao', '').strip()
        localizacao = request.form.get('localizacao', '').strip()
        nome_denunciante = request.form.get('nome_denunciante', '').strip()
        telefone = request.form.get('telefone', '').strip()
        email = request.form.get('email', '').strip() or None

        # Validação
        if not tipo_problema or not descricao or not localizacao or not nome_denunciante or not telefone:
            flash('Por favor, preencha todos os campos obrigatórios.', 'error')
            return redirect(url_for('problema_acessibilidade_registrar'))

        # Processar anexos
        anexos_list = []
        if 'anexos' in request.files:
            files = request.files.getlist('anexos')
            for file in files:
                if file and file.filename:
                    if not allowed_document_file(file.filename):
                        flash('Tipo de arquivo não permitido. Use PDF/DOC/IMG etc.', 'error')
                        return redirect(url_for('problema_acessibilidade_registrar'))
                    upload_dir = os.path.join('static', 'documents', 'problemas_acessibilidade')
                    os.makedirs(upload_dir, exist_ok=True)
                    filename = secure_filename(file.filename)
                    unique_name = f"{uuid.uuid4()}_{filename}"
                    filepath = os.path.join(upload_dir, unique_name)
                    try:
                        file.save(filepath)
                        anexos_list.append(f"documents/problemas_acessibilidade/{unique_name}")
                    except Exception as e:
                        print('Erro ao salvar anexo:', e)
                        flash('Erro ao salvar arquivo enviado.', 'error')
                        return redirect(url_for('problema_acessibilidade_registrar'))

        anexos_txt = ','.join(anexos_list) if anexos_list else None

        try:
            # Garantir que a tabela existe antes de inserir
            try:
                db.create_all()
                # Verificar se a tabela existe
                from sqlalchemy import inspect
                inspector = inspect(db.engine)
                if 'problema_acessibilidade' not in inspector.get_table_names():
                    print('[PROBLEMA_ACESSIBILIDADE] Tabela não existe, executando migração...')
                    try:
                        import migrate_postgres_problema_acessibilidade as mig_problema
                        mig_problema.migrate()
                        print('[PROBLEMA_ACESSIBILIDADE] Migração executada')
                    except Exception as mig_error:
                        print(f'[PROBLEMA_ACESSIBILIDADE] Erro na migração: {mig_error}')
                        # Tentar criar manualmente
                        from sqlalchemy import text
                        is_sqlite = db.engine.url.drivername == 'sqlite'
                        with db.engine.connect() as conn:
                            if is_sqlite:
                                conn.execute(text('''
                                    CREATE TABLE IF NOT EXISTS problema_acessibilidade (
                                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                                        tipo_problema VARCHAR(100) NOT NULL,
                                        descricao TEXT NOT NULL,
                                        localizacao VARCHAR(500) NOT NULL,
                                        nome_denunciante VARCHAR(200) NOT NULL,
                                        telefone VARCHAR(100) NOT NULL,
                                        email VARCHAR(200),
                                        anexos TEXT,
                                        status VARCHAR(50) DEFAULT 'novo',
                                        observacoes_admin TEXT,
                                        created_at TIMESTAMP,
                                        updated_at TIMESTAMP
                                    )
                                '''))
                            else:
                                conn.execute(text('''
                                    CREATE TABLE IF NOT EXISTS problema_acessibilidade (
                                        id SERIAL PRIMARY KEY,
                                        tipo_problema VARCHAR(100) NOT NULL,
                                        descricao TEXT NOT NULL,
                                        localizacao VARCHAR(500) NOT NULL,
                                        nome_denunciante VARCHAR(200) NOT NULL,
                                        telefone VARCHAR(100) NOT NULL,
                                        email VARCHAR(200),
                                        anexos TEXT,
                                        status VARCHAR(50) DEFAULT 'novo',
                                        observacoes_admin TEXT,
                                        created_at TIMESTAMP,
                                        updated_at TIMESTAMP
                                    )
                                '''))
                            conn.commit()
                        print('[PROBLEMA_ACESSIBILIDADE] Tabela criada manualmente')
            except Exception as create_error:
                print(f'[PROBLEMA_ACESSIBILIDADE] Aviso ao verificar/criar tabela: {create_error}')

            problema = ProblemaAcessibilidade(
                tipo_problema=tipo_problema,
                descricao=descricao,
                localizacao=localizacao,
                nome_denunciante=nome_denunciante,
                telefone=telefone,
                email=email,
                anexos=anexos_txt,
                status='novo'
            )
            db.session.add(problema)
            db.session.commit()
            flash('Problema de acessibilidade registrado com sucesso! Obrigado por contribuir para uma cidade mais acessível.', 'success')
            return redirect(url_for('problema_acessibilidade_registrar'))
        except Exception as e:
            db.session.rollback()
            print('Erro ao salvar problema de acessibilidade:', e)
            flash('Erro ao registrar problema. Tente novamente mais tarde.', 'error')
            return redirect(url_for('problema_acessibilidade_registrar'))

    return render_template('problema_acessibilidade/registrar.html')


@app.route('/admin/problemas-acessibilidade')
@admin_required
def admin_problemas_acessibilidade():
    """Listagem de problemas de acessibilidade para admin"""
    problemas = ProblemaAcessibilidade.query.order_by(ProblemaAcessibilidade.created_at.desc()).all()
    return render_template('admin/problemas_acessibilidade.html', problemas=problemas)


@app.route('/admin/problemas-acessibilidade/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_problemas_acessibilidade_editar(id):
    """Editar problema de acessibilidade"""
    problema = ProblemaAcessibilidade.query.get_or_404(id)
    if request.method == 'POST':
        problema.tipo_problema = request.form.get('tipo_problema', problema.tipo_problema)
        problema.descricao = request.form.get('descricao', problema.descricao)
        problema.localizacao = request.form.get('localizacao', problema.localizacao)
        problema.status = request.form.get('status', problema.status)
        problema.observacoes_admin = request.form.get('observacoes_admin', problema.observacoes_admin)
        try:
            db.session.commit()
            flash('Problema atualizado com sucesso.', 'success')
            return redirect(url_for('admin_problemas_acessibilidade'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar problema: {e}', 'error')
    return render_template('admin/problema_acessibilidade_form.html', problema=problema)


@app.route('/admin/problemas-acessibilidade/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_problemas_acessibilidade_excluir(id):
    """Excluir problema de acessibilidade"""
    problema = ProblemaAcessibilidade.query.get_or_404(id)
    try:
        db.session.delete(problema)
        db.session.commit()
        flash('Problema excluído com sucesso.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir problema: {e}', 'error')
    return redirect(url_for('admin_problemas_acessibilidade'))


@app.route('/admin/certificados')
@admin_required
def admin_certificados():
    certificados = Certificado.query.order_by(Certificado.created_at.desc()).all()
    return render_template('admin/certificados.html', certificados=certificados)


@app.route('/admin/certificados/novo', methods=['GET', 'POST'])
@admin_required
def admin_certificados_novo():
    if request.method == 'POST':
        nome_pessoa = request.form.get('nome_pessoa', '').strip()
        documento = request.form.get('documento', '').strip() or None
        descricao = request.form.get('descricao', '').strip() or None
        curso = request.form.get('curso', '').strip() or None
        data_emissao_str = request.form.get('data_emissao')
        status = request.form.get('status', 'valido')

        if not nome_pessoa:
            flash('Informe o nome do beneficiário do certificado.', 'error')
            return redirect(url_for('admin_certificados_novo'))

        data_emissao = datetime.utcnow()
        if data_emissao_str:
            try:
                data_emissao = datetime.strptime(data_emissao_str, '%Y-%m-%d')
            except ValueError:
                flash('Data de emissão inválida.', 'error')
                return redirect(url_for('admin_certificados_novo'))

        numero_validacao = gerar_codigo_certificado()
        while Certificado.query.filter_by(numero_validacao=numero_validacao).first():
            numero_validacao = gerar_codigo_certificado()

        try:
            certificado = Certificado(
                numero_validacao=numero_validacao,
                nome_pessoa=nome_pessoa,
                documento=documento,
                descricao=descricao,
                curso=curso,
                data_emissao=data_emissao,
                data_validade=None,  # Certificados são vitalícios
                status=status
            )
            db.session.add(certificado)
            db.session.commit()

            certificado.qr_code_path = salvar_qr_certificado(certificado.numero_validacao)
            db.session.commit()

            flash('Certificado criado com sucesso.', 'success')
            return redirect(url_for('admin_certificados'))
        except Exception as e:
            db.session.rollback()
            print('Erro ao criar certificado:', e)
            flash('Erro ao criar certificado.', 'error')
            return redirect(url_for('admin_certificados_novo'))

    return render_template('admin/certificado_form.html', certificado=None)


@app.route('/admin/certificados/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_certificados_editar(id):
    certificado = Certificado.query.get_or_404(id)
    if request.method == 'POST':
        certificado.nome_pessoa = request.form.get('nome_pessoa', certificado.nome_pessoa)
        certificado.documento = request.form.get('documento', certificado.documento)
        certificado.descricao = request.form.get('descricao', certificado.descricao)
        certificado.curso = request.form.get('curso', certificado.curso)
        status = request.form.get('status', certificado.status)
        certificado.status = status

        data_emissao_str = request.form.get('data_emissao')

        try:
            if data_emissao_str:
                certificado.data_emissao = datetime.strptime(data_emissao_str, '%Y-%m-%d')
            # Certificados são vitalícios, sempre manter data_validade como None
            certificado.data_validade = None
        except ValueError:
            flash('Data de emissão inválida.', 'error')
            return redirect(url_for('admin_certificados_editar', id=id))

        try:
            db.session.commit()
            flash('Certificado atualizado com sucesso.', 'success')
            return redirect(url_for('admin_certificados'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar certificado: {e}', 'error')

    return render_template('admin/certificado_form.html', certificado=certificado)


@app.route('/admin/certificados/<int:id>/regenerar-qr', methods=['POST'])
@admin_required
def admin_certificados_regenerar_qr(id):
    certificado = Certificado.query.get_or_404(id)
    try:
        certificado.qr_code_path = salvar_qr_certificado(certificado.numero_validacao)
        db.session.commit()
        flash('QR Code regenerado com sucesso.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao regenerar QR Code: {e}', 'error')
    return redirect(url_for('admin_certificados'))


@app.route('/certificados/validar/<codigo>')
def certificado_validar(codigo):
    codigo = codigo.upper()
    certificado = Certificado.query.filter_by(numero_validacao=codigo).first()
    valido = certificado_esta_valido(certificado)
    return render_template('certificados/validar.html', certificado=certificado, valido=valido)


@app.route('/certificados/validar', methods=['GET', 'POST'])
def certificado_validar_form():
    if request.method == 'POST':
        codigo = request.form.get('codigo', '').strip().upper()
        if codigo:
            return redirect(url_for('certificado_validar', codigo=codigo))
        flash('Informe o número do certificado para validar.', 'error')
    return render_template('certificados/validar_form.html')

@app.route('/reciclagem', methods=['GET', 'POST'])
def reciclagem_form():
    """Formulário público para coleta de reciclagem"""
    if request.method == 'POST':
        try:
            tipo_material = request.form.get('tipo_material', '').strip()
            nome_completo = request.form.get('nome_completo', '').strip()
            telefone = request.form.get('telefone', '').strip()
            endereco_retirada = request.form.get('endereco_retirada', '').strip()
            observacoes = request.form.get('observacoes', '').strip()
            
            # Validações
            if not tipo_material:
                flash('Selecione o tipo de material.', 'error')
                return render_template('reciclagem/form.html')
            
            if not nome_completo:
                flash('Nome completo é obrigatório.', 'error')
                return render_template('reciclagem/form.html')
            
            if not telefone:
                flash('Telefone/WhatsApp é obrigatório.', 'error')
                return render_template('reciclagem/form.html')
            
            if not endereco_retirada:
                flash('Endereço de retirada é obrigatório.', 'error')
                return render_template('reciclagem/form.html')
            
            # Criar registro
            reciclagem = Reciclagem(
                tipo_material=tipo_material,
                nome_completo=nome_completo,
                telefone=telefone,
                endereco_retirada=endereco_retirada,
                observacoes=observacoes if observacoes else None,
                status='pendente'
            )
            
            db.session.add(reciclagem)
            db.session.commit()
            
            flash('Solicitação de coleta de reciclagem enviada com sucesso! Entraremos em contato em breve.', 'success')
            return redirect(url_for('reciclagem_form'))
            
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao processar formulário de reciclagem: {e}")
            flash('Erro ao enviar solicitação. Tente novamente.', 'error')
    
    return render_template('reciclagem/form.html')


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
            
            titulo = request.form.get('titulo')
            slug = gerar_slug_unico(titulo, ReunionPresencial)
            
            reunion = ReunionPresencial(
                titulo=titulo,
                slug=slug,
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
            
            titulo = request.form.get('titulo')
            # Atualizar slug se o título mudou
            if reunion.titulo != titulo:
                reunion.slug = gerar_slug_unico(titulo, ReunionPresencial, reunion.id)
            
            reunion.titulo = titulo
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
            
            titulo = request.form.get('titulo')
            slug = gerar_slug_unico(titulo, ReunionVirtual)
            
            reunion = ReunionVirtual(
                titulo=titulo,
                slug=slug,
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
            
            titulo = request.form.get('titulo')
            # Atualizar slug se o título mudou
            if reunion.titulo != titulo:
                reunion.slug = gerar_slug_unico(titulo, ReunionVirtual, reunion.id)
            
            reunion.titulo = titulo
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
            
            # Processar upload da foto - salvar como base64 no banco para persistência no Render
            imagen_path = None
            imagen_base64_data = None
            if 'imagen' in request.files:
                file = request.files['imagen']
                if file and file.filename != '' and allowed_file(file.filename):
                    # Ler o arquivo e converter para base64
                    file_data = file.read()
                    file_ext = os.path.splitext(file.filename)[1].lower().replace('.', '')
                    
                    # Determinar o tipo MIME
                    mime_types = {
                        'jpg': 'image/jpeg',
                        'jpeg': 'image/jpeg',
                        'png': 'image/png',
                        'gif': 'image/gif',
                        'webp': 'image/webp'
                    }
                    mime_type = mime_types.get(file_ext, 'image/jpeg')
                    
                    # Converter para base64
                    imagen_base64_data = base64.b64encode(file_data).decode('utf-8')
                    imagen_path = f"base64:{mime_type}"
                    
                    # Também salvar localmente para desenvolvimento local (opcional)
                    try:
                        upload_folder = app.config['UPLOAD_FOLDER']
                        os.makedirs(upload_folder, exist_ok=True)
                        
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        filepath = os.path.join(upload_folder, unique_filename)
                        file.seek(0)  # Reset file pointer after reading for base64
                        file.save(filepath)
                        imagen_path = f"images/uploads/{unique_filename}"
                    except Exception as e:
                        print(f"[AVISO] Não foi possível salvar imagem localmente: {e}")
                elif file and file.filename != '':
                    flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP', 'error')
                    return redirect(url_for('admin_projetos_novo'))
            
            # Processar upload do PDF - salvar como base64 no banco para persistência no Render
            pdf_path = None
            pdf_base64_data = None
            if 'arquivo_pdf' in request.files:
                file = request.files['arquivo_pdf']
                if file and file.filename != '' and allowed_pdf_file(file.filename):
                    # Ler o arquivo e converter para base64
                    file_data = file.read()
                    
                    # Converter para base64
                    pdf_base64_data = base64.b64encode(file_data).decode('utf-8')
                    pdf_path = "base64:application/pdf"
                    
                    # Também salvar localmente para desenvolvimento local (opcional)
                    try:
                        upload_folder_pdf = os.path.join('static', 'documents', 'projetos')
                        os.makedirs(upload_folder_pdf, exist_ok=True)
                        
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        filepath = os.path.join(upload_folder_pdf, unique_filename)
                        file.seek(0)  # Reset file pointer after reading for base64
                        file.save(filepath)
                        pdf_path = f"documents/projetos/{unique_filename}"
                    except Exception as e:
                        print(f"[AVISO] Não foi possível salvar PDF localmente: {e}")
                elif file and file.filename != '':
                    flash('Tipo de arquivo não permitido para PDF. Use apenas arquivos .pdf', 'error')
                    return redirect(url_for('admin_projetos_novo'))
            
            titulo = request.form.get('titulo')
            slug = gerar_slug_unico(titulo, Projeto)
            
            projeto = Projeto(
                titulo=titulo,
                slug=slug,
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
                imagen=imagen_path,
                imagen_base64=imagen_base64_data,
                descricao_imagem=request.form.get('descricao_imagem', '').strip() or None,
                arquivo_pdf=pdf_path,
                arquivo_pdf_base64=pdf_base64_data
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
            
            # Processar upload da foto (se uma nova foi enviada) - salvar como base64 no banco para persistência no Render
            if 'imagen' in request.files:
                file = request.files['imagen']
                if file and file.filename != '' and allowed_file(file.filename):
                    # Remover foto antiga se existir (apenas arquivo local, não base64)
                    if projeto.imagen and not (projeto.imagen.startswith('base64:') if projeto.imagen else False):
                        old_filepath = os.path.join('static', projeto.imagen)
                        if os.path.exists(old_filepath):
                            try:
                                os.remove(old_filepath)
                            except:
                                pass
                    
                    # Ler o arquivo e converter para base64
                    file_data = file.read()
                    file_ext = os.path.splitext(file.filename)[1].lower().replace('.', '')
                    
                    # Determinar o tipo MIME
                    mime_types = {
                        'jpg': 'image/jpeg',
                        'jpeg': 'image/jpeg',
                        'png': 'image/png',
                        'gif': 'image/gif',
                        'webp': 'image/webp'
                    }
                    mime_type = mime_types.get(file_ext, 'image/jpeg')
                    
                    # Converter para base64
                    imagen_base64_data = base64.b64encode(file_data).decode('utf-8')
                    projeto.imagen_base64 = imagen_base64_data
                    projeto.imagen = f"base64:{mime_type}"
                    
                    # Também salvar localmente para desenvolvimento local (opcional)
                    try:
                        upload_folder = app.config['UPLOAD_FOLDER']
                        os.makedirs(upload_folder, exist_ok=True)
                        
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        filepath = os.path.join(upload_folder, unique_filename)
                        file.seek(0)  # Reset file pointer after reading for base64
                        file.save(filepath)
                        projeto.imagen = f"images/uploads/{unique_filename}"
                    except Exception as e:
                        print(f"[AVISO] Não foi possível salvar imagem localmente: {e}")
                elif file and file.filename != '':
                    flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP', 'error')
                    return redirect(url_for('admin_projetos_editar', id=id))
            
            # Processar upload do PDF - salvar como base64 no banco para persistência no Render
            if 'arquivo_pdf' in request.files:
                file = request.files['arquivo_pdf']
                if file and file.filename != '' and allowed_pdf_file(file.filename):
                    # Remover PDF antigo se existir (apenas arquivo local, não base64)
                    if projeto.arquivo_pdf and not (projeto.arquivo_pdf.startswith('base64:') if projeto.arquivo_pdf else False):
                        old_filepath = os.path.join('static', projeto.arquivo_pdf)
                        if os.path.exists(old_filepath):
                            try:
                                os.remove(old_filepath)
                            except:
                                pass
                    
                    # Ler o arquivo e converter para base64
                    file_data = file.read()
                    
                    # Converter para base64
                    pdf_base64_data = base64.b64encode(file_data).decode('utf-8')
                    projeto.arquivo_pdf_base64 = pdf_base64_data
                    projeto.arquivo_pdf = "base64:application/pdf"
                    
                    # Também salvar localmente para desenvolvimento local (opcional)
                    try:
                        upload_folder_pdf = os.path.join('static', 'documents', 'projetos')
                        os.makedirs(upload_folder_pdf, exist_ok=True)
                        
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        filepath = os.path.join(upload_folder_pdf, unique_filename)
                        file.seek(0)  # Reset file pointer after reading for base64
                        file.save(filepath)
                        projeto.arquivo_pdf = f"documents/projetos/{unique_filename}"
                    except Exception as e:
                        print(f"[AVISO] Não foi possível salvar PDF localmente: {e}")
                elif file and file.filename != '':
                    flash('Tipo de arquivo não permitido para PDF. Use apenas arquivos .pdf', 'error')
                    return redirect(url_for('admin_projetos_editar', id=id))
            
            # Remover PDF se solicitado
            if request.form.get('remover_pdf') == '1':
                if projeto.arquivo_pdf and not (projeto.arquivo_pdf.startswith('base64:') if projeto.arquivo_pdf else False):
                    old_filepath = os.path.join('static', projeto.arquivo_pdf)
                    if os.path.exists(old_filepath):
                        try:
                            os.remove(old_filepath)
                        except:
                            pass
                projeto.arquivo_pdf = None
                projeto.arquivo_pdf_base64 = None
            
            titulo = request.form.get('titulo')
            # Atualizar slug se o título mudou
            if projeto.titulo != titulo:
                projeto.slug = gerar_slug_unico(titulo, Projeto, projeto.id)
            
            projeto.titulo = titulo
            projeto.descripcion = request.form.get('descripcion')
            projeto.descricao_imagem = request.form.get('descricao_imagem', '').strip() or None
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
            
            titulo = request.form.get('titulo')
            slug = gerar_slug_unico(titulo, Evento)
            
            evento = Evento(
                titulo=titulo,
                slug=slug,
                descricao=request.form.get('descricao'),
                data=data_datetime,
                hora=hora,
                local=request.form.get('local'),
                endereco=request.form.get('endereco'),
                tipo=request.form.get('tipo'),
                link=request.form.get('link'),
                imagem=imagem_path,
                descricao_imagem=request.form.get('descricao_imagem', '').strip() or None
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
            
            titulo = request.form.get('titulo')
            # Atualizar slug se o título mudou
            if evento.titulo != titulo:
                evento.slug = gerar_slug_unico(titulo, Evento, evento.id)
            
            evento.titulo = titulo
            evento.descricao = request.form.get('descricao')
            evento.data = data_datetime
            evento.hora = hora
            evento.local = request.form.get('local')
            evento.endereco = request.form.get('endereco')
            evento.tipo = request.form.get('tipo')
            evento.link = request.form.get('link')
            evento.descricao_imagem = request.form.get('descricao_imagem', '').strip() or None
            
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
            
            # Processar upload da foto - salvar como base64 no banco para persistência no Render
            imagem_path = None
            imagem_base64_data = None
            if 'imagem' in request.files:
                file = request.files['imagem']
                if file and file.filename != '' and allowed_file(file.filename):
                    # Ler o arquivo e converter para base64
                    file_data = file.read()
                    file_ext = os.path.splitext(file.filename)[1].lower().replace('.', '')
                    
                    # Determinar o tipo MIME
                    mime_types = {
                        'jpg': 'image/jpeg',
                        'jpeg': 'image/jpeg',
                        'png': 'image/png',
                        'gif': 'image/gif',
                        'webp': 'image/webp'
                    }
                    mime_type = mime_types.get(file_ext, 'image/jpeg')
                    
                    # Converter para base64
                    imagem_base64_data = base64.b64encode(file_data).decode('utf-8')
                    imagem_path = f"base64:{mime_type}"
                    
                    # Também salvar localmente para desenvolvimento local (opcional)
                    try:
                        upload_folder = app.config['UPLOAD_FOLDER']
                        os.makedirs(upload_folder, exist_ok=True)
                        
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        filepath = os.path.join(upload_folder, unique_filename)
                        file.seek(0)  # Reset file pointer after reading for base64
                        file.save(filepath)
                        imagem_path = f"images/uploads/{unique_filename}"
                    except Exception as e:
                        print(f"[AVISO] Não foi possível salvar imagem localmente: {e}")
                elif file and file.filename != '':
                    flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP', 'error')
                    return redirect(url_for('admin_acoes_novo'))
            
            titulo = request.form.get('titulo')
            slug = gerar_slug_unico(titulo, Acao)
            
            acao = Acao(
                titulo=titulo,
                slug=slug,
                descricao=request.form.get('descricao'),
                data=datetime.strptime(data_str, "%Y-%m-%d").date(),
                categoria=request.form.get('categoria'),
                imagem=imagem_path,
                imagem_base64=imagem_base64_data,
                descricao_imagem=request.form.get('descricao_imagem', '').strip() or None
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
            
            # Processar upload da foto (se uma nova foi enviada) - salvar como base64 no banco para persistência no Render
            if 'imagem' in request.files:
                file = request.files['imagem']
                if file and file.filename != '' and allowed_file(file.filename):
                    # Remover foto antiga se existir (apenas arquivo local, não base64)
                    if acao.imagem and not (acao.imagem.startswith('base64:') if acao.imagem else False):
                        old_filepath = os.path.join('static', acao.imagem)
                        if os.path.exists(old_filepath):
                            try:
                                os.remove(old_filepath)
                            except:
                                pass
                    
                    # Ler o arquivo e converter para base64
                    file_data = file.read()
                    file_ext = os.path.splitext(file.filename)[1].lower().replace('.', '')
                    
                    # Determinar o tipo MIME
                    mime_types = {
                        'jpg': 'image/jpeg',
                        'jpeg': 'image/jpeg',
                        'png': 'image/png',
                        'gif': 'image/gif',
                        'webp': 'image/webp'
                    }
                    mime_type = mime_types.get(file_ext, 'image/jpeg')
                    
                    # Converter para base64
                    imagem_base64_data = base64.b64encode(file_data).decode('utf-8')
                    acao.imagem_base64 = imagem_base64_data
                    acao.imagem = f"base64:{mime_type}"
                    
                    # Também salvar localmente para desenvolvimento local (opcional)
                    try:
                        upload_folder = app.config['UPLOAD_FOLDER']
                        os.makedirs(upload_folder, exist_ok=True)
                        
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        filepath = os.path.join(upload_folder, unique_filename)
                        file.seek(0)  # Reset file pointer after reading for base64
                        file.save(filepath)
                        acao.imagem = f"images/uploads/{unique_filename}"
                    except Exception as e:
                        print(f"[AVISO] Não foi possível salvar imagem localmente: {e}")
                elif file and file.filename != '':
                    flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP', 'error')
                    return redirect(url_for('admin_acoes_editar', id=id))
            
            titulo = request.form.get('titulo')
            # Atualizar slug se o título mudou
            if acao.titulo != titulo:
                acao.slug = gerar_slug_unico(titulo, Acao, acao.id)
            
            acao.titulo = titulo
            acao.descricao = request.form.get('descricao')
            acao.data = datetime.strptime(data_str, "%Y-%m-%d").date()
            acao.categoria = request.form.get('categoria')
            acao.descricao_imagem = request.form.get('descricao_imagem', '').strip() or None
            
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
                        # Ler dados do arquivo e converter para Base64
                        file_data = file.read()
                        file_ext = os.path.splitext(file.filename)[1].lower().replace('.', '')
                        mime_types = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'gif': 'image/gif', 'webp': 'image/webp'}
                        mime_type = mime_types.get(file_ext, 'image/png')
                        qrcode_base64_data = base64.b64encode(file_data).decode('utf-8')
                        
                        # Salvar Base64 na configuração
                        config_base64 = Configuracao.query.filter_by(chave='footer_qrcode_base64').first()
                        if config_base64:
                            config_base64.valor = qrcode_base64_data
                            config_base64.tipo = 'imagem_base64'
                            config_base64.updated_at = datetime.utcnow()
                        else:
                            config_base64 = Configuracao(chave='footer_qrcode_base64', valor=qrcode_base64_data, tipo='imagem_base64')
                            db.session.add(config_base64)
                        
                        # Salvar mime type na configuração footer_qrcode_mime
                        config_mime = Configuracao.query.filter_by(chave='footer_qrcode_mime').first()
                        if config_mime:
                            config_mime.valor = mime_type
                            config_mime.updated_at = datetime.utcnow()
                        else:
                            config_mime = Configuracao(chave='footer_qrcode_mime', valor=mime_type, tipo='texto')
                            db.session.add(config_mime)
                        
                        # Também salvar localmente para desenvolvimento local (opcional)
                        try:
                            upload_folder = 'static/images'
                            os.makedirs(upload_folder, exist_ok=True)
                            filepath = os.path.join(upload_folder, 'qrcode.png')
                            file.seek(0)  # Reset file pointer after reading for base64
                            file.save(filepath)
                            
                            # Manter compatibilidade com o valor antigo
                            config = Configuracao.query.filter_by(chave='footer_qrcode').first()
                            if config:
                                config.valor = 'images/qrcode.png'
                                config.updated_at = datetime.utcnow()
                            else:
                                config = Configuracao(chave='footer_qrcode', valor='images/qrcode.png', tipo='imagem')
                                db.session.add(config)
                        except Exception as e:
                            print(f"[AVISO] Não foi possível salvar arquivo localmente: {e}")
            
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
            coluna_input = request.form.get('coluna')
            ativo = request.form.get('ativo') == 'on'
            
            if not titulo:
                flash('Título é obrigatório!', 'error')
                return redirect(url_for('admin_o_que_fazemos_novo'))
            
            if not descricao:
                flash('Descrição é obrigatória!', 'error')
                return redirect(url_for('admin_o_que_fazemos_novo'))
            
            # Distribuir automaticamente entre as 3 colunas (round-robin)
            # Se o usuário não especificar uma coluna, calcular automaticamente
            if coluna_input:
                coluna = int(coluna_input)
                if coluna not in [1, 2, 3]:
                    coluna = 1
            else:
                # Contar serviços ativos existentes para distribuir automaticamente
                total_servicos = OQueFazemosServico.query.filter_by(ativo=True).count()
                # Distribuir em round-robin: 1, 2, 3, 1, 2, 3...
                coluna = (total_servicos % 3) + 1
                print(f"[DEBUG] Novo serviço será adicionado na coluna {coluna} (total de serviços: {total_servicos})")
            
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

def start_instagram_updater(username, instagram_url):
    """Executa a atualização de posts do Instagram em thread separada"""
    global _instagram_update_lock, _instagram_last_update_time
    
    # Importante: threads precisam do contexto da aplicação para acessar o banco
    with app.app_context():
        try:
            print(f"[Instagram] Iniciando atualização em background para @{username}...")
            posts_cadastrados = buscar_posts_instagram(username, instagram_url)
            print(f"[Instagram] Posts atualizados em background: {posts_cadastrados}")
        except Exception as e:
            print(f"[Instagram] Erro ao atualizar: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Liberar o lock e atualizar timestamp
            _instagram_update_lock = False
            _instagram_last_update_time = datetime.utcnow()

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
            
            # Upload da foto - salvar como base64 no banco para persistência no Render
            foto_path = None
            foto_base64_data = None
            if 'foto' in request.files:
                file = request.files['foto']
                if file.filename != '':
                    if file and allowed_file(file.filename):
                        # Salvar também como arquivo local (compatibilidade)
                        upload_folder = 'static/images/diretoria'
                        os.makedirs(upload_folder, exist_ok=True)
                        
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        filepath = os.path.join(upload_folder, unique_filename)
                        file.save(filepath)
                        foto_path = f"images/diretoria/{unique_filename}"
                        
                        # Salvar em base64 para persistência no Render
                        file.seek(0)  # Voltar ao início do arquivo
                        file_data = file.read()
                        mime_type = file.content_type or 'image/jpeg'
                        foto_base64_data = base64.b64encode(file_data).decode('utf-8')
                        foto_path = f"base64:{mime_type}"
            
            membro = MembroDiretoria(
                cargo=cargo,
                nome_pt=nome_pt,
                nome_es=nome_es,
                nome_en=nome_en,
                foto=foto_path,
                foto_base64=foto_base64_data,
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
            
            # Upload da foto (se uma nova foi enviada) - salvar como base64 no banco para persistência no Render
            if 'foto' in request.files:
                file = request.files['foto']
                if file.filename != '':
                    if file and allowed_file(file.filename):
                        # Salvar também como arquivo local (compatibilidade)
                        upload_folder = 'static/images/diretoria'
                        os.makedirs(upload_folder, exist_ok=True)
                        
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        filepath = os.path.join(upload_folder, unique_filename)
                        file.save(filepath)
                        
                        # Salvar em base64 para persistência no Render
                        file.seek(0)  # Voltar ao início do arquivo
                        file_data = file.read()
                        mime_type = file.content_type or 'image/jpeg'
                        membro.foto_base64 = base64.b64encode(file_data).decode('utf-8')
                        membro.foto = f"base64:{mime_type}"
            
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
            
            # Upload da foto - salvar como base64 no banco para persistência no Render
            foto_path = None
            foto_base64_data = None
            if 'foto' in request.files:
                file = request.files['foto']
                if file.filename != '':
                    if file and allowed_file(file.filename):
                        # Salvar também como arquivo local (compatibilidade)
                        upload_folder = 'static/images/diretoria'
                        os.makedirs(upload_folder, exist_ok=True)
                        
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        filepath = os.path.join(upload_folder, unique_filename)
                        file.save(filepath)
                        foto_path = f"images/diretoria/{unique_filename}"
                        
                        # Salvar em base64 para persistência no Render
                        file.seek(0)  # Voltar ao início do arquivo
                        file_data = file.read()
                        mime_type = file.content_type or 'image/jpeg'
                        foto_base64_data = base64.b64encode(file_data).decode('utf-8')
                        foto_path = f"base64:{mime_type}"
            
            membro = MembroConselhoFiscal(
                nome_pt=nome_pt,
                nome_es=nome_es,
                nome_en=nome_en,
                foto=foto_path,
                foto_base64=foto_base64_data,
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
            
            # Upload da foto (se uma nova foi enviada) - salvar como base64 no banco para persistência no Render
            if 'foto' in request.files:
                file = request.files['foto']
                if file.filename != '':
                    if file and allowed_file(file.filename):
                        # Salvar também como arquivo local (compatibilidade)
                        upload_folder = 'static/images/diretoria'
                        os.makedirs(upload_folder, exist_ok=True)
                        
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        filepath = os.path.join(upload_folder, unique_filename)
                        file.save(filepath)
                        
                        # Salvar em base64 para persistência no Render
                        file.seek(0)  # Voltar ao início do arquivo
                        file_data = file.read()
                        mime_type = file.content_type or 'image/jpeg'
                        membro.foto_base64 = base64.b64encode(file_data).decode('utf-8')
                        membro.foto = f"base64:{mime_type}"
            
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
    relatorios_atividades = RelatorioAtividade.query.order_by(RelatorioAtividade.ordem.asc(), RelatorioAtividade.periodo_inicio.desc()).all()
    informacoes_doacao = InformacaoDoacao.query.order_by(InformacaoDoacao.ordem.asc()).all()
    
    return render_template('admin/transparencia.html',
                         relatorios=relatorios,
                         documentos=documentos,
                         prestacoes=prestacoes,
                         relatorios_atividades=relatorios_atividades,
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
# CRUD - RELATÓRIOS DE ATIVIDADES
# ============================================

def processar_texto_relatorio(texto):
    """Processa texto de relatório: converte tags <br> para quebras de linha e limpa dados antigos"""
    if not texto:
        return ''
    # Converter <br>, <br/>, <br /> para quebras de linha
    texto = texto.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
    # Remover tags HTML restantes que possam ter sido inseridas
    import re
    texto = re.sub(r'<[^>]+>', '', texto)  # Remove qualquer tag HTML restante
    return texto

def processar_texto_paragrafos(texto):
    """Converte quebras de linha em parágrafos HTML"""
    if not texto:
        return ''
    # Remover tags HTML existentes que possam causar problemas
    import re
    texto = re.sub(r'<[^>]+>', '', texto)
    
    # Dividir por quebras de linha duplas ou simples
    # Quebras duplas (\n\n) criam novos parágrafos
    # Quebras simples (\n) criam <br>
    paragrafos = []
    linhas = texto.split('\n\n')
    
    for paragrafo in linhas:
        paragrafo = paragrafo.strip()
        if paragrafo:
            # Substituir quebras simples dentro do parágrafo por <br>
            paragrafo = paragrafo.replace('\n', '<br>')
            paragrafos.append(f'<p>{paragrafo}</p>')
    
    return '\n'.join(paragrafos) if paragrafos else ''

def html_para_texto(html):
    """Converte HTML de volta para texto simples para edição"""
    if not html:
        return ''
    import re
    # Remover tags <p> e </p>, substituindo por quebras duplas
    texto = html.replace('</p>', '\n\n').replace('<p>', '')
    # Remover tags <br> e substituir por quebras simples
    texto = re.sub(r'<br\s*/?>', '\n', texto, flags=re.IGNORECASE)
    # Remover outras tags HTML
    texto = re.sub(r'<[^>]+>', '', texto)
    # Limpar espaços extras e quebras de linha
    texto = '\n\n'.join([p.strip() for p in texto.split('\n\n') if p.strip()])
    return texto

@app.route('/admin/transparencia/relatorio-atividade/novo', methods=['GET', 'POST'])
@admin_required
def admin_relatorio_atividade_novo():
    if request.method == 'POST':
        try:
            titulo_pt = request.form.get('titulo_pt')
            titulo_es = request.form.get('titulo_es', '')
            titulo_en = request.form.get('titulo_en', '')
            descricao_pt = request.form.get('descricao_pt', '')
            descricao_es = request.form.get('descricao_es', '')
            descricao_en = request.form.get('descricao_en', '')
            atividades_realizadas_pt = request.form.get('atividades_realizadas_pt', '')
            atividades_realizadas_es = request.form.get('atividades_realizadas_es', '')
            atividades_realizadas_en = request.form.get('atividades_realizadas_en', '')
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
                return redirect(url_for('admin_relatorio_atividade_novo'))
            
            # Processar texto: converter tags <br> para quebras de linha
            descricao_pt = processar_texto_relatorio(descricao_pt)
            descricao_es = processar_texto_relatorio(descricao_es)
            descricao_en = processar_texto_relatorio(descricao_en)
            atividades_realizadas_pt = processar_texto_relatorio(atividades_realizadas_pt)
            atividades_realizadas_es = processar_texto_relatorio(atividades_realizadas_es)
            atividades_realizadas_en = processar_texto_relatorio(atividades_realizadas_en)
            resultados_pt = processar_texto_relatorio(resultados_pt)
            resultados_es = processar_texto_relatorio(resultados_es)
            resultados_en = processar_texto_relatorio(resultados_en)
            
            # Upload do arquivo - salvar como base64 no banco para persistência no Render
            arquivo_path = None
            arquivo_base64_data = None
            if 'arquivo' in request.files:
                file = request.files['arquivo']
                if file.filename != '':
                    if file and allowed_document_file(file.filename):
                        # Salvar também como arquivo local (compatibilidade)
                        upload_folder = 'static/documents/transparencia'
                        os.makedirs(upload_folder, exist_ok=True)
                        
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        filepath = os.path.join(upload_folder, unique_filename)
                        file.save(filepath)
                        
                        # Salvar em base64 para persistência no Render
                        file.seek(0)  # Voltar ao início do arquivo
                        file_data = file.read()
                        mime_type = file.content_type or 'application/pdf'
                        arquivo_base64_data = base64.b64encode(file_data).decode('utf-8')
                        arquivo_path = f"base64:{mime_type}"
            
            relatorio = RelatorioAtividade(
                titulo_pt=titulo_pt,
                titulo_es=titulo_es,
                titulo_en=titulo_en,
                descricao_pt=descricao_pt,
                descricao_es=descricao_es,
                descricao_en=descricao_en,
                atividades_realizadas_pt=atividades_realizadas_pt,
                atividades_realizadas_es=atividades_realizadas_es,
                atividades_realizadas_en=atividades_realizadas_en,
                resultados_pt=resultados_pt,
                resultados_es=resultados_es,
                resultados_en=resultados_en,
                periodo_inicio=periodo_inicio,
                periodo_fim=periodo_fim,
                arquivo=arquivo_path,
                arquivo_base64=arquivo_base64_data,
                ordem=ordem
            )
            db.session.add(relatorio)
            db.session.commit()
            flash('Relatório de atividades cadastrado com sucesso!', 'success')
            return redirect(url_for('admin_transparencia'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar relatório de atividades: {str(e)}', 'error')
    
    return render_template('admin/relatorio_atividade_form.html')

@app.route('/admin/transparencia/relatorio-atividade/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_relatorio_atividade_editar(id):
    relatorio = RelatorioAtividade.query.get_or_404(id)
    
    # Limpar dados existentes que têm tags <br> ao carregar para edição
    if request.method == 'GET':
        campos_texto = [
            'descricao_pt', 'descricao_es', 'descricao_en',
            'atividades_realizadas_pt', 'atividades_realizadas_es', 'atividades_realizadas_en',
            'resultados_pt', 'resultados_es', 'resultados_en'
        ]
        precisa_salvar = False
        for campo in campos_texto:
            valor = getattr(relatorio, campo, None)
            if valor and ('<br>' in valor or '<br/>' in valor or '<br />' in valor):
                valor_limpo = processar_texto_relatorio(valor)
                setattr(relatorio, campo, valor_limpo)
                precisa_salvar = True
        
        if precisa_salvar:
            try:
                db.session.commit()
            except:
                db.session.rollback()
    
    if request.method == 'POST':
        try:
            relatorio.titulo_pt = request.form.get('titulo_pt')
            relatorio.titulo_es = request.form.get('titulo_es', '')
            relatorio.titulo_en = request.form.get('titulo_en', '')
            
            relatorio.descricao_pt = processar_texto_relatorio(request.form.get('descricao_pt', ''))
            relatorio.descricao_es = processar_texto_relatorio(request.form.get('descricao_es', ''))
            relatorio.descricao_en = processar_texto_relatorio(request.form.get('descricao_en', ''))
            relatorio.atividades_realizadas_pt = processar_texto_relatorio(request.form.get('atividades_realizadas_pt', ''))
            relatorio.atividades_realizadas_es = processar_texto_relatorio(request.form.get('atividades_realizadas_es', ''))
            relatorio.atividades_realizadas_en = processar_texto_relatorio(request.form.get('atividades_realizadas_en', ''))
            relatorio.resultados_pt = processar_texto_relatorio(request.form.get('resultados_pt', ''))
            relatorio.resultados_es = processar_texto_relatorio(request.form.get('resultados_es', ''))
            relatorio.resultados_en = processar_texto_relatorio(request.form.get('resultados_en', ''))
            relatorio.ordem = int(request.form.get('ordem', 0))
            periodo_inicio_str = request.form.get('periodo_inicio')
            periodo_fim_str = request.form.get('periodo_fim')
            relatorio.periodo_inicio = datetime.strptime(periodo_inicio_str, '%Y-%m-%d').date() if periodo_inicio_str else None
            relatorio.periodo_fim = datetime.strptime(periodo_fim_str, '%Y-%m-%d').date() if periodo_fim_str else None
            
            # Upload do arquivo se fornecido
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
                        
                        # Salvar em base64 para persistência no Render
                        file.seek(0)  # Voltar ao início do arquivo
                        file_data = file.read()
                        mime_type = file.content_type or 'application/pdf'
                        relatorio.arquivo_base64 = base64.b64encode(file_data).decode('utf-8')
                        relatorio.arquivo = f"base64:{mime_type}"
            
            relatorio.updated_at = datetime.utcnow()
            db.session.commit()
            flash('Relatório de atividades atualizado com sucesso!', 'success')
            return redirect(url_for('admin_transparencia'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar relatório de atividades: {str(e)}', 'error')
    
    return render_template('admin/relatorio_atividade_form.html', relatorio=relatorio)

@app.route('/admin/transparencia/relatorio-atividade/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_relatorio_atividade_excluir(id):
    relatorio = RelatorioAtividade.query.get_or_404(id)
    try:
        db.session.delete(relatorio)
        db.session.commit()
        flash('Relatório de atividades excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir relatório de atividades: {str(e)}', 'error')
    return redirect(url_for('admin_transparencia'))

@app.route('/relatorio-atividade/<int:id>/arquivo')
def relatorio_atividade_arquivo(id):
    """Rota para servir arquivos de relatórios de atividades do banco de dados (base64)"""
    try:
        relatorio = RelatorioAtividade.query.get_or_404(id)
        
        # Verificar se tem arquivo em base64 (prioridade para persistência no Render)
        arquivo_base64 = getattr(relatorio, 'arquivo_base64', None)
        
        # Se não tem arquivo nem base64, retornar 404
        if not relatorio.arquivo and not arquivo_base64:
            from flask import abort
            abort(404)
        
        if arquivo_base64:
            # Servir arquivo do banco de dados (base64)
            try:
                # Extrair o tipo MIME do campo arquivo
                mime_type = 'application/pdf'  # padrão
                if relatorio.arquivo and relatorio.arquivo.startswith('base64:'):
                    mime_type = relatorio.arquivo.replace('base64:', '')
                
                arquivo_data = base64.b64decode(arquivo_base64)
                from flask import Response
                return Response(
                    arquivo_data,
                    mimetype=mime_type,
                    headers={
                        'Content-Disposition': f'attachment; filename=relatorio_atividade_{relatorio.id}.pdf'
                    }
                )
            except Exception as e:
                print(f"Erro ao decodificar arquivo base64: {e}")
                from flask import abort
                abort(404)
        
        # Se não tem base64, tentar servir do arquivo (compatibilidade com dados antigos)
        if relatorio.arquivo and not (relatorio.arquivo.startswith('base64:') if relatorio.arquivo else False):
            from flask import send_from_directory
            import os
            
            file_path = os.path.dirname(relatorio.arquivo)
            file_name = os.path.basename(relatorio.arquivo)
            static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
            
            try:
                return send_from_directory(
                    os.path.join(static_dir, file_path), 
                    file_name, 
                    as_attachment=True,
                    download_name=f'relatorio_atividade_{relatorio.id}.pdf'
                )
            except Exception as e:
                print(f"Erro ao servir arquivo: {e}")
                from flask import abort
                abort(404)
        
        from flask import abort
        abort(404)
    except Exception as e:
        print(f"Erro ao servir arquivo do relatório de atividades: {e}")
        from flask import abort
        abort(404)

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
# CRUD - MODELOS DE DOCUMENTOS AADVITA
# ============================================

@app.route('/admin/modelos-documentos')
@admin_required
def admin_modelos_documentos():
    documentos = ModeloDocumento.query.order_by(ModeloDocumento.created_at.desc()).all()
    return render_template('admin/modelos_documentos.html', documentos=documentos)

@app.route('/admin/modelos-documentos/novo', methods=['GET', 'POST'])
@admin_required
def admin_modelos_documentos_novo():
    if request.method == 'POST':
        try:
            nome = request.form.get('nome')
            descricao = request.form.get('descricao', '')
            
            if not nome:
                flash('Nome do documento é obrigatório!', 'error')
                return redirect(url_for('admin_modelos_documentos_novo'))
            
            # Upload do arquivo
            if 'arquivo' not in request.files:
                flash('Selecione um arquivo para upload!', 'error')
                return redirect(url_for('admin_modelos_documentos_novo'))
            
            file = request.files['arquivo']
            if file.filename == '':
                flash('Selecione um arquivo para upload!', 'error')
                return redirect(url_for('admin_modelos_documentos_novo'))
            
            # Verificar se é arquivo Word (.doc ou .docx)
            ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
            if ext not in ['doc', 'docx']:
                flash('Apenas arquivos Word (.doc ou .docx) são permitidos!', 'error')
                return redirect(url_for('admin_modelos_documentos_novo'))
            
            # Criar diretório se não existir
            upload_folder = 'static/documents/modelos'
            os.makedirs(upload_folder, exist_ok=True)
            
            # Salvar arquivo
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4()}_{filename}"
            filepath = os.path.join(upload_folder, unique_filename)
            file.save(filepath)
            
            # Obter tamanho do arquivo
            tamanho_arquivo = os.path.getsize(filepath)
            
            # Criar registro no banco
            documento = ModeloDocumento(
                nome=nome,
                descricao=descricao,
                arquivo=f"documents/modelos/{unique_filename}",
                nome_arquivo_original=filename,
                tamanho_arquivo=tamanho_arquivo
            )
            db.session.add(documento)
            db.session.commit()
            flash('Documento adicionado com sucesso!', 'success')
            return redirect(url_for('admin_modelos_documentos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao adicionar documento: {str(e)}', 'error')
            import traceback
            traceback.print_exc()
    
    return render_template('admin/modelos_documentos_form.html')

@app.route('/admin/modelos-documentos/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_modelos_documentos_excluir(id):
    documento = ModeloDocumento.query.get_or_404(id)
    try:
        # Excluir arquivo físico se existir
        if documento.arquivo:
            filepath = os.path.join('static', documento.arquivo)
            if os.path.exists(filepath):
                os.remove(filepath)
        
        # Excluir do banco de dados
        db.session.delete(documento)
        db.session.commit()
        flash('Documento excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir documento: {str(e)}', 'error')
        import traceback
        traceback.print_exc()
    return redirect(url_for('admin_modelos_documentos'))

@app.route('/admin/modelos-documentos/<int:id>/download')
@admin_required
def admin_modelos_documentos_download(id):
    documento = ModeloDocumento.query.get_or_404(id)
    if documento.arquivo:
        filepath = os.path.join('static', documento.arquivo)
        if os.path.exists(filepath):
            directory = os.path.dirname(filepath)
            filename = os.path.basename(filepath)
            return send_from_directory(directory, filename, as_attachment=True, download_name=documento.nome_arquivo_original or filename)
    flash('Arquivo não encontrado!', 'error')
    return redirect(url_for('admin_modelos_documentos'))

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
                        # Ler bytes e salvar também em base64 para persistência no DB (Render)
                        file_data = file.read()
                        file_ext = os.path.splitext(file.filename)[1].lower().replace('.', '')
                        mime_types = {
                            'jpg': 'image/jpeg',
                            'jpeg': 'image/jpeg',
                            'png': 'image/png',
                            'gif': 'image/gif',
                            'webp': 'image/webp'
                        }
                        mime_type = mime_types.get(file_ext, 'image/jpeg')
                        try:
                            foto_base64_data = base64.b64encode(file_data).decode('utf-8')
                        except Exception:
                            foto_base64_data = None

                        # salvar localmente também para ambiente de desenvolvimento
                        try:
                            upload_folder = 'static/images/associados'
                            os.makedirs(upload_folder, exist_ok=True)
                            filename = secure_filename(file.filename)
                            unique_filename = f"{uuid.uuid4()}_{filename}"
                            filepath = os.path.join(upload_folder, unique_filename)
                            file.seek(0)
                            file.save(filepath)
                            foto_path = f"images/associados/{unique_filename}"
                        except Exception as e:
                            print(f"[AVISO] Não foi possível salvar imagem localmente: {e}")
                            foto_path = None
                        # marcar path as base64 reference if we have base64 data
                        if foto_base64_data:
                            foto_path = f"base64:{mime_type}"
                        # atribuir valores no objeto associado abaixo
                    else:
                        flash('Formato de arquivo não permitido. Use JPG, PNG ou GIF.', 'error')
                        return redirect(url_for('admin_associados_novo'))
            
            tipo_associado = request.form.get('tipo_associado', 'contribuinte')
            
            associado = Associado(
                nome_completo=request.form.get('nome_completo'),
                cpf=request.form.get('cpf'),
                data_nascimento=datetime.strptime(data_nascimento_str, "%Y-%m-%d").date(),
                endereco=request.form.get('endereco'),
                telefone=request.form.get('telefone'),
                tipo_associado=tipo_associado,
                valor_mensalidade=float(valor_mensalidade) if valor_mensalidade else 0.0,
                status='aprovado',  # Cadastro pelo admin é aprovado automaticamente
                foto=foto_path,
                foto_base64=(foto_base64_data if 'foto_base64_data' in locals() else None),
                created_at=datetime.now()
            )
            associado.set_password(senha)
            db.session.add(associado)
            db.session.commit()
            
            # Gerar primeira mensalidade apenas se for Contribuinte e tiver valor configurado
            if tipo_associado == 'contribuinte' and associado.valor_mensalidade and associado.valor_mensalidade > 0:
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
            
            # Atualizar tipo de associado
            tipo_associado = request.form.get('tipo_associado', 'contribuinte')
            associado.tipo_associado = tipo_associado
            
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
                        
                        # Ler bytes e salvar também em base64 para persistência no DB (Render)
                        file_data = file.read()
                        file_ext = os.path.splitext(file.filename)[1].lower().replace('.', '')
                        mime_types = {
                            'jpg': 'image/jpeg',
                            'jpeg': 'image/jpeg',
                            'png': 'image/png',
                            'gif': 'image/gif',
                            'webp': 'image/webp'
                        }
                        mime_type = mime_types.get(file_ext, 'image/jpeg')
                        try:
                            foto_base64_data = base64.b64encode(file_data).decode('utf-8')
                        except Exception:
                            foto_base64_data = None

                        # salvar localmente também para ambiente de desenvolvimento
                        try:
                            upload_folder = 'static/images/associados'
                            os.makedirs(upload_folder, exist_ok=True)
                            filename = secure_filename(file.filename)
                            unique_filename = f"{uuid.uuid4()}_{filename}"
                            filepath = os.path.join(upload_folder, unique_filename)
                            file.seek(0)
                            file.save(filepath)
                            associado.foto = f"images/associados/{unique_filename}"
                        except Exception as e:
                            print(f"[AVISO] Não foi possível salvar imagem localmente: {e}")
                            associado.foto = None
                        # marcar path como base64 reference if we have base64 data
                        if foto_base64_data:
                            associado.foto = f"base64:{mime_type}"
                        associado.foto_base64 = (foto_base64_data if foto_base64_data else None)
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
            
            # Se o valor foi alterado, atualizar todas as mensalidades não pagas (apenas para Contribuintes)
            mensalidades_atualizadas = 0
            if tipo_associado == 'contribuinte' and valor_alterado and novo_valor_mensalidade > 0:
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
        
        # Variável para armazenar caminho do arquivo temporário (será deletado no final)
        foto_temp_path = None
        
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
            
            # Usar a variável do escopo externo
            nonlocal foto_temp_path
            
            print(f"[Carteira] Verificando foto do associado {associado.id} ({associado.nome_completo})")
            print(f"[Carteira] associado.foto = {associado.foto}")
            print(f"[Carteira] associado.foto_base64 existe? {bool(getattr(associado, 'foto_base64', None))}")
            
            if associado.foto:
                foto_path = None
                
                # Verificar se a foto está em base64 (Render)
                if associado.foto.startswith('base64:'):
                    foto_base64 = getattr(associado, 'foto_base64', None)
                    if foto_base64:
                        try:
                            import tempfile
                            from PIL import Image as PILImage
                            from io import BytesIO
                            
                            # Extrair o tipo MIME
                            mime_type = associado.foto.replace('base64:', '')
                            print(f"[Carteira] Tipo MIME da foto: {mime_type}")
                            print(f"[Carteira] Tamanho do base64: {len(foto_base64)} caracteres")
                            
                            # Decodificar base64
                            image_data = base64.b64decode(foto_base64)
                            print(f"[Carteira] Foto base64 decodificada, tamanho: {len(image_data)} bytes")
                            
                            # Criar imagem PIL a partir dos bytes
                            img = PILImage.open(BytesIO(image_data))
                            print(f"[Carteira] Imagem PIL criada: {img.size} pixels, formato: {img.format}")
                            
                            # Converter para RGB se necessário (para JPEG)
                            if img.mode != 'RGB':
                                print(f"[Carteira] Convertendo imagem de {img.mode} para RGB")
                                img = img.convert('RGB')
                            
                            # Criar arquivo temporário
                            foto_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                            foto_temp_path = foto_temp_file.name
                            foto_temp_file.close()
                            
                            # Salvar imagem no arquivo temporário
                            img.save(foto_temp_path, 'JPEG', quality=95)
                            print(f"[Carteira] Foto temporária salva em: {foto_temp_path}")
                            print(f"[Carteira] Arquivo existe? {os.path.exists(foto_temp_path)}")
                            
                            foto_path = foto_temp_path
                        except Exception as e:
                            print(f"[Carteira] Erro ao processar foto base64: {e}")
                            import traceback
                            traceback.print_exc()
                            foto_path = None
                    else:
                        print(f"[Carteira] Foto marcada como base64 mas foto_base64 está vazio")
                else:
                    # Tentar usar o caminho do arquivo
                    foto_path = os.path.join('static', associado.foto)
                    print(f"[Carteira] Tentando usar arquivo local: {foto_path}")
                    if not os.path.exists(foto_path):
                        print(f"[Carteira] Arquivo não encontrado: {foto_path}")
                        foto_path = None
                
                if foto_path and os.path.exists(foto_path):
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
                        print(f"[Carteira] Desenhando foto: {foto_path}, tamanho: {foto_w}x{foto_h}, posição: ({foto_x}, {foto_y})")
                        c.drawImage(foto_path, foto_x, foto_y, width=foto_w, height=foto_h, preserveAspectRatio=True)
                        print(f"[Carteira] Foto desenhada com sucesso!")
                    except Exception as e:
                        print(f"[Carteira] Erro ao desenhar foto na carteira: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    print(f"[Carteira] Foto não encontrada ou inválida: {foto_path}")
            else:
                print(f"[Carteira] Associado não possui foto cadastrada")
            
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
        
        # Ler o PDF gerado e converter para base64
        pdf_base64 = None
        try:
            with open(filepath, 'rb') as pdf_file:
                pdf_bytes = pdf_file.read()
                pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
                print(f"[Carteira] PDF convertido para base64, tamanho: {len(pdf_base64)} caracteres")
        except Exception as e:
            print(f"[Carteira] Erro ao converter PDF para base64: {e}")
        
        # Salvar base64 no banco de dados (sem commit - será feito pela função chamadora)
        if pdf_base64:
            try:
                associado.carteira_pdf_base64 = pdf_base64
                associado.carteira_pdf = f"base64:application/pdf"  # Marcar como base64
                # Não fazer commit aqui - será feito pela função que chama
                print(f"[Carteira] PDF preparado para salvar em base64 no banco de dados")
            except Exception as e:
                print(f"[Carteira] Erro ao preparar PDF base64: {e}")
        
        # Limpar arquivo temporário se foi criado (após salvar o PDF)
        if foto_temp_path and os.path.exists(foto_temp_path):
            try:
                os.unlink(foto_temp_path)
                print(f"[Carteira] Arquivo temporário removido: {foto_temp_path}")
            except Exception as e:
                print(f"[Carteira] Erro ao remover arquivo temporário: {e}")
        
        return f"documents/carteiras/{filename}"
        
    except Exception as e:
        print(f"Erro ao gerar carteira PDF: {str(e)}")
        import traceback
        traceback.print_exc()
        # Limpar arquivo temporário em caso de erro
        if 'foto_temp_path' in locals() and foto_temp_path and os.path.exists(foto_temp_path):
            try:
                os.unlink(foto_temp_path)
            except:
                pass
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
        # Recarregar associado do banco para garantir que tem foto_base64 atualizado
        db.session.refresh(associado)
        
        print(f"[Admin Carteira] Gerando carteira para associado {associado.id} - {associado.nome_completo}")
        print(f"[Admin Carteira] Foto: {associado.foto}")
        print(f"[Admin Carteira] Foto base64 existe? {bool(associado.foto_base64)}")
        
        # Deletar carteira antiga se existir (apenas se for arquivo, não base64)
        if associado.carteira_pdf and not associado.carteira_pdf.startswith('base64:'):
            old_filepath = os.path.join('static', associado.carteira_pdf)
            if os.path.exists(old_filepath):
                try:
                    os.remove(old_filepath)
                except Exception as e:
                    print(f"Erro ao deletar carteira antiga: {str(e)}")
        
        # Limpar base64 antigo
        associado.carteira_pdf_base64 = None
        
        # Gerar nova carteira (a função já salva em base64 automaticamente)
        carteira_path = gerar_carteira_pdf(associado)
        
        # Atualizar no banco de dados (a função já atualizou carteira_pdf e carteira_pdf_base64)
        db.session.commit()
        print(f"[Admin Carteira] Carteira gerada e salva com sucesso")
        
        flash(f'Carteira gerada com sucesso para {associado.nome_completo}!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao gerar carteira: {str(e)}', 'error')
    
    return redirect(url_for('admin_carteiras'))

@app.route('/admin/carteiras/<int:id>/pdf')
@admin_required
def admin_carteira_pdf(id):
    """Rota para servir o PDF da carteira do associado"""
    associado = Associado.query.get_or_404(id)
    
    if not associado.carteira_pdf:
        from flask import abort
        abort(404)
    
    # Verificar se está em base64 (Render)
    if associado.carteira_pdf.startswith('base64:') and associado.carteira_pdf_base64:
        try:
            pdf_data = base64.b64decode(associado.carteira_pdf_base64)
            from flask import Response
            return Response(pdf_data, mimetype='application/pdf')
        except Exception as e:
            print(f"Erro ao servir carteira base64: {e}")
            from flask import abort
            abort(404)
    
    # Tentar servir do arquivo (compatibilidade com dados antigos)
    filepath = os.path.join('static', associado.carteira_pdf)
    if not os.path.exists(filepath):
        from flask import abort
        abort(404)
    
    return send_from_directory('static', associado.carteira_pdf, as_attachment=False)

@app.route('/admin/carteiras/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_carteira_excluir(id):
    """Exclui a carteira PDF de um associado"""
    associado = Associado.query.get_or_404(id)
    
    try:
        if associado.carteira_pdf:
            # Deletar arquivo se existir (apenas se não for base64)
            if not associado.carteira_pdf.startswith('base64:'):
                filepath = os.path.join('static', associado.carteira_pdf)
                if os.path.exists(filepath):
                    os.remove(filepath)
            
            # Limpar campos no banco de dados
            associado.carteira_pdf = None
            associado.carteira_pdf_base64 = None
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
        
        # Gerar primeira mensalidade apenas se for Contribuinte e tiver valor configurado
        if associado.tipo_associado == 'contribuinte':
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
    # Verificar se é Associado Regular (não paga mensalidade)
    if associado.tipo_associado == 'regular':
        return  # Associados Regulares não pagam mensalidade
    
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
    
    # Buscar todos os associados aprovados, ativos, Contribuintes (não Regulares) com valor de mensalidade definido
    associados = Associado.query.filter_by(
        status='aprovado',
        ativo=True,
        tipo_associado='contribuinte'
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
        logo_base64_data = None
        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename != '' and allowed_file(file.filename):
                # Ler dados do arquivo e converter para Base64
                file_data = file.read()
                file_ext = os.path.splitext(file.filename)[1].lower().replace('.', '')
                mime_types = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'gif': 'image/gif', 'webp': 'image/webp'}
                mime_type = mime_types.get(file_ext, 'image/jpeg')
                logo_base64_data = base64.b64encode(file_data).decode('utf-8')
                logo_path = f"base64:{mime_type}"  # Store mime type in 'logo' field
                
                # Também salvar localmente para desenvolvimento local (opcional)
                try:
                    upload_folder = app.config['UPLOAD_FOLDER']
                    os.makedirs(upload_folder, exist_ok=True)
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    filepath = os.path.join(upload_folder, unique_filename)
                    file.seek(0)  # Reset file pointer after reading for base64
                    file.save(filepath)
                    # Manter o caminho local também para compatibilidade
                    logo_path = f"images/uploads/{unique_filename}"
                except Exception as e:
                    print(f"[AVISO] Não foi possível salvar arquivo localmente: {e}")
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
                logo_base64=logo_base64_data,
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
                # Remover foto antiga se existir (apenas arquivo local, não base64)
                if apoiador.logo and not (apoiador.logo.startswith('base64:') if apoiador.logo else False):
                    old_filepath = os.path.join('static', apoiador.logo)
                    if os.path.exists(old_filepath):
                        try:
                            os.remove(old_filepath)
                        except:
                            pass
                
                # Ler dados do arquivo e converter para Base64
                file_data = file.read()
                file_ext = os.path.splitext(file.filename)[1].lower().replace('.', '')
                mime_types = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'gif': 'image/gif', 'webp': 'image/webp'}
                mime_type = mime_types.get(file_ext, 'image/jpeg')
                logo_base64_data = base64.b64encode(file_data).decode('utf-8')
                apoiador.logo_base64 = logo_base64_data
                apoiador.logo = f"base64:{mime_type}"  # Store mime type in 'logo' field
                
                # Também salvar localmente para desenvolvimento local (opcional)
                try:
                    upload_folder = app.config['UPLOAD_FOLDER']
                    os.makedirs(upload_folder, exist_ok=True)
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    filepath = os.path.join(upload_folder, unique_filename)
                    file.seek(0)  # Reset file pointer after reading for base64
                    file.save(filepath)
                    # Manter o caminho local também para compatibilidade
                    apoiador.logo = f"images/uploads/{unique_filename}"
                except Exception as e:
                    print(f"[AVISO] Não foi possível salvar arquivo localmente: {e}")
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
        apoiador.logo_descricao = request.form.get('logo_descricao', '').strip() or None
        
        try:
            db.session.commit()
            flash('Apoiador atualizado com sucesso!', 'success')
            return redirect(url_for('admin_apoiadores'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar apoiador: {str(e)}', 'error')
            return redirect(url_for('admin_apoiadores_editar', id=id))
    
    return render_template('admin/apoiador_form.html', apoiador=apoiador)

@app.route('/qrcode/imagem')
def qrcode_imagem():
    """Rota para servir QR code do banco de dados (base64)"""
    try:
        config_base64 = Configuracao.query.filter_by(chave='footer_qrcode_base64').first()
        
        if config_base64 and config_base64.valor:
            # Buscar mime type
            mime_type = 'image/png'  # padrão
            config_mime = Configuracao.query.filter_by(chave='footer_qrcode_mime').first()
            if config_mime and config_mime.valor:
                mime_type = config_mime.valor
            
            try:
                image_data = base64.b64decode(config_base64.valor)
                from flask import Response
                return Response(image_data, mimetype=mime_type)
            except Exception as e:
                print(f"Erro ao decodificar QR code base64: {e}")
                from flask import abort
                abort(404)
        
        # Fallback para arquivo estático
        from flask import send_from_directory
        import os
        static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
        try:
            return send_from_directory(os.path.join(static_dir, 'images'), 'qrcode.png')
        except Exception as e:
            print(f"Erro ao servir arquivo estático do QR code: {e}")
            from flask import abort
            abort(404)
    except Exception as e:
        print(f"Erro na rota qrcode_imagem: {e}")
        import traceback
        traceback.print_exc()
        from flask import abort
        abort(500)

@app.route('/apoiador/<int:id>/logo')
def apoiador_logo(id):
    """Rota para servir imagens do apoiador do banco de dados (base64)"""
    try:
        apoiador = Apoiador.query.get_or_404(id)
        logo_base64 = getattr(apoiador, 'logo_base64', None)
        
        if logo_base64:
            mime_type = 'image/jpeg'
            if apoiador.logo and apoiador.logo.startswith('base64:'):
                mime_type = apoiador.logo.replace('base64:', '')
            try:
                image_data = base64.b64decode(logo_base64)
                from flask import Response
                return Response(image_data, mimetype=mime_type)
            except Exception as e:
                print(f"Erro ao decodificar imagem base64: {e}")
                from flask import abort
                abort(404)
        
        if apoiador.logo and not (apoiador.logo.startswith('base64:') if apoiador.logo else False):
            from flask import send_from_directory
            import os
            static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
            file_path = os.path.dirname(apoiador.logo)
            file_name = os.path.basename(apoiador.logo)
            try:
                return send_from_directory(os.path.join(static_dir, file_path), file_name)
            except Exception as e:
                print(f"Erro ao servir arquivo estático: {e}")
                from flask import abort
                abort(404)
        
        from flask import abort
        abort(404)
    except Exception as e:
        print(f"Erro na rota apoiador_logo: {e}")
        import traceback
        traceback.print_exc()
        from flask import abort
        abort(500)

@app.route('/admin/apoiadores/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_apoiadores_excluir(id):
    apoiador = Apoiador.query.get_or_404(id)
    
    try:
        # Remover logo se existir (apenas arquivo local, não base64)
        if apoiador.logo and not (apoiador.logo.startswith('base64:') if apoiador.logo else False):
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
        
        # Processar upload da imagem - salvar como base64 no banco para persistência no Render
        imagem_base64_data = None
        imagem_path = None
        
        if 'imagem' in request.files:
            file = request.files['imagem']
            if file and file.filename != '' and allowed_file(file.filename):
                # Ler o arquivo e converter para base64
                file_data = file.read()
                file_ext = os.path.splitext(file.filename)[1].lower().replace('.', '')
                
                # Determinar o tipo MIME
                mime_types = {
                    'jpg': 'image/jpeg',
                    'jpeg': 'image/jpeg',
                    'png': 'image/png',
                    'gif': 'image/gif',
                    'webp': 'image/webp'
                }
                mime_type = mime_types.get(file_ext, 'image/jpeg')
                
                # Converter para base64
                imagem_base64_data = base64.b64encode(file_data).decode('utf-8')
                imagem_path = f"base64:{mime_type}"
                
                # Também salvar localmente para desenvolvimento local (opcional)
                try:
                    upload_folder = app.config['UPLOAD_FOLDER']
                    os.makedirs(upload_folder, exist_ok=True)
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    filepath = os.path.join(upload_folder, unique_filename)
                    # Reescrever o arquivo (já foi lido acima)
                    file.seek(0)
                    file.save(filepath)
                except Exception as e:
                    print(f"[AVISO] Não foi possível salvar arquivo localmente: {e}")
            elif file and file.filename != '':
                flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP', 'error')
                return redirect(url_for('admin_slider_novo'))
        
        if not imagem_base64_data:
            flash('A imagem é obrigatória!', 'error')
            return redirect(url_for('admin_slider_novo'))
        
        try:
            nova_imagem = SliderImage(
                titulo=titulo,
                imagem=imagem_path,
                imagem_base64=imagem_base64_data,
                descricao_imagem=request.form.get('descricao_imagem', '').strip() or None,
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
        
        # Processar upload da imagem (se uma nova foi enviada) - salvar como base64
        if 'imagem' in request.files:
            file = request.files['imagem']
            if file and file.filename != '' and allowed_file(file.filename):
                # Ler o arquivo e converter para base64
                file_data = file.read()
                file_ext = os.path.splitext(file.filename)[1].lower().replace('.', '')
                
                # Determinar o tipo MIME
                mime_types = {
                    'jpg': 'image/jpeg',
                    'jpeg': 'image/jpeg',
                    'png': 'image/png',
                    'gif': 'image/gif',
                    'webp': 'image/webp'
                }
                mime_type = mime_types.get(file_ext, 'image/jpeg')
                
                # Converter para base64
                imagem_base64_data = base64.b64encode(file_data).decode('utf-8')
                slider_image.imagem = f"base64:{mime_type}"
                slider_image.imagem_base64 = imagem_base64_data
                
                # Tentar remover imagem antiga do sistema de arquivos (se existir)
                if slider_image.imagem and not slider_image.imagem.startswith('base64:'):
                    old_filepath = os.path.join('static', slider_image.imagem)
                    if os.path.exists(old_filepath):
                        try:
                            os.remove(old_filepath)
                        except:
                            pass
            elif file and file.filename != '':
                flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP', 'error')
                return redirect(url_for('admin_slider_editar', id=id))
        
        # Atualizar dados
        slider_image.titulo = titulo
        slider_image.link = link if link else None
        slider_image.descricao_imagem = request.form.get('descricao_imagem', '').strip() or None
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

@app.route('/slider/<int:id>/imagem')
def slider_imagem(id):
    """Rota para servir imagens do slider do banco de dados (base64)"""
    try:
        slider_image = SliderImage.query.get_or_404(id)
        
        # Verificar se tem imagem_base64 (usando getattr para evitar erro se coluna não existir)
        imagem_base64 = getattr(slider_image, 'imagem_base64', None)
        
        # Se tem imagem em base64, servir ela
        if imagem_base64:
            # Extrair o tipo MIME do campo imagem
            mime_type = 'image/jpeg'  # padrão
            if slider_image.imagem and slider_image.imagem.startswith('base64:'):
                mime_type = slider_image.imagem.replace('base64:', '')
            
            # Decodificar base64
            try:
                image_data = base64.b64decode(imagem_base64)
                from flask import Response
                return Response(image_data, mimetype=mime_type)
            except Exception as e:
                print(f"Erro ao decodificar imagem base64: {e}")
                # Retornar imagem padrão ou erro
                from flask import abort
                abort(404)
        
        # Se não tem base64, tentar servir do arquivo (compatibilidade com dados antigos)
        if slider_image.imagem and not (slider_image.imagem.startswith('base64:') if slider_image.imagem else False):
            from flask import send_from_directory
            import os
            static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
            file_path = os.path.dirname(slider_image.imagem)
            file_name = os.path.basename(slider_image.imagem)
            try:
                return send_from_directory(os.path.join(static_dir, file_path), file_name)
            except:
                from flask import abort
                abort(404)
        
        from flask import abort
        abort(404)
    except Exception as e:
        print(f"Erro ao servir imagem do slider: {e}")
        from flask import abort
        abort(404)

@app.route('/projeto/<int:id>/imagem')
@app.route('/projeto/<slug>/imagem')
def projeto_imagem(id=None, slug=None):
    """Rota para servir imagens de projetos do banco de dados (base64)"""
    try:
        if slug:
            projeto = Projeto.query.filter_by(slug=slug).first_or_404()
        else:
            projeto = Projeto.query.get_or_404(id)
        
        # Verificar se tem imagen_base64 (usando getattr para evitar erro se coluna não existir)
        imagen_base64 = getattr(projeto, 'imagen_base64', None)
        
        # Se tem imagem em base64, servir ela
        if imagen_base64:
            # Extrair o tipo MIME do campo imagen
            mime_type = 'image/jpeg'  # padrão
            if projeto.imagen and projeto.imagen.startswith('base64:'):
                mime_type = projeto.imagen.replace('base64:', '')
            
            # Decodificar base64
            try:
                image_data = base64.b64decode(imagen_base64)
                from flask import Response
                return Response(image_data, mimetype=mime_type)
            except Exception as e:
                print(f"Erro ao decodificar imagem base64: {e}")
                from flask import abort
                abort(404)
        
        # Se não tem base64, tentar servir do arquivo (compatibilidade com dados antigos)
        if projeto.imagen and not (projeto.imagen.startswith('base64:') if projeto.imagen else False):
            from flask import send_from_directory
            import os
            static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
            file_path = os.path.dirname(projeto.imagen)
            file_name = os.path.basename(projeto.imagen)
            try:
                return send_from_directory(os.path.join(static_dir, file_path), file_name)
            except Exception as e:
                print(f"Erro ao servir arquivo estático: {e}")
                from flask import abort
                abort(404)
        
        from flask import abort
        abort(404)
    except Exception as e:
        print(f"Erro ao servir imagem do projeto: {e}")
        import traceback
        traceback.print_exc()
        from flask import abort
        abort(404)

@app.route('/radio-programa/<int:id>/imagem')
def radio_programa_imagem(id):
    """Rota para servir imagens de programas de rádio do banco de dados (base64)"""
    try:
        programa = RadioPrograma.query.get_or_404(id)
        
        # Verificar se tem imagem_base64 (usando getattr para evitar erro se coluna não existir)
        imagem_base64 = getattr(programa, 'imagem_base64', None)
        
        # Se tem imagem em base64, servir ela
        if imagem_base64:
            # Extrair o tipo MIME do campo imagem
            mime_type = 'image/jpeg'  # padrão
            if programa.imagem and programa.imagem.startswith('base64:'):
                mime_type = programa.imagem.replace('base64:', '')
            
            # Decodificar base64
            try:
                image_data = base64.b64decode(imagem_base64)
                from flask import Response
                return Response(image_data, mimetype=mime_type)
            except Exception as e:
                print(f"Erro ao decodificar imagem base64: {e}")
                from flask import abort
                abort(404)
        
        # Se não tem base64, tentar servir do arquivo (compatibilidade com dados antigos)
        if programa.imagem and not (programa.imagem.startswith('base64:') if programa.imagem else False):
            from flask import send_from_directory
            import os
            static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
            file_path = os.path.dirname(programa.imagem)
            file_name = os.path.basename(programa.imagem)
            try:
                return send_from_directory(os.path.join(static_dir, file_path), file_name)
            except Exception as e:
                print(f"Erro ao servir arquivo estático: {e}")
                from flask import abort
                abort(404)
        
        from flask import abort
        abort(404)
    except Exception as e:
        print(f"Erro ao servir imagem do programa de rádio: {e}")
        import traceback
        traceback.print_exc()
        from flask import abort
        abort(404)

@app.route('/acao/<int:id>/imagem')
@app.route('/acao/<slug>/imagem')
def acao_imagem(id=None, slug=None):
    """Rota para servir imagens de ações do banco de dados (base64)"""
    try:
        if slug:
            acao = Acao.query.filter_by(slug=slug).first_or_404()
        else:
            acao = Acao.query.get_or_404(id)
        
        # Verificar se tem imagem_base64 (usando getattr para evitar erro se coluna não existir)
        imagem_base64 = getattr(acao, 'imagem_base64', None)
        
        # Se tem imagem em base64, servir ela
        if imagem_base64:
            # Extrair o tipo MIME do campo imagem
            mime_type = 'image/jpeg'  # padrão
            if acao.imagem and acao.imagem.startswith('base64:'):
                mime_type = acao.imagem.replace('base64:', '')
            
            # Decodificar base64
            try:
                image_data = base64.b64decode(imagem_base64)
                from flask import Response
                return Response(image_data, mimetype=mime_type)
            except Exception as e:
                print(f"Erro ao decodificar imagem base64: {e}")
                from flask import abort
                abort(404)
        
        # Se não tem base64, tentar servir do arquivo (compatibilidade com dados antigos)
        if acao.imagem and not (acao.imagem.startswith('base64:') if acao.imagem else False):
            from flask import send_from_directory
            import os
            static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
            file_path = os.path.dirname(acao.imagem)
            file_name = os.path.basename(acao.imagem)
            try:
                return send_from_directory(os.path.join(static_dir, file_path), file_name)
            except Exception as e:
                print(f"Erro ao servir arquivo estático: {e}")
                from flask import abort
                abort(404)
        
        from flask import abort
        abort(404)
    except Exception as e:
        print(f"Erro ao servir imagem da ação: {e}")
        import traceback
        traceback.print_exc()
        from flask import abort
        abort(404)

@app.route('/informativo/<int:id>/imagem')
@app.route('/informativo/<slug>/imagem')
def informativo_imagem(id=None, slug=None):
    """Rota para servir imagens de informativos do banco de dados (base64)"""
    try:
        if slug:
            informativo = Informativo.query.filter_by(slug=slug).first_or_404()
        else:
            informativo = Informativo.query.get_or_404(id)
        
        # Verificar se tem imagem_base64 (usando getattr para evitar erro se coluna não existir)
        imagem_base64 = getattr(informativo, 'imagem_base64', None)
        
        # Se tem imagem em base64, servir ela
        if imagem_base64:
            # Extrair o tipo MIME do campo imagem
            mime_type = 'image/jpeg'  # padrão
            if informativo.imagem and informativo.imagem.startswith('base64:'):
                mime_type = informativo.imagem.replace('base64:', '')
            
            # Decodificar base64
            try:
                image_data = base64.b64decode(imagem_base64)
                from flask import Response
                return Response(image_data, mimetype=mime_type)
            except Exception as e:
                print(f"Erro ao decodificar imagem base64: {e}")
                from flask import abort
                abort(404)
        
        # Se não tem base64, tentar servir do arquivo (compatibilidade com dados antigos)
        if informativo.imagem and not (informativo.imagem.startswith('base64:') if informativo.imagem else False):
            from flask import send_from_directory
            import os
            static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
            file_path = os.path.dirname(informativo.imagem)
            file_name = os.path.basename(informativo.imagem)
            try:
                return send_from_directory(os.path.join(static_dir, file_path), file_name)
            except Exception as e:
                print(f"Erro ao servir arquivo estático: {e}")
                from flask import abort
                abort(404)
        
        from flask import abort
        abort(404)
    except Exception as e:
        print(f"Erro ao servir imagem do informativo: {e}")
        import traceback
        traceback.print_exc()
        from flask import abort
        abort(404)

@app.route('/diretoria/<int:id>/foto')
def diretoria_foto(id):
    """Rota para servir fotos da diretoria do banco de dados (base64)"""
    try:
        membro = MembroDiretoria.query.get_or_404(id)
        
        # Verificar se tem foto_base64
        foto_base64 = getattr(membro, 'foto_base64', None)
        
        # Se tem foto em base64, servir ela
        if foto_base64:
            # Extrair o tipo MIME do campo foto
            mime_type = 'image/jpeg'  # padrão
            if membro.foto and membro.foto.startswith('base64:'):
                mime_type = membro.foto.replace('base64:', '')
            
            # Decodificar base64
            try:
                image_data = base64.b64decode(foto_base64)
                from flask import Response
                return Response(image_data, mimetype=mime_type)
            except Exception as e:
                print(f"Erro ao decodificar foto base64: {e}")
                from flask import abort
                abort(404)
        
        # Se não tem base64, tentar servir do arquivo (compatibilidade com dados antigos)
        if membro.foto and not (membro.foto.startswith('base64:') if membro.foto else False):
            from flask import send_from_directory
            import os
            static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
            file_path = os.path.dirname(membro.foto)
            file_name = os.path.basename(membro.foto)
            try:
                return send_from_directory(os.path.join(static_dir, file_path), file_name)
            except:
                from flask import abort
                abort(404)
        
        from flask import abort
        abort(404)
    except Exception as e:
        print(f"Erro ao servir foto da diretoria: {e}")
        from flask import abort
        abort(404)

@app.route('/conselho/<int:id>/foto')
def conselho_foto(id):
    """Rota para servir fotos do conselho fiscal do banco de dados (base64)"""
    try:
        membro = MembroConselhoFiscal.query.get_or_404(id)
        
        # Verificar se tem foto_base64
        foto_base64 = getattr(membro, 'foto_base64', None)
        
        # Se tem foto em base64, servir ela
        if foto_base64:
            # Extrair o tipo MIME do campo foto
            mime_type = 'image/jpeg'  # padrão
            if membro.foto and membro.foto.startswith('base64:'):
                mime_type = membro.foto.replace('base64:', '')
            
            # Decodificar base64
            try:
                image_data = base64.b64decode(foto_base64)
                from flask import Response
                return Response(image_data, mimetype=mime_type)
            except Exception as e:
                print(f"Erro ao decodificar foto base64: {e}")
                from flask import abort
                abort(404)
        
        # Se não tem base64, tentar servir do arquivo (compatibilidade com dados antigos)
        if membro.foto and not (membro.foto.startswith('base64:') if membro.foto else False):
            from flask import send_from_directory
            import os
            static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
            file_path = os.path.dirname(membro.foto)
            file_name = os.path.basename(membro.foto)
            try:
                return send_from_directory(os.path.join(static_dir, file_path), file_name)
            except:
                from flask import abort
                abort(404)
        
        from flask import abort
        abort(404)
    except Exception as e:
        print(f"Erro ao servir foto do conselho: {e}")
        from flask import abort
        abort(404)

@app.route('/associado/<int:id>/foto')
def associado_foto(id):
    """Rota para servir fotos de associados do banco de dados (base64)"""
    try:
        associado = Associado.query.get_or_404(id)
        
        # Verificar se tem foto_base64
        foto_base64 = getattr(associado, 'foto_base64', None)
        
        # Se tem foto em base64, servir ela
        if foto_base64:
            # Extrair o tipo MIME do campo foto
            mime_type = 'image/jpeg'  # padrão
            if associado.foto and associado.foto.startswith('base64:'):
                mime_type = associado.foto.replace('base64:', '')
            
            # Decodificar base64
            try:
                image_data = base64.b64decode(foto_base64)
                from flask import Response
                return Response(image_data, mimetype=mime_type)
            except Exception as e:
                print(f"Erro ao decodificar foto base64: {e}")
                from flask import abort
                abort(404)
        
        # Se não tem base64, tentar servir do arquivo (compatibilidade com dados antigos)
        if associado.foto and not (associado.foto.startswith('base64:') if associado.foto else False):
            from flask import send_from_directory
            import os
            static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
            file_path = os.path.dirname(associado.foto)
            file_name = os.path.basename(associado.foto)
            try:
                return send_from_directory(os.path.join(static_dir, file_path), file_name)
            except Exception as e:
                print(f"Erro ao servir arquivo estático: {e}")
                from flask import abort
                abort(404)
        
        from flask import abort
        abort(404)
    except Exception as e:
        print(f"Erro ao servir foto do associado: {e}")
        from flask import abort
        abort(404)

@app.route('/banner-conteudo/<int:id>/imagem')
def banner_conteudo_imagem(id):
    """Rota para servir imagens do banner conteúdo do banco de dados (base64)"""
    try:
        # Garantir que colunas base64 existem antes de fazer queries
        ensure_base64_columns()
        
        conteudo = BannerConteudo.query.get_or_404(id)
        
        # Verificar se tem imagem_base64 (usando getattr para evitar erro se coluna não existir)
        imagem_base64 = getattr(conteudo, 'imagem_base64', None)
        
        # Se tem imagem em base64, servir ela
        if imagem_base64:
            # Extrair o tipo MIME do campo imagem
            mime_type = 'image/jpeg'  # padrão
            if conteudo.imagem and conteudo.imagem.startswith('base64:'):
                mime_type = conteudo.imagem.replace('base64:', '')
            
            # Decodificar base64
            try:
                image_data = base64.b64decode(imagem_base64)
                from flask import Response
                return Response(image_data, mimetype=mime_type)
            except Exception as e:
                print(f"Erro ao decodificar imagem base64: {e}")
                from flask import abort
                abort(404)
        
        # Se não tem base64, tentar servir do arquivo (compatibilidade com dados antigos)
        if conteudo.imagem and not (conteudo.imagem.startswith('base64:') if conteudo.imagem else False):
            from flask import send_from_directory
            import os
            static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
            file_path = os.path.dirname(conteudo.imagem)
            file_name = os.path.basename(conteudo.imagem)
            try:
                return send_from_directory(os.path.join(static_dir, file_path), file_name)
            except Exception as e:
                print(f"Erro ao servir arquivo estático: {e}")
                from flask import abort
                abort(404)
        
        from flask import abort
        abort(404)
    except Exception as e:
        print(f"Erro na rota banner_conteudo_imagem: {e}")
        import traceback
        traceback.print_exc()
        from flask import abort
        abort(500)

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

def gerar_slug(titulo):
    """Gera um slug amigável a partir do título"""
    # Converter para minúsculas
    slug = titulo.lower()
    # Remover acentos
    slug = unicodedata.normalize('NFKD', slug).encode('ascii', 'ignore').decode('ascii')
    # Substituir espaços e caracteres especiais por hífen
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    # Remover hífens no início e fim
    slug = slug.strip('-')
    # Limitar tamanho
    if len(slug) > 200:
        slug = slug[:200].rstrip('-')
    return slug

def gerar_slug_unico(titulo, model_class, item_id=None):
    """Gera um slug único para qualquer modelo, adicionando número se necessário"""
    base_slug = gerar_slug(titulo)
    slug = base_slug
    
    # Verificar se já existe um item com esse slug (exceto o atual)
    contador = 1
    while True:
        query = model_class.query.filter_by(slug=slug)
        if item_id:
            query = query.filter(model_class.id != item_id)
        if not query.first():
            break
        slug = f"{base_slug}-{contador}"
        contador += 1
        if contador > 1000:  # Limite de segurança
            slug = f"{base_slug}-{uuid.uuid4().hex[:8]}"
            break
    
    return slug

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
            
            # Processar upload da imagem (apenas para notícias) - salvar como base64 no banco para persistência no Render
            imagem_path = None
            imagem_base64_data = None
            if tipo == 'Noticia' and 'imagem' in request.files:
                file = request.files['imagem']
                if file and file.filename != '' and allowed_file(file.filename):
                    # Ler o arquivo e converter para base64
                    file_data = file.read()
                    file_ext = os.path.splitext(file.filename)[1].lower().replace('.', '')
                    
                    # Determinar o tipo MIME
                    mime_types = {
                        'jpg': 'image/jpeg',
                        'jpeg': 'image/jpeg',
                        'png': 'image/png',
                        'gif': 'image/gif',
                        'webp': 'image/webp'
                    }
                    mime_type = mime_types.get(file_ext, 'image/jpeg')
                    
                    # Converter para base64
                    imagem_base64_data = base64.b64encode(file_data).decode('utf-8')
                    imagem_path = f"base64:{mime_type}"
                    
                    # Também salvar localmente para desenvolvimento local (opcional)
                    try:
                        upload_folder = app.config['UPLOAD_FOLDER']
                        os.makedirs(upload_folder, exist_ok=True)
                        
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        filepath = os.path.join(upload_folder, unique_filename)
                        file.seek(0)  # Reset file pointer after reading for base64
                        file.save(filepath)
                        imagem_path = f"images/uploads/{unique_filename}"
                    except Exception as e:
                        print(f"[AVISO] Não foi possível salvar imagem localmente: {e}")
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
                imagem_base64=imagem_base64_data,
                descricao_imagem=request.form.get('descricao_imagem', '').strip() or None,
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
            
            # Processar upload da imagem (apenas para notícias) - salvar como base64 no banco para persistência no Render
            if tipo == 'Noticia' and 'imagem' in request.files:
                file = request.files['imagem']
                if file and file.filename != '' and allowed_file(file.filename):
                    # Remover imagem antiga se existir (apenas arquivo local, não base64)
                    if informativo.imagem and not (informativo.imagem.startswith('base64:') if informativo.imagem else False):
                        old_filepath = os.path.join('static', informativo.imagem)
                        if os.path.exists(old_filepath):
                            try:
                                os.remove(old_filepath)
                            except:
                                pass
                    
                    # Ler o arquivo e converter para base64
                    file_data = file.read()
                    file_ext = os.path.splitext(file.filename)[1].lower().replace('.', '')
                    
                    # Determinar o tipo MIME
                    mime_types = {
                        'jpg': 'image/jpeg',
                        'jpeg': 'image/jpeg',
                        'png': 'image/png',
                        'gif': 'image/gif',
                        'webp': 'image/webp'
                    }
                    mime_type = mime_types.get(file_ext, 'image/jpeg')
                    
                    # Converter para base64
                    imagem_base64_data = base64.b64encode(file_data).decode('utf-8')
                    informativo.imagem_base64 = imagem_base64_data
                    informativo.imagem = f"base64:{mime_type}"
                    
                    # Também salvar localmente para desenvolvimento local (opcional)
                    try:
                        upload_folder = app.config['UPLOAD_FOLDER']
                        os.makedirs(upload_folder, exist_ok=True)
                        
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        filepath = os.path.join(upload_folder, unique_filename)
                        file.seek(0)  # Reset file pointer after reading for base64
                        file.save(filepath)
                        informativo.imagem = f"images/uploads/{unique_filename}"
                    except Exception as e:
                        print(f"[AVISO] Não foi possível salvar imagem localmente: {e}")
                elif file and file.filename != '':
                    flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP', 'error')
                    return redirect(url_for('admin_informativos_editar', id=id))
            elif tipo == 'Podcast' and informativo.imagem:
                # Remover imagem se mudou de Noticia para Podcast
                if not (informativo.imagem.startswith('base64:') if informativo.imagem else False):
                    old_filepath = os.path.join('static', informativo.imagem)
                    if os.path.exists(old_filepath):
                        try:
                            os.remove(old_filepath)
                        except:
                            pass
                informativo.imagem = None
                informativo.imagem_base64 = None
            
            informativo.tipo = tipo
            # Atualizar slug se o título mudou
            if informativo.titulo != titulo:
                informativo.slug = gerar_slug_unico(titulo, Informativo, informativo.id)
            
            informativo.titulo = titulo
            informativo.subtitulo = subtitulo if subtitulo else None
            informativo.conteudo = conteudo if tipo == 'Noticia' else None
            informativo.url_soundcloud = url_soundcloud if tipo == 'Podcast' else None
            informativo.descricao_imagem = request.form.get('descricao_imagem', '').strip() or None
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
# CRUD - VOLUNTÁRIOS
# ============================================

@app.route('/admin/voluntarios')
@admin_required
def admin_voluntarios():
    status_filter = request.args.get('status', 'todos')
    voluntarios = Voluntario.query
    
    if status_filter == 'pendentes':
        voluntarios = voluntarios.filter_by(status='pendente')
    elif status_filter == 'aprovados':
        voluntarios = voluntarios.filter_by(status='aprovado')
    elif status_filter == 'inativos':
        voluntarios = voluntarios.filter_by(status='inativo')
    
    voluntarios = voluntarios.order_by(Voluntario.created_at.desc()).all()
    return render_template('admin/voluntarios.html', voluntarios=voluntarios, status_filter=status_filter)

@app.route('/admin/voluntarios/<int:id>')
@admin_required
def admin_voluntarios_detalhe(id):
    voluntario = Voluntario.query.get_or_404(id)
    ofertas = OfertaHoras.query.filter_by(voluntario_id=id).order_by(OfertaHoras.data_inicio.desc()).all()
    agendamentos = AgendamentoVoluntario.query.filter_by(voluntario_id=id).order_by(AgendamentoVoluntario.data_agendamento.desc()).all()
    return render_template('admin/voluntarios_detalhe.html', voluntario=voluntario, ofertas=ofertas, agendamentos=agendamentos)

@app.route('/admin/voluntarios/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_voluntarios_editar(id):
    voluntario = Voluntario.query.get_or_404(id)
    if request.method == 'POST':
        try:
            data_nascimento_str = request.form.get('data_nascimento')
            data_nascimento = None
            if data_nascimento_str:
                try:
                    data_nascimento = datetime.strptime(data_nascimento_str, "%Y-%m-%d").date()
                except:
                    pass
            
            voluntario.nome_completo = request.form.get('nome_completo')
            voluntario.email = request.form.get('email')
            voluntario.telefone = request.form.get('telefone')
            voluntario.cpf = request.form.get('cpf')
            voluntario.endereco = request.form.get('endereco')
            voluntario.cidade = request.form.get('cidade')
            voluntario.estado = request.form.get('estado')
            voluntario.cep = request.form.get('cep')
            voluntario.data_nascimento = data_nascimento
            voluntario.profissao = request.form.get('profissao')
            voluntario.habilidades = request.form.get('habilidades')
            voluntario.disponibilidade = request.form.get('disponibilidade')
            voluntario.area_interesse = request.form.get('area_interesse')
            voluntario.observacoes = request.form.get('observacoes')
            voluntario.status = request.form.get('status', 'pendente')
            voluntario.ativo = request.form.get('ativo') == 'on'

            # Senha opcional definida pelo admin
            senha = request.form.get('senha')
            senha_confirm = request.form.get('senha_confirm')
            if senha or senha_confirm:
                if senha != senha_confirm:
                    flash('As senhas não coincidem.', 'error')
                    return redirect(url_for('admin_voluntarios_editar', id=id))
                if len(senha) < 6:
                    flash('A senha precisa ter pelo menos 6 caracteres.', 'error')
                    return redirect(url_for('admin_voluntarios_editar', id=id))
                try:
                    voluntario.set_password(senha)
                except Exception as e:
                    db.session.rollback()
                    flash('Não foi possível definir a senha: verifique o esquema do banco.', 'error')
                    return redirect(url_for('admin_voluntarios_editar', id=id))
            
            db.session.commit()
            flash('Voluntário atualizado com sucesso!', 'success')
            return redirect(url_for('admin_voluntarios_detalhe', id=id))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar voluntário: {str(e)}', 'error')
    
    return render_template('admin/voluntarios_form.html', voluntario=voluntario)

@app.route('/admin/voluntarios/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_voluntarios_excluir(id):
    voluntario = Voluntario.query.get_or_404(id)
    try:
        db.session.delete(voluntario)
        db.session.commit()
        flash('Voluntário excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir voluntário: {str(e)}', 'error')
    return redirect(url_for('admin_voluntarios'))

# ============================================
# CRUD - OFERTAS DE HORAS
# ============================================

@app.route('/admin/ofertas-horas')
@admin_required
def admin_ofertas_horas():
    status_filter = request.args.get('status', 'todos')
    ofertas = OfertaHoras.query
    
    if status_filter == 'disponiveis':
        ofertas = ofertas.filter_by(status='disponivel')
    elif status_filter == 'agendadas':
        ofertas = ofertas.filter_by(status='agendada')
    elif status_filter == 'concluidas':
        ofertas = ofertas.filter_by(status='concluida')
    
    ofertas = ofertas.order_by(OfertaHoras.data_inicio.desc()).all()
    return render_template('admin/ofertas_horas.html', ofertas=ofertas, status_filter=status_filter)

@app.route('/admin/ofertas-horas/novo', methods=['GET', 'POST'])
@admin_required
def admin_ofertas_horas_novo():
    voluntario_id = request.args.get('voluntario_id')
    voluntarios = Voluntario.query.filter_by(status='aprovado', ativo=True).order_by(Voluntario.nome_completo).all()
    
    if request.method == 'POST':
        try:
            data_inicio_str = request.form.get('data_inicio')
            data_fim_str = request.form.get('data_fim')
            
            data_inicio = datetime.strptime(data_inicio_str, "%Y-%m-%d").date() if data_inicio_str else None
            data_fim = datetime.strptime(data_fim_str, "%Y-%m-%d").date() if data_fim_str else None
            
            horas_totais = None
            if request.form.get('horas_totais'):
                try:
                    horas_totais = float(request.form.get('horas_totais'))
                except:
                    pass
            
            oferta = OfertaHoras(
                voluntario_id=request.form.get('voluntario_id'),
                data_inicio=data_inicio,
                data_fim=data_fim,
                hora_inicio=request.form.get('hora_inicio'),
                hora_fim=request.form.get('hora_fim'),
                dias_semana=request.form.get('dias_semana'),
                horas_totais=horas_totais,
                descricao=request.form.get('descricao'),
                area_atividade=request.form.get('area_atividade'),
                status=request.form.get('status', 'disponivel')
            )
            db.session.add(oferta)
            db.session.commit()
            flash('Oferta de horas criada com sucesso!', 'success')
            return redirect(url_for('admin_ofertas_horas'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar oferta: {str(e)}', 'error')
    
    return render_template('admin/ofertas_horas_form.html', oferta=None, voluntarios=voluntarios, voluntario_id=voluntario_id)

@app.route('/admin/ofertas-horas/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_ofertas_horas_editar(id):
    oferta = OfertaHoras.query.get_or_404(id)
    voluntarios = Voluntario.query.filter_by(status='aprovado', ativo=True).order_by(Voluntario.nome_completo).all()
    
    if request.method == 'POST':
        try:
            data_inicio_str = request.form.get('data_inicio')
            data_fim_str = request.form.get('data_fim')
            
            oferta.data_inicio = datetime.strptime(data_inicio_str, "%Y-%m-%d").date() if data_inicio_str else None
            oferta.data_fim = datetime.strptime(data_fim_str, "%Y-%m-%d").date() if data_fim_str else None
            oferta.hora_inicio = request.form.get('hora_inicio')
            oferta.hora_fim = request.form.get('hora_fim')
            oferta.dias_semana = request.form.get('dias_semana')
            oferta.area_atividade = request.form.get('area_atividade')
            oferta.descricao = request.form.get('descricao')
            oferta.status = request.form.get('status', 'disponivel')
            
            horas_totais = None
            if request.form.get('horas_totais'):
                try:
                    horas_totais = float(request.form.get('horas_totais'))
                except:
                    pass
            oferta.horas_totais = horas_totais
            
            db.session.commit()
            flash('Oferta de horas atualizada com sucesso!', 'success')
            return redirect(url_for('admin_ofertas_horas'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar oferta: {str(e)}', 'error')
    
    return render_template('admin/ofertas_horas_form.html', oferta=oferta, voluntarios=voluntarios)

@app.route('/admin/ofertas-horas/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_ofertas_horas_excluir(id):
    oferta = OfertaHoras.query.get_or_404(id)
    try:
        db.session.delete(oferta)
        db.session.commit()
        flash('Oferta de horas excluída com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir oferta: {str(e)}', 'error')
    return redirect(url_for('admin_ofertas_horas'))

# ============================================
# CRUD - AGENDAMENTOS DE VOLUNTÁRIOS
# ============================================

@app.route('/admin/agendamentos-voluntarios')
@admin_required
def admin_agendamentos_voluntarios():
    status_filter = request.args.get('status', 'todos')
    agendamentos = AgendamentoVoluntario.query
    
    if status_filter == 'agendados':
        agendamentos = agendamentos.filter_by(status='agendado')
    elif status_filter == 'confirmados':
        agendamentos = agendamentos.filter_by(status='confirmado')
    elif status_filter == 'em_andamento':
        agendamentos = agendamentos.filter_by(status='em_andamento')
    elif status_filter == 'concluidos':
        agendamentos = agendamentos.filter_by(status='concluido')
    elif status_filter == 'cancelados':
        agendamentos = agendamentos.filter_by(status='cancelado')
    
    agendamentos = agendamentos.order_by(AgendamentoVoluntario.data_agendamento.desc()).all()
    return render_template('admin/agendamentos_voluntarios.html', agendamentos=agendamentos, status_filter=status_filter)

@app.route('/admin/agendamentos-voluntarios/novo', methods=['GET', 'POST'])
@admin_required
def admin_agendamentos_voluntarios_novo():
    voluntario_id = request.args.get('voluntario_id')
    oferta_id = request.args.get('oferta_id')
    voluntarios = Voluntario.query.filter_by(status='aprovado', ativo=True).order_by(Voluntario.nome_completo).all()
    ofertas = OfertaHoras.query.filter_by(status='disponivel').order_by(OfertaHoras.data_inicio.desc()).all() if not oferta_id else []
    
    if request.method == 'POST':
        try:
            data_agendamento_str = request.form.get('data_agendamento')
            data_agendamento = datetime.strptime(data_agendamento_str, "%Y-%m-%d").date() if data_agendamento_str else None
            
            oferta_horas_id = request.form.get('oferta_horas_id')
            if oferta_horas_id == '':
                oferta_horas_id = None
            
            agendamento = AgendamentoVoluntario(
                voluntario_id=request.form.get('voluntario_id'),
                oferta_horas_id=oferta_horas_id,
                data_agendamento=data_agendamento,
                hora_inicio=request.form.get('hora_inicio'),
                hora_fim=request.form.get('hora_fim'),
                atividade=request.form.get('atividade'),
                descricao=request.form.get('descricao'),
                responsavel=request.form.get('responsavel'),
                contato_responsavel=request.form.get('contato_responsavel'),
                local=request.form.get('local'),
                observacoes=request.form.get('observacoes'),
                status=request.form.get('status', 'agendado')
            )
            db.session.add(agendamento)
            
            # Atualizar status da oferta se foi vinculada
            if oferta_horas_id:
                oferta = OfertaHoras.query.get(oferta_horas_id)
                if oferta:
                    oferta.status = 'agendada'
            
            db.session.commit()
            flash('Agendamento criado com sucesso!', 'success')
            return redirect(url_for('admin_agendamentos_voluntarios'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar agendamento: {str(e)}', 'error')
    
    return render_template('admin/agendamentos_voluntarios_form.html', agendamento=None, voluntarios=voluntarios, ofertas=ofertas, voluntario_id=voluntario_id, oferta_id=oferta_id)

@app.route('/admin/agendamentos-voluntarios/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_agendamentos_voluntarios_editar(id):
    agendamento = AgendamentoVoluntario.query.get_or_404(id)
    voluntarios = Voluntario.query.filter_by(status='aprovado', ativo=True).order_by(Voluntario.nome_completo).all()
    ofertas = OfertaHoras.query.order_by(OfertaHoras.data_inicio.desc()).all()
    
    if request.method == 'POST':
        try:
            data_agendamento_str = request.form.get('data_agendamento')
            agendamento.data_agendamento = datetime.strptime(data_agendamento_str, "%Y-%m-%d").date() if data_agendamento_str else None
            agendamento.hora_inicio = request.form.get('hora_inicio')
            agendamento.hora_fim = request.form.get('hora_fim')
            agendamento.atividade = request.form.get('atividade')
            agendamento.descricao = request.form.get('descricao')
            agendamento.responsavel = request.form.get('responsavel')
            agendamento.contato_responsavel = request.form.get('contato_responsavel')
            agendamento.local = request.form.get('local')
            agendamento.observacoes = request.form.get('observacoes')
            agendamento.status = request.form.get('status', 'agendado')
            
            oferta_horas_id = request.form.get('oferta_horas_id')
            if oferta_horas_id == '':
                oferta_horas_id = None
            agendamento.oferta_horas_id = oferta_horas_id
            
            db.session.commit()
            flash('Agendamento atualizado com sucesso!', 'success')
            return redirect(url_for('admin_agendamentos_voluntarios'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar agendamento: {str(e)}', 'error')
    
    return render_template('admin/agendamentos_voluntarios_form.html', agendamento=agendamento, voluntarios=voluntarios, ofertas=ofertas)

@app.route('/admin/agendamentos-voluntarios/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_agendamentos_voluntarios_excluir(id):
    agendamento = AgendamentoVoluntario.query.get_or_404(id)
    try:
        # Liberar oferta se estava vinculada
        if agendamento.oferta_horas_id:
            oferta = OfertaHoras.query.get(agendamento.oferta_horas_id)
            if oferta and oferta.status == 'agendada':
                oferta.status = 'disponivel'
        
        db.session.delete(agendamento)
        db.session.commit()
        flash('Agendamento excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir agendamento: {str(e)}', 'error')
    return redirect(url_for('admin_agendamentos_voluntarios'))

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
            
            # Processar upload da imagem - salvar como base64 no banco para persistência no Render
            imagem_path = None
            imagem_base64_data = None
            if 'imagem' in request.files:
                file = request.files['imagem']
                if file and file.filename != '' and allowed_file(file.filename):
                    # Ler o arquivo e converter para base64
                    file_data = file.read()
                    file_ext = os.path.splitext(file.filename)[1].lower().replace('.', '')
                    
                    # Determinar o tipo MIME
                    mime_types = {
                        'jpg': 'image/jpeg',
                        'jpeg': 'image/jpeg',
                        'png': 'image/png',
                        'gif': 'image/gif',
                        'webp': 'image/webp'
                    }
                    mime_type = mime_types.get(file_ext, 'image/jpeg')
                    
                    # Converter para base64
                    imagem_base64_data = base64.b64encode(file_data).decode('utf-8')
                    imagem_path = f"base64:{mime_type}"
                    
                    # Também salvar localmente para desenvolvimento local (opcional)
                    try:
                        upload_folder = app.config['UPLOAD_FOLDER']
                        os.makedirs(upload_folder, exist_ok=True)
                        
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        filepath = os.path.join(upload_folder, unique_filename)
                        file.seek(0)  # Reset file pointer after reading for base64
                        file.save(filepath)
                        imagem_path = f"images/uploads/{unique_filename}"
                    except Exception as e:
                        print(f"[AVISO] Não foi possível salvar imagem localmente: {e}")
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
                imagem_base64=imagem_base64_data,
                descricao_imagem=request.form.get('descricao_imagem', '').strip() or None,
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
            
            # Processar upload da imagem - salvar como base64 no banco para persistência no Render
            if 'imagem' in request.files:
                file = request.files['imagem']
                if file and file.filename != '' and allowed_file(file.filename):
                    # Remover imagem antiga se existir (apenas arquivo local, não base64)
                    if programa.imagem and not (programa.imagem.startswith('base64:') if programa.imagem else False):
                        old_filepath = os.path.join('static', programa.imagem)
                        if os.path.exists(old_filepath):
                            try:
                                os.remove(old_filepath)
                            except:
                                pass
                    
                    # Ler o arquivo e converter para base64
                    file_data = file.read()
                    file_ext = os.path.splitext(file.filename)[1].lower().replace('.', '')
                    
                    # Determinar o tipo MIME
                    mime_types = {
                        'jpg': 'image/jpeg',
                        'jpeg': 'image/jpeg',
                        'png': 'image/png',
                        'gif': 'image/gif',
                        'webp': 'image/webp'
                    }
                    mime_type = mime_types.get(file_ext, 'image/jpeg')
                    
                    # Converter para base64
                    imagem_base64_data = base64.b64encode(file_data).decode('utf-8')
                    programa.imagem_base64 = imagem_base64_data
                    programa.imagem = f"base64:{mime_type}"
                    
                    # Também salvar localmente para desenvolvimento local (opcional)
                    try:
                        upload_folder = app.config['UPLOAD_FOLDER']
                        os.makedirs(upload_folder, exist_ok=True)
                        
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        filepath = os.path.join(upload_folder, unique_filename)
                        file.seek(0)  # Reset file pointer after reading for base64
                        file.save(filepath)
                        programa.imagem = f"images/uploads/{unique_filename}"
                    except Exception as e:
                        print(f"[AVISO] Não foi possível salvar imagem localmente: {e}")
                elif file and file.filename != '':
                    flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP', 'error')
                    return redirect(url_for('admin_radio_editar', id=id))
            
            programa.nome = nome
            programa.descricao = descricao if descricao else None
            programa.apresentador = apresentador if apresentador else None
            programa.horario = horario if horario else None
            programa.url_streaming = url_streaming if url_streaming else None
            programa.url_arquivo = url_arquivo if url_arquivo else None
            programa.descricao_imagem = request.form.get('descricao_imagem', '').strip() or None
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
# CRUD - RECICLAGEM
# ============================================

@app.route('/admin/reciclagem')
@admin_required
def admin_reciclagem():
    """Lista todas as solicitações de reciclagem"""
    status_filter = request.args.get('status', 'todos')
    
    if status_filter == 'pendente':
        reciclagens = Reciclagem.query.filter_by(status='pendente').order_by(Reciclagem.created_at.desc()).all()
    elif status_filter == 'em_andamento':
        reciclagens = Reciclagem.query.filter_by(status='em_andamento').order_by(Reciclagem.created_at.desc()).all()
    elif status_filter == 'coletado':
        reciclagens = Reciclagem.query.filter_by(status='coletado').order_by(Reciclagem.created_at.desc()).all()
    elif status_filter == 'cancelado':
        reciclagens = Reciclagem.query.filter_by(status='cancelado').order_by(Reciclagem.created_at.desc()).all()
    else:
        reciclagens = Reciclagem.query.order_by(Reciclagem.created_at.desc()).all()
    
    # Contar por status
    pendentes_count = Reciclagem.query.filter_by(status='pendente').count()
    em_andamento_count = Reciclagem.query.filter_by(status='em_andamento').count()
    coletados_count = Reciclagem.query.filter_by(status='coletado').count()
    cancelados_count = Reciclagem.query.filter_by(status='cancelado').count()
    
    return render_template('admin/reciclagem.html',
                         reciclagens=reciclagens,
                         status_filter=status_filter,
                         pendentes_count=pendentes_count,
                         em_andamento_count=em_andamento_count,
                         coletados_count=coletados_count,
                         cancelados_count=cancelados_count)

@app.route('/admin/reciclagem/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_reciclagem_editar(id):
    """Edita uma solicitação de reciclagem"""
    reciclagem = Reciclagem.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            reciclagem.status = request.form.get('status', 'pendente')
            reciclagem.observacoes_admin = request.form.get('observacoes_admin', '').strip() or None
            reciclagem.updated_at = datetime.now()
            
            db.session.commit()
            flash('Solicitação de reciclagem atualizada com sucesso!', 'success')
            return redirect(url_for('admin_reciclagem'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar solicitação: {str(e)}', 'error')
    
    return render_template('admin/reciclagem_form.html', reciclagem=reciclagem)

@app.route('/admin/reciclagem/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_reciclagem_excluir(id):
    """Exclui uma solicitação de reciclagem"""
    reciclagem = Reciclagem.query.get_or_404(id)
    
    try:
        db.session.delete(reciclagem)
        db.session.commit()
        flash('Solicitação de reciclagem excluída com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir solicitação: {str(e)}', 'error')
    
    return redirect(url_for('admin_reciclagem'))

# ============================================
# CRUD - BANNERS
# ============================================

@app.route('/admin/banners')
@admin_required
def admin_banners():
    # Garantir que colunas base64 existem antes de fazer queries
    ensure_base64_columns()
    
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
    # Garantir que colunas base64 existem antes de fazer queries
    ensure_base64_columns()
    
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
            banner.descricao_imagem = request.form.get('descricao_imagem', '').strip() or None
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
    # Garantir que colunas base64 existem antes de fazer queries
    ensure_base64_columns()
    
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
            
            # Processar upload da imagem - salvar como base64 no banco para persistência no Render
            imagem_path = None
            imagem_base64_data = None
            if 'imagem' in request.files:
                file = request.files['imagem']
                if file and file.filename != '' and allowed_file(file.filename):
                    # Ler o arquivo e converter para base64
                    file_data = file.read()
                    file_ext = os.path.splitext(file.filename)[1].lower().replace('.', '')
                    
                    # Determinar o tipo MIME
                    mime_types = {
                        'jpg': 'image/jpeg',
                        'jpeg': 'image/jpeg',
                        'png': 'image/png',
                        'gif': 'image/gif',
                        'webp': 'image/webp'
                    }
                    mime_type = mime_types.get(file_ext, 'image/jpeg')
                    
                    # Converter para base64
                    imagem_base64_data = base64.b64encode(file_data).decode('utf-8')
                    imagem_path = f"base64:{mime_type}"
                    
                    # Também salvar localmente para desenvolvimento local (opcional)
                    try:
                        upload_folder = app.config['UPLOAD_FOLDER']
                        os.makedirs(upload_folder, exist_ok=True)
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        filepath = os.path.join(upload_folder, unique_filename)
                        file.seek(0)  # Reset file pointer after reading for base64
                        file.save(filepath)
                        imagem_path = f"images/uploads/{unique_filename}"
                    except Exception as e:
                        print(f"[AVISO] Não foi possível salvar arquivo localmente: {e}")
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
            
            # Processar conteúdo: converter quebras de linha em parágrafos HTML
            conteudo_processado = processar_texto_paragrafos(conteudo) if conteudo else None
            
            # Obter descricao_imagem
            descricao_imagem = request.form.get('descricao_imagem', '').strip() or None
            
            novo_conteudo = BannerConteudo(
                banner_id=banner_id,
                titulo=titulo,
                conteudo=conteudo_processado,
                imagem=imagem_path,
                imagem_base64=imagem_base64_data,
                descricao_imagem=descricao_imagem,
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
    # Garantir que colunas base64 existem antes de fazer queries
    ensure_base64_columns()
    
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
            
            # Processar upload da imagem - salvar como base64 no banco para persistência no Render
            if 'imagem' in request.files:
                file = request.files['imagem']
                if file and file.filename != '' and allowed_file(file.filename):
                    # Remover imagem antiga se existir (apenas arquivo local, não base64)
                    if conteudo.imagem and not (conteudo.imagem.startswith('base64:') if conteudo.imagem else False):
                        old_filepath = os.path.join('static', conteudo.imagem)
                        if os.path.exists(old_filepath):
                            try:
                                os.remove(old_filepath)
                            except:
                                pass
                    
                    # Ler o arquivo e converter para base64
                    file_data = file.read()
                    file_ext = os.path.splitext(file.filename)[1].lower().replace('.', '')
                    
                    # Determinar o tipo MIME
                    mime_types = {
                        'jpg': 'image/jpeg',
                        'jpeg': 'image/jpeg',
                        'png': 'image/png',
                        'gif': 'image/gif',
                        'webp': 'image/webp'
                    }
                    mime_type = mime_types.get(file_ext, 'image/jpeg')
                    
                    # Converter para base64
                    imagem_base64_data = base64.b64encode(file_data).decode('utf-8')
                    conteudo.imagem_base64 = imagem_base64_data
                    conteudo.imagem = f"base64:{mime_type}"
                    
                    # Também salvar localmente para desenvolvimento local (opcional)
                    try:
                        upload_folder = app.config['UPLOAD_FOLDER']
                        os.makedirs(upload_folder, exist_ok=True)
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        filepath = os.path.join(upload_folder, unique_filename)
                        file.seek(0)  # Reset file pointer after reading for base64
                        file.save(filepath)
                        conteudo.imagem = f"images/uploads/{unique_filename}"
                    except Exception as e:
                        print(f"[AVISO] Não foi possível salvar arquivo localmente: {e}")
                elif file and file.filename != '':
                    flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP', 'error')
                    return redirect(url_for('admin_banner_conteudo_editar', id=id))
            
            # Remover imagem se solicitado
            if request.form.get('remover_imagem') == '1':
                if conteudo.imagem and not (conteudo.imagem.startswith('base64:') if conteudo.imagem else False):
                    old_filepath = os.path.join('static', conteudo.imagem)
                    if os.path.exists(old_filepath):
                        try:
                            os.remove(old_filepath)
                        except:
                            pass
                conteudo.imagem = None
                conteudo.imagem_base64 = None
            
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
            
            # Processar conteúdo: converter quebras de linha em parágrafos HTML
            conteudo_processado = processar_texto_paragrafos(conteudo_text) if conteudo_text else None
            
            # Obter descricao_imagem
            descricao_imagem = request.form.get('descricao_imagem', '').strip() or None
            
            conteudo.titulo = titulo
            conteudo.conteudo = conteudo_processado
            conteudo.descricao_imagem = descricao_imagem
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
        # Mostrar lista de associados (apenas Contribuintes)
        associados = Associado.query.filter_by(
            status='aprovado',
            tipo_associado='contribuinte'
        ).order_by(Associado.nome_completo.asc()).all()
        
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
    # CRÍTICO: Garantir que colunas base64 existem ANTES de qualquer query
    # Isso deve ser feito PRIMEIRO, antes de qualquer query que use modelos com essas colunas
    ensure_base64_columns()
    
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
        # Garantir que a coluna está entre 1 e 3
        coluna = servico.coluna if servico.coluna in [1, 2, 3] else 1
        if coluna in servicos_por_coluna:
            servicos_por_coluna[coluna].append(servico)
    
    # Debug: verificar distribuição de serviços por coluna
    total_servicos = len(servicos_por_coluna[1]) + len(servicos_por_coluna[2]) + len(servicos_por_coluna[3])
    print(f"[DEBUG] Total de serviços: {total_servicos}")
    print(f"[DEBUG] Serviços por coluna - Coluna 1: {len(servicos_por_coluna[1])}, Coluna 2: {len(servicos_por_coluna[2])}, Coluna 3: {len(servicos_por_coluna[3])}")
    
    # Redistribuir automaticamente os serviços entre as 3 colunas de forma equilibrada
    # Isso garante que os serviços sejam distribuídos horizontalmente (1, 2, 3, 1, 2, 3...)
    if total_servicos > 0:
        # Verificar se a distribuição está desequilibrada (diferença maior que 1 entre colunas)
        tamanhos = [len(servicos_por_coluna[1]), len(servicos_por_coluna[2]), len(servicos_por_coluna[3])]
        max_tamanho = max(tamanhos)
        min_tamanho = min(tamanhos)
        
        # Se a diferença for maior que 1, redistribuir
        if max_tamanho - min_tamanho > 1:
            print(f"[DEBUG] Distribuição desequilibrada detectada. Redistribuindo automaticamente...")
            # Coletar todos os serviços ordenados
            todos_servicos = []
            for col in [1, 2, 3]:
                todos_servicos.extend(servicos_por_coluna[col])
            
            # Redistribuir em round-robin: 1, 2, 3, 1, 2, 3...
            servicos_por_coluna = {1: [], 2: [], 3: []}
            for idx, servico in enumerate(todos_servicos):
                coluna = (idx % 3) + 1
                servicos_por_coluna[coluna].append(servico)
                # Atualizar no banco também
                if servico.coluna != coluna:
                    servico.coluna = coluna
            db.session.commit()
            print(f"[DEBUG] Redistribuição concluída - Coluna 1: {len(servicos_por_coluna[1])}, Coluna 2: {len(servicos_por_coluna[2])}, Coluna 3: {len(servicos_por_coluna[3])}")
    
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
        # Verificar se precisa atualizar (posts antigos ou não existem)
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
        # IMPORTANTE: Throttling para evitar múltiplas atualizações simultâneas
        if precisa_atualizar:
            global _instagram_update_lock, _instagram_last_update_time, _instagram_update_interval
            
            # Verificar se já existe uma atualização em andamento
            if _instagram_update_lock:
                print(f"[Instagram] Atualização já em andamento, pulando...")
            # Verificar se a última atualização foi há menos de 6 horas
            elif _instagram_last_update_time and (datetime.utcnow() - _instagram_last_update_time) < _instagram_update_interval:
                print(f"[Instagram] Última atualização foi há menos de 6 horas, pulando...")
            else:
                # Marcar como em atualização e iniciar thread
                _instagram_update_lock = True
                threading.Thread(target=start_instagram_updater, args=(instagram_username, instagram_url), daemon=True).start()
    
    # Funções helper para tradução de conteúdos dinâmicos
    current_lang = session.get('language', 'pt')
    
    # Dicionário de tradução estático para serviços "O que fazemos"
    servicos_translations = {
        'pt': {},
        'es': {
            'Biblioteca': 'Biblioteca',
            'Espaço de leitura inclusiva com livros em Braille, audiolivros e materiais acessíveis que estimulam o aprendizado e a imaginação.': 'Espacio de lectura inclusiva con libros en Braille, audiolibros y materiales accesibles que estimulan el aprendizaje y la imaginación.',
            'Serviço Social': 'Servicio Social',
            'Orientação e apoio às famílias, auxiliando no acesso a benefícios, políticas públicas e encaminhamentos sociais.': 'Orientación y apoyo a las familias, ayudando en el acceso a beneficios, políticas públicas y derivaciones sociales.',
            'Educação': 'Educación',
            'Ações educativas e oficinas que garantem acesso ao conhecimento, alfabetização e inclusão escolar para todos.': 'Acciones educativas y talleres que garantizan el acceso al conocimiento, alfabetización e inclusión escolar para todos.',
            'Ensino em Braille': 'Enseñanza en Braille',
            'Aulas práticas e personalizadas que ensinam o sistema Braille, essencial para a leitura, escrita e independência educacional.': 'Clases prácticas y personalizadas que enseñan el sistema Braille, esencial para la lectura, escritura e independencia educativa.',
            'Terapia Ocupacional': 'Terapia Ocupacional',
            'Atividades que desenvolvem habilidades motoras e funcionais, promovendo autonomia e qualidade de vida no dia a dia.': 'Actividades que desarrollan habilidades motoras y funcionales, promoviendo autonomía y calidad de vida en el día a día.',
            'Rádio': 'Radio',
            'Canal de comunicação e informação acessível, onde a voz da inclusão é transmitida através de notícias, entrevistas e programas educativos.': 'Canal de comunicación e información accesible, donde la voz de la inclusión se transmite a través de noticias, entrevistas y programas educativos.',
            'Informática e novas tecnologias': 'Informática y nuevas tecnologías',
            'Capacitação em informática acessível e uso de tecnologias assistivas, promovendo autonomia digital e oportunidades de inserção profissional.': 'Capacitación en informática accesible y uso de tecnologías asistivas, promoviendo autonomía digital y oportunidades de inserción profesional.',
            'Projetos': 'Proyectos',
            'Iniciativas sociais e comunitárias que fortalecem os direitos, a cidadania e a qualidade de vida das pessoas com deficiência visual.': 'Iniciativas sociales y comunitarias que fortalecen los derechos, la ciudadanía y la calidad de vida de las personas con discapacidad visual.',
            'Música': 'Música',
            'Espaço de expressão artística e sensorial, que estimula talentos, integração e sensibilidade através do som e do ritmo.': 'Espacio de expresión artística y sensorial, que estimula talentos, integración y sensibilidad a través del sonido y el ritmo.',
        },
        'en': {
            'Biblioteca': 'Library',
            'Espaço de leitura inclusiva com livros em Braille, audiolivros e materiais acessíveis que estimulam o aprendizado e a imaginação.': 'Inclusive reading space with Braille books, audiobooks and accessible materials that stimulate learning and imagination.',
            'Serviço Social': 'Social Service',
            'Orientação e apoio às famílias, auxiliando no acesso a benefícios, políticas públicas e encaminhamentos sociais.': 'Guidance and support to families, assisting in access to benefits, public policies and social referrals.',
            'Educação': 'Education',
            'Ações educativas e oficinas que garantem acesso ao conhecimento, alfabetização e inclusão escolar para todos.': 'Educational actions and workshops that guarantee access to knowledge, literacy and school inclusion for everyone.',
            'Ensino em Braille': 'Braille Teaching',
            'Aulas práticas e personalizadas que ensinam o sistema Braille, essencial para a leitura, escrita e independência educacional.': 'Practical and personalized classes that teach the Braille system, essential for reading, writing and educational independence.',
            'Terapia Ocupacional': 'Occupational Therapy',
            'Atividades que desenvolvem habilidades motoras e funcionais, promovendo autonomia e qualidade de vida no dia a dia.': 'Activities that develop motor and functional skills, promoting autonomy and quality of life in daily life.',
            'Rádio': 'Radio',
            'Canal de comunicação e informação acessível, onde a voz da inclusão é transmitida através de notícias, entrevistas e programas educativos.': 'Accessible communication and information channel, where the voice of inclusion is transmitted through news, interviews and educational programs.',
            'Informática e novas tecnologias': 'Computer Science and New Technologies',
            'Capacitação em informática acessível e uso de tecnologias assistivas, promovendo autonomia digital e oportunidades de inserção profissional.': 'Training in accessible computing and use of assistive technologies, promoting digital autonomy and professional insertion opportunities.',
            'Projetos': 'Projects',
            'Iniciativas sociais e comunitárias que fortalecem os direitos, a cidadania e a qualidade de vida das pessoas com deficiência visual.': 'Social and community initiatives that strengthen the rights, citizenship and quality of life of visually impaired people.',
            'Música': 'Music',
            'Espaço de expressão artística e sensorial, que estimula talentos, integração e sensibilidade através do som e do ritmo.': 'Space for artistic and sensory expression, which stimulates talents, integration and sensitivity through sound and rhythm.',
        }
    }
    
    def get_servico_text(servico, field):
        """Retorna texto traduzido do serviço 'O que fazemos'"""
        if not servico:
            return ''
        texto_original = getattr(servico, field, '')
        if not texto_original:
            return ''
        # Tentar tradução estática primeiro
        if current_lang in servicos_translations and texto_original in servicos_translations[current_lang]:
            return servicos_translations[current_lang][texto_original]
        # Se não encontrar tradução, retorna o original
        return texto_original
    
    def get_reunion_text(reunion, field):
        """Retorna texto traduzido da reunião"""
        if not reunion:
            return ''
        # Por enquanto, retorna o texto original
        return getattr(reunion, field, '')
    
    def get_projeto_text(projeto, field):
        """Retorna texto traduzido do projeto"""
        if not projeto:
            return ''
        # Por enquanto, retorna o texto original
        return getattr(projeto, field, '')
    
    def get_evento_text(evento, field):
        """Retorna texto traduzido do evento"""
        if not evento:
            return ''
        # Por enquanto, retorna o texto original
        return getattr(evento, field, '')
    
    def get_acao_text(acao, field):
        """Retorna texto traduzido da ação"""
        if not acao:
            return ''
        # Por enquanto, retorna o texto original
        return getattr(acao, field, '')
    
    def get_video_text(video, field):
        """Retorna texto traduzido do vídeo"""
        if not video:
            return ''
        # Por enquanto, retorna o texto original
        return getattr(video, field, '')
    
    # Dicionário de tradução estático para banners
    banners_translations = {
        'pt': {},
        'es': {
            'Campanhas': 'Campañas',
            'Apoie-nos': 'Apóyanos',
            'Editais': 'Editales',
        },
        'en': {
            'Campanhas': 'Campaigns',
            'Apoie-nos': 'Support Us',
            'Editais': 'Public Notices',
        }
    }
    
    def get_banner_text(banner, field):
        """Retorna texto traduzido do banner"""
        if not banner:
            return ''
        texto_original = getattr(banner, field, '')
        if not texto_original:
            return ''
        # Tentar tradução estática primeiro
        if current_lang in banners_translations and texto_original in banners_translations[current_lang]:
            return banners_translations[current_lang][texto_original]
        # Se não encontrar tradução, retorna o original
        return texto_original
    
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
                         slider_images=slider_images,
                         get_servico_text=get_servico_text,
                         get_reunion_text=get_reunion_text,
                         get_projeto_text=get_projeto_text,
                         get_evento_text=get_evento_text,
                         get_acao_text=get_acao_text,
                         get_video_text=get_video_text,
                         get_banner_text=get_banner_text)

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
    ensure_base64_columns()
    projetos = Projeto.query.order_by(Projeto.data_inicio.desc(), Projeto.created_at.desc()).all()
    return render_template('projetos.html', projetos=projetos)

@app.route('/projetos/<int:id>')
@app.route('/projetos/<slug>')
def projeto(id=None, slug=None):
    ensure_base64_columns()
    # Suportar tanto ID quanto slug para compatibilidade
    if slug:
        projeto = Projeto.query.filter_by(slug=slug).first_or_404()
    else:
        projeto = Projeto.query.get_or_404(id)
    return render_template('projeto.html', projeto=projeto)

@app.route('/projetos/<int:id>/download')
def projeto_download_pdf(id):
    """Rota para download do PDF do projeto (do banco de dados base64 ou arquivo estático)"""
    projeto = Projeto.query.get_or_404(id)
    
    if not projeto.arquivo_pdf:
        from flask import abort
        abort(404)
    
    # Verificar se tem PDF em base64 (prioridade para persistência no Render)
    pdf_base64 = getattr(projeto, 'arquivo_pdf_base64', None)
    
    if pdf_base64:
        # Servir PDF do banco de dados (base64)
        try:
            pdf_data = base64.b64decode(pdf_base64)
            from flask import Response
            return Response(
                pdf_data,
                mimetype='application/pdf',
                headers={
                    'Content-Disposition': f'attachment; filename=projeto_{projeto.titulo.replace(" ", "_")}.pdf'
                }
            )
        except Exception as e:
            print(f"Erro ao decodificar PDF base64: {e}")
            from flask import abort
            abort(404)
    
    # Se não tem base64, tentar servir do arquivo (compatibilidade com dados antigos)
    if projeto.arquivo_pdf and not (projeto.arquivo_pdf.startswith('base64:') if projeto.arquivo_pdf else False):
        from flask import send_from_directory
        import os
        
        file_path = os.path.dirname(projeto.arquivo_pdf)
        file_name = os.path.basename(projeto.arquivo_pdf)
        static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
        
        try:
            return send_from_directory(
                os.path.join(static_dir, file_path), 
                file_name, 
                as_attachment=True,
                download_name=f'projeto_{projeto.titulo.replace(" ", "_")}.pdf'
            )
        except Exception as e:
            print(f"Erro ao servir PDF do arquivo: {e}")
            from flask import abort
            abort(404)
    
    from flask import abort
    abort(404)

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
@app.route('/informativo/<slug>')
def informativo_detalhe(id=None, slug=None):
    # Suportar tanto ID quanto slug para compatibilidade
    if slug:
        informativo = Informativo.query.filter_by(slug=slug).first_or_404()
    else:
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
    try:
        # Garantir que colunas base64 existem antes de fazer queries
        ensure_base64_columns()
        
        banner = Banner.query.filter_by(tipo='Campanhas', ativo=True).first()
        conteudos = []
        if banner:
            conteudos = BannerConteudo.query.filter_by(banner_id=banner.id, ativo=True).order_by(BannerConteudo.ordem.asc()).all()
        return render_template('campanhas.html', banner=banner, conteudos=conteudos)
    except Exception as e:
        print(f"Erro na rota campanhas: {e}")
        import traceback
        traceback.print_exc()
        # Retornar página mesmo com erro, mas sem conteudos
        return render_template('campanhas.html', banner=None, conteudos=[])

@app.route('/apoie')
def apoie():
    # Garantir que colunas base64 existem antes de fazer queries
    ensure_base64_columns()
    
    banner = Banner.query.filter_by(tipo='Apoie-nos', ativo=True).first()
    conteudos = []
    if banner:
        conteudos = BannerConteudo.query.filter_by(banner_id=banner.id, ativo=True).order_by(BannerConteudo.ordem.asc()).all()
        
        # Se não houver conteúdos, criar um conteúdo padrão "Como Apoiar"
        if not conteudos:
            try:
                conteudo_padrao = BannerConteudo(
                    banner_id=banner.id,
                    titulo='Como Apoiar',
                    conteudo='<p>Sua contribuição é fundamental para continuarmos promovendo inclusão e acessibilidade.</p><p>Em breve, mais informações sobre como apoiar estarão disponíveis aqui.</p>',
                    ordem=0,
                    ativo=True
                )
                db.session.add(conteudo_padrao)
                db.session.commit()
                conteudos = [conteudo_padrao]
            except Exception as e:
                db.session.rollback()
                # Se houver erro ao criar, continuar sem conteúdo
                pass
    
    return render_template('apoie.html', banner=banner, conteudos=conteudos)

@app.route('/editais')
def editais():
    # Garantir que colunas base64 existem antes de fazer queries
    ensure_base64_columns()
    
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
    relatorios_atividades = RelatorioAtividade.query.order_by(RelatorioAtividade.ordem.asc(), RelatorioAtividade.periodo_inicio.desc()).all()
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
                         relatorios_atividades=relatorios_atividades,
                         informacoes_doacao=informacoes_doacao,
                         get_text=get_text,
                         current_lang=current_lang)

@app.route('/transparencia/relatorios-financeiros')
def relatorios_financeiros():
    current_lang = session.get('language', 'pt')
    
    # Obter parâmetros de filtro de data
    data_inicio = request.args.get('data_inicio', '')
    data_fim = request.args.get('data_fim', '')
    
    # Buscar relatórios financeiros cadastrados no admin
    query = RelatorioFinanceiro.query
    
    # Aplicar filtros de data
    if data_inicio:
        try:
            data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
            query = query.filter(RelatorioFinanceiro.data_relatorio >= data_inicio_obj)
        except ValueError:
            pass
    
    if data_fim:
        try:
            data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
            query = query.filter(RelatorioFinanceiro.data_relatorio <= data_fim_obj)
        except ValueError:
            pass
    
    relatorios = query.order_by(RelatorioFinanceiro.ordem.asc(), RelatorioFinanceiro.data_relatorio.desc()).all()
    
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
                         current_lang=current_lang,
                         data_inicio=data_inicio,
                         data_fim=data_fim)

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

@app.route('/transparencia/relatorios-atividades')
def relatorios_atividades():
    current_lang = session.get('language', 'pt')
    
    # Obter parâmetros de filtro de data
    data_inicio = request.args.get('data_inicio', '')
    data_fim = request.args.get('data_fim', '')
    
    # Buscar relatórios de atividades cadastrados no admin
    query = RelatorioAtividade.query
    
    # Aplicar filtros de data (verificar se o período se sobrepõe ao filtro)
    if data_inicio:
        try:
            data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
            # Relatórios onde o período_fim >= data_inicio OU período_inicio >= data_inicio
            # Ou seja, relatórios que se sobrepõem ao período de filtro
            query = query.filter(
                db.or_(
                    RelatorioAtividade.periodo_fim >= data_inicio_obj,
                    RelatorioAtividade.periodo_inicio >= data_inicio_obj,
                    db.and_(
                        RelatorioAtividade.periodo_inicio.is_(None),
                        RelatorioAtividade.periodo_fim.is_(None)
                    )
                )
            )
        except ValueError:
            pass
    
    if data_fim:
        try:
            data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
            # Relatórios onde o período_inicio <= data_fim OU período_fim <= data_fim
            query = query.filter(
                db.or_(
                    RelatorioAtividade.periodo_inicio <= data_fim_obj,
                    RelatorioAtividade.periodo_fim <= data_fim_obj,
                    RelatorioAtividade.periodo_inicio.is_(None)
                )
            )
        except ValueError:
            pass
    
    relatorios = query.order_by(RelatorioAtividade.ordem.asc(), RelatorioAtividade.periodo_inicio.desc()).all()
    
    # Limpar tags <br> dos dados existentes automaticamente
    campos_texto = [
        'descricao_pt', 'descricao_es', 'descricao_en',
        'atividades_realizadas_pt', 'atividades_realizadas_es', 'atividades_realizadas_en',
        'resultados_pt', 'resultados_es', 'resultados_en'
    ]
    precisa_salvar = False
    for relatorio in relatorios:
        for campo in campos_texto:
            valor = getattr(relatorio, campo, None)
            if valor and ('<br>' in valor or '<br/>' in valor or '<br />' in valor):
                valor_limpo = processar_texto_relatorio(valor)
                setattr(relatorio, campo, valor_limpo)
                precisa_salvar = True
    
    if precisa_salvar:
        try:
            db.session.commit()
        except:
            db.session.rollback()
    
    # Função auxiliar para obter texto no idioma correto
    def get_text(obj, field):
        if not obj:
            return None
        if current_lang == 'es' and getattr(obj, f'{field}_es', None):
            return getattr(obj, f'{field}_es')
        elif current_lang == 'en' and getattr(obj, f'{field}_en', None):
            return getattr(obj, f'{field}_en')
        return getattr(obj, f'{field}_pt', None)
    
    return render_template('relatorios_atividades.html',
                         relatorios=relatorios,
                         get_text=get_text,
                         current_lang=current_lang,
                         data_inicio=data_inicio,
                         data_fim=data_fim)

@app.route('/transparencia/prestacao-contas')
def prestacao_contas():
    current_lang = session.get('language', 'pt')
    
    # Obter parâmetros de filtro de data
    data_inicio = request.args.get('data_inicio', '')
    data_fim = request.args.get('data_fim', '')
    
    # Buscar prestações de contas cadastradas no admin
    query = PrestacaoConta.query
    
    # Aplicar filtros de data (verificar se o período se sobrepõe ao filtro)
    if data_inicio:
        try:
            data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
            # Relatórios onde o período_fim >= data_inicio OU período_inicio >= data_inicio
            # Ou seja, relatórios que se sobrepõem ao período de filtro
            query = query.filter(
                db.or_(
                    PrestacaoConta.periodo_fim >= data_inicio_obj,
                    PrestacaoConta.periodo_inicio >= data_inicio_obj,
                    db.and_(
                        PrestacaoConta.periodo_inicio.is_(None),
                        PrestacaoConta.periodo_fim.is_(None)
                    )
                )
            )
        except ValueError:
            pass
    
    if data_fim:
        try:
            data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
            # Relatórios onde o período_inicio <= data_fim OU período_fim <= data_fim
            query = query.filter(
                db.or_(
                    PrestacaoConta.periodo_inicio <= data_fim_obj,
                    PrestacaoConta.periodo_fim <= data_fim_obj,
                    PrestacaoConta.periodo_inicio.is_(None)
                )
            )
        except ValueError:
            pass
    
    prestacoes = query.order_by(PrestacaoConta.ordem.asc(), PrestacaoConta.periodo_inicio.desc()).all()
    
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
                         current_lang=current_lang,
                         data_inicio=data_inicio,
                         data_fim=data_fim)

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

@app.route('/evento/<int:id>')
@app.route('/evento/<slug>')
def evento_detalhe(id=None, slug=None):
    """Rota para página de detalhe do evento"""
    ensure_base64_columns()
    if slug:
        evento = Evento.query.filter_by(slug=slug).first_or_404()
    else:
        evento = Evento.query.get_or_404(id)
    return render_template('evento.html', evento=evento)

@app.route('/acao/<int:id>')
@app.route('/acao/<slug>')
def acao_detalhe(id=None, slug=None):
    """Rota para página de detalhe da ação"""
    ensure_base64_columns()
    if slug:
        acao = Acao.query.filter_by(slug=slug).first_or_404()
    else:
        acao = Acao.query.get_or_404(id)
    return render_template('acao.html', acao=acao)

@app.route('/agenda-presencial/<int:id>')
@app.route('/agenda-presencial/<slug>')
def agenda_presencial_detalhe(id=None, slug=None):
    """Rota para página de detalhe da reunião presencial"""
    if slug:
        reunion = ReunionPresencial.query.filter_by(slug=slug).first_or_404()
    else:
        reunion = ReunionPresencial.query.get_or_404(id)
    return render_template('agenda_presencial_detalhe.html', reunion=reunion)

@app.route('/agenda-virtual/<int:id>')
@app.route('/agenda-virtual/<slug>')
def agenda_virtual_detalhe(id=None, slug=None):
    """Rota para página de detalhe da reunião virtual"""
    if slug:
        reunion = ReunionVirtual.query.filter_by(slug=slug).first_or_404()
    else:
        reunion = ReunionVirtual.query.get_or_404(id)
    return render_template('agenda_virtual_detalhe.html', reunion=reunion)

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
            
            tipo_associado = request.form.get('tipo_associado', 'contribuinte')
            
            associado = Associado(
                nome_completo=request.form.get('nome_completo'),
                cpf=cpf,
                data_nascimento=datetime.strptime(data_nascimento_str, "%Y-%m-%d").date(),
                endereco=request.form.get('endereco'),
                telefone=request.form.get('telefone'),
                tipo_associado=tipo_associado,
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

# ============================================
# ROTAS PÚBLICAS - VOLUNTÁRIOS
# ============================================

@app.route('/voluntario/cadastro', methods=['GET', 'POST'])
def voluntario_cadastro():
    """Página pública para cadastro de voluntários"""
    if request.method == 'POST':
        try:
            # Verificar se email já existe
            email = request.form.get('email')
            voluntario_existente = Voluntario.query.filter_by(email=email).first()
            if voluntario_existente:
                flash('Este email já está cadastrado. Entre em contato conosco se precisar de ajuda.', 'error')
                return redirect(url_for('voluntario_cadastro'))
            
            data_nascimento_str = request.form.get('data_nascimento')
            data_nascimento = None
            if data_nascimento_str:
                try:
                    data_nascimento = datetime.strptime(data_nascimento_str, "%Y-%m-%d").date()
                except:
                    pass
            
            # Limpar CPF (remover pontuação)
            cpf_raw = request.form.get('cpf')
            cpf_clean = cpf_raw.replace('.', '').replace('-', '') if cpf_raw else None

            voluntario = Voluntario(
                nome_completo=request.form.get('nome_completo'),
                email=email,
                telefone=request.form.get('telefone'),
                cpf=cpf_clean,
                endereco=request.form.get('endereco'),
                cidade=request.form.get('cidade'),
                estado=request.form.get('estado'),
                cep=request.form.get('cep'),
                data_nascimento=data_nascimento,
                profissao=request.form.get('profissao'),
                habilidades=request.form.get('habilidades'),
                disponibilidade=request.form.get('disponibilidade'),
                area_interesse=request.form.get('area_interesse'),
                observacoes=request.form.get('observacoes'),
                status='pendente',
                ativo=True
            )
            # Validação de senha: exigir senha e confirmação
            senha = request.form.get('senha')
            senha_confirm = request.form.get('senha_confirm')
            if not senha or not senha_confirm:
                flash('Senha e confirmação são obrigatórias para cadastro de voluntário.', 'error')
                return redirect(url_for('voluntario_cadastro'))
            if senha != senha_confirm:
                flash('As senhas não coincidem.', 'error')
                return redirect(url_for('voluntario_cadastro'))
            if len(senha) < 6:
                flash('A senha precisa ter pelo menos 6 caracteres.', 'error')
                return redirect(url_for('voluntario_cadastro'))

            # Adicionar voluntário e salvar senha (hash)
            db.session.add(voluntario)
            try:
                voluntario.set_password(senha)
            except Exception:
                # Se não for possível definir a senha (coluna ausente), avisar e abortar
                db.session.rollback()
                flash('Não foi possível salvar a senha: execute a migração para adicionar a coluna password_hash.', 'error')
                return redirect(url_for('voluntario_cadastro'))

            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                flash(f'Erro ao realizar cadastro: {str(e)}', 'error')
                return redirect(url_for('voluntario_cadastro'))
            flash('Cadastro de voluntário enviado com sucesso! Entraremos em contato em breve.', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao realizar cadastro: {str(e)}', 'error')
    
    return render_template('voluntario/cadastro.html')

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
        elif tipo == 'voluntario':
            # Voluntário faz login com CPF + senha (mesmo fluxo do associado)
            cpf = request.form.get('cpf')
            senha = request.form.get('senha')
            cpf_limpo = cpf.replace('.', '').replace('-', '') if cpf else None

            voluntario = None
            if cpf_limpo:
                voluntario = Voluntario.query.filter_by(cpf=cpf_limpo).first()

            # Se houver um voluntário cadastrado, tentar autenticar usando password_hash (se existir)
            if voluntario:
                # Se o modelo Voluntario tiver password_hash, compare
                pw_hash = getattr(voluntario, 'password_hash', None)
                if pw_hash:
                    if check_password_hash(pw_hash, senha):
                        if voluntario.status != 'aprovado':
                            flash('Seu cadastro de voluntário ainda não foi aprovado.', 'warning')
                            return redirect(url_for('login'))
                        if not voluntario.ativo:
                            flash('Sua conta de voluntário está inativa. Entre em contato com a administração.', 'error')
                            return redirect(url_for('login'))

                        session['voluntario_logged_in'] = True
                        session['voluntario_id'] = voluntario.id
                        session['voluntario_nome'] = voluntario.nome_completo
                        flash('Login de voluntário realizado com sucesso!', 'success')
                        return redirect(url_for('voluntario_dashboard'))
                    else:
                        flash('CPF ou senha de voluntário incorretos', 'error')
                        return redirect(url_for('login'))
                else:
                    # Fallback: se não há senha no modelo Voluntario, tentar autenticar contra Associado (se existir)
                    associado = Associado.query.filter_by(cpf=cpf_limpo).first()
                    if associado and associado.check_password(senha):
                        # permitir acesso à área de voluntário se o associado estiver com login válido
                        session['voluntario_logged_in'] = True
                        session['voluntario_id'] = voluntario.id
                        session['voluntario_nome'] = voluntario.nome_completo
                        flash('Login de voluntário realizado via credenciais de associado!', 'success')
                        return redirect(url_for('voluntario_dashboard'))
                    else:
                        flash('Voluntário não possui senha. Peça ao administrador para definir uma senha, ou use as credenciais de associado.', 'error')
                        return redirect(url_for('login'))
            else:
                # Se não existir voluntário, tentar autenticar como associado e negar acesso se não for voluntário
                associado = Associado.query.filter_by(cpf=cpf_limpo).first()
                if associado and associado.check_password(senha):
                    # Se existe um associado com esse CPF e senha, permitir acesso à área de voluntário
                    session['voluntario_logged_in'] = True
                    session['voluntario_id'] = None
                    session['voluntario_nome'] = associado.nome_completo
                    flash('Login de voluntário realizado com sucesso (via associado)!', 'success')
                    return redirect(url_for('voluntario_dashboard'))
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


@app.route('/voluntario/logout')
def voluntario_logout():
    session.pop('voluntario_logged_in', None)
    session.pop('voluntario_id', None)
    session.pop('voluntario_nome', None)
    flash('Logout realizado com sucesso!', 'success')
    return redirect(url_for('index'))


@app.route('/voluntario')
@voluntario_required
def voluntario_dashboard():
    # Tentar obter o id do voluntário da sessão
    voluntario_id = session.get('voluntario_id')
    voluntario = None

    if voluntario_id:
        voluntario = Voluntario.query.get(voluntario_id)
    else:
        # Caso o login tenha sido feito via associado (fallback), tentar localizar voluntario pelo CPF em sessão
        associado_cpf = session.get('associado_cpf')
        if associado_cpf:
            voluntario = Voluntario.query.filter_by(cpf=associado_cpf).first()

    # Se ainda não houver voluntario, criar um objeto mínimo para template (apenas nome)
    if not voluntario:
        class Dummy:
            nome_completo = session.get('voluntario_nome') or session.get('associado_nome') or 'Voluntário'
            id = None

        voluntario = Dummy()

    # Buscar ofertas e agendamentos atribuídos a este voluntário (se houver id)
    ofertas = []
    agendamentos = []
    if getattr(voluntario, 'id', None):
        ofertas = OfertaHoras.query.filter_by(voluntario_id=voluntario.id).order_by(OfertaHoras.data_inicio.desc()).all()
        agendamentos = AgendamentoVoluntario.query.filter_by(voluntario_id=voluntario.id).order_by(AgendamentoVoluntario.data_agendamento.desc()).all()

    return render_template('voluntario/dashboard.html', voluntario=voluntario, ofertas=ofertas, agendamentos=agendamentos)

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
    
    # Verificar se está em base64 (Render)
    if associado.carteira_pdf.startswith('base64:') and associado.carteira_pdf_base64:
        try:
            pdf_data = base64.b64decode(associado.carteira_pdf_base64)
            from flask import Response
            return Response(pdf_data, mimetype='application/pdf')
        except Exception as e:
            print(f"Erro ao servir carteira base64: {e}")
            flash('Erro ao carregar carteira. Entre em contato com o administrador.', 'error')
            return redirect(url_for('associado_dashboard'))
    
    # Tentar servir do arquivo (compatibilidade com dados antigos)
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
    
    # Verificar se está em base64 (Render)
    if associado.carteira_pdf.startswith('base64:') and associado.carteira_pdf_base64:
        try:
            pdf_data = base64.b64decode(associado.carteira_pdf_base64)
            from flask import Response
            return Response(
                pdf_data, 
                mimetype='application/pdf',
                headers={'Content-Disposition': f'attachment; filename=carteira_associado_{associado.cpf}.pdf'}
            )
        except Exception as e:
            print(f"Erro ao servir carteira base64: {e}")
            flash('Erro ao carregar carteira. Entre em contato com o administrador.', 'error')
            return redirect(url_for('associado_dashboard'))
    
    # Tentar servir do arquivo (compatibilidade com dados antigos)
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

def gerar_codigo_certificado():
    return f"CERT-{uuid.uuid4().hex[:10].upper()}"

def salvar_qr_certificado(numero_validacao):
    validation_url = url_for('certificado_validar', codigo=numero_validacao, _external=True)
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(validation_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    qr_dir = os.path.join('static', 'qrcodes', 'certificados')
    os.makedirs(qr_dir, exist_ok=True)
    filename = f"certificado_{numero_validacao}.png"
    qr_path = os.path.join(qr_dir, filename)
    img.save(qr_path)
    return f"qrcodes/certificados/{filename}"

def certificado_esta_valido(certificado):
    """Verifica se um certificado está válido baseado apenas no status (certificados são vitalícios)"""
    if not certificado:
        return False
    
    # Verificar status - se for None ou vazio, considerar como válido (default do modelo)
    status_str = (certificado.status or '').strip().lower()
    
    # Certificados são vitalícios, então apenas verificar se o status não é inválido
    if status_str in ('revogado', 'expirado', 'invalido', 'inválido'):
        return False
    
    # Se status é válido, ativo, None ou vazio, considerar válido
    return True

def garantir_qr_certificado(certificado):
    if not certificado:
        return None
    rel_path = certificado.qr_code_path
    precisa_regenerar = False
    if not rel_path:
        precisa_regenerar = True
    else:
        file_path = os.path.join('static', rel_path.replace('\\', '/').replace('/', os.sep))
        if not os.path.exists(file_path):
            precisa_regenerar = True
    if precisa_regenerar:
        try:
            rel_path = salvar_qr_certificado(certificado.numero_validacao)
            certificado.qr_code_path = rel_path
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f'Erro ao regenerar QR do certificado {certificado.numero_validacao}:', e)
            return None
    return rel_path

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

# Função para detectar dispositivo mobile
def is_mobile_device():
    """Detecta se o dispositivo é mobile baseado no User-Agent"""
    user_agent = request.headers.get('User-Agent', '').lower()
    mobile_keywords = [
        'mobile', 'android', 'iphone', 'ipad', 'ipod', 
        'blackberry', 'windows phone', 'opera mini', 
        'iemobile', 'palm', 'smartphone', 'tablet'
    ]
    return any(keyword in user_agent for keyword in mobile_keywords)

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
    
    def slider_imagem_url(slider_image):
        """Helper function para obter URL da imagem do slider de forma segura"""
        if not slider_image:
            return None
        try:
            # Verificar se tem imagem_base64 usando getattr (seguro se coluna não existir)
            imagem_base64 = None
            try:
                imagem_base64 = getattr(slider_image, 'imagem_base64', None)
            except (AttributeError, KeyError):
                # Coluna pode não existir ainda
                pass
            
            if imagem_base64:
                return f"/slider/{slider_image.id}/imagem"
            
            # Verificar se imagem começa com base64:
            try:
                if slider_image.imagem and 'base64:' in str(slider_image.imagem):
                    return f"/slider/{slider_image.id}/imagem"
            except (AttributeError, KeyError):
                pass
            
            # Fallback para arquivo estático
            try:
                if slider_image.imagem:
                    from flask import url_for
                    return url_for('static', filename=slider_image.imagem)
            except (AttributeError, KeyError, Exception):
                pass
            
            return None
        except Exception as e:
            print(f"Erro ao obter URL da imagem do slider: {e}")
            import traceback
            traceback.print_exc()
            # Fallback final
            try:
                if hasattr(slider_image, 'imagem') and slider_image.imagem:
                    from flask import url_for
                    return url_for('static', filename=slider_image.imagem)
            except:
                pass
            return None
    
    def apoiador_logo_url(apoiador):
        """Helper function para obter URL do logo do apoiador de forma segura"""
        if not apoiador:
            return None
        try:
            # Verificar se tem logo_base64 usando getattr (seguro se coluna não existir)
            logo_base64 = None
            try:
                logo_base64 = getattr(apoiador, 'logo_base64', None)
            except (AttributeError, KeyError):
                # Coluna pode não existir ainda
                pass
            
            if logo_base64:
                return f"/apoiador/{apoiador.id}/logo"
            
            # Verificar se logo começa com base64:
            try:
                if apoiador.logo and 'base64:' in str(apoiador.logo):
                    return f"/apoiador/{apoiador.id}/logo"
            except (AttributeError, KeyError):
                pass
            
            # Fallback para arquivo estático
            try:
                if apoiador.logo:
                    from flask import url_for
                    return url_for('static', filename=apoiador.logo)
            except (AttributeError, KeyError, Exception):
                pass
            
            return None
        except Exception as e:
            print(f"Erro ao obter URL do logo do apoiador: {e}")
            import traceback
            traceback.print_exc()
            # Fallback final
            try:
                if hasattr(apoiador, 'logo') and apoiador.logo:
                    from flask import url_for
                    return url_for('static', filename=apoiador.logo)
            except:
                pass
            return None
    
    def projeto_imagem_url(projeto, external=False):
        """Helper function para obter URL da imagem do projeto de forma segura"""
        if not projeto:
            return None
        try:
            # Verificar se tem imagen_base64 usando getattr (seguro se coluna não existir)
            imagen_base64 = None
            try:
                imagen_base64 = getattr(projeto, 'imagen_base64', None)
            except (AttributeError, KeyError):
                pass
            
            if imagen_base64:
                slug_or_id = projeto.slug if projeto.slug else projeto.id
                if external:
                    return url_for('projeto_imagem', slug=slug_or_id, _external=True) if projeto.slug else url_for('projeto_imagem', id=projeto.id, _external=True)
                return f"/projeto/{slug_or_id}/imagem" if projeto.slug else f"/projeto/{projeto.id}/imagem"
            
            # Verificar se imagen começa com base64:
            try:
                if projeto.imagen and 'base64:' in str(projeto.imagen):
                    slug_or_id = projeto.slug if projeto.slug else projeto.id
                    if external:
                        return url_for('projeto_imagem', slug=slug_or_id, _external=True) if projeto.slug else url_for('projeto_imagem', id=projeto.id, _external=True)
                    return f"/projeto/{slug_or_id}/imagem" if projeto.slug else f"/projeto/{projeto.id}/imagem"
            except (AttributeError, KeyError):
                pass
            
            # Fallback para arquivo estático
            try:
                if projeto.imagen:
                    return url_for('static', filename=projeto.imagen, _external=external)
            except (AttributeError, KeyError, Exception):
                pass
            
            return None
        except Exception as e:
            print(f"Erro ao obter URL da imagem do projeto: {e}")
            try:
                if hasattr(projeto, 'imagen') and projeto.imagen:
                    return url_for('static', filename=projeto.imagen, _external=external)
            except:
                pass
            return None
    
    def radio_programa_imagem_url(programa):
        """Helper function para obter URL da imagem do programa de rádio de forma segura"""
        if not programa:
            return None
        try:
            # Verificar se tem imagem_base64 usando getattr (seguro se coluna não existir)
            imagem_base64 = None
            try:
                imagem_base64 = getattr(programa, 'imagem_base64', None)
            except (AttributeError, KeyError):
                pass
            
            if imagem_base64:
                return f"/radio-programa/{programa.id}/imagem"
            
            # Verificar se imagem começa com base64:
            try:
                if programa.imagem and 'base64:' in str(programa.imagem):
                    return f"/radio-programa/{programa.id}/imagem"
            except (AttributeError, KeyError):
                pass
            
            # Fallback para arquivo estático
            try:
                if programa.imagem:
                    from flask import url_for
                    return url_for('static', filename=programa.imagem)
            except (AttributeError, KeyError, Exception):
                pass
            
            return None
        except Exception as e:
            print(f"Erro ao obter URL da imagem do programa de rádio: {e}")
            try:
                if hasattr(programa, 'imagem') and programa.imagem:
                    from flask import url_for
                    return url_for('static', filename=programa.imagem)
            except:
                pass
            return None
    
    def acao_imagem_url(acao, external=False):
        """Helper function para obter URL da imagem da ação de forma segura"""
        if not acao:
            return None
        try:
            # Verificar se tem imagem_base64 usando getattr (seguro se coluna não existir)
            imagem_base64 = None
            try:
                imagem_base64 = getattr(acao, 'imagem_base64', None)
            except (AttributeError, KeyError):
                pass
            
            if imagem_base64:
                slug_or_id = acao.slug if acao.slug else acao.id
                if external:
                    return url_for('acao_imagem', slug=slug_or_id, _external=True) if acao.slug else url_for('acao_imagem', id=acao.id, _external=True)
                return f"/acao/{slug_or_id}/imagem" if acao.slug else f"/acao/{acao.id}/imagem"
            
            # Verificar se imagem começa com base64:
            try:
                if acao.imagem and 'base64:' in str(acao.imagem):
                    slug_or_id = acao.slug if acao.slug else acao.id
                    if external:
                        return url_for('acao_imagem', slug=slug_or_id, _external=True) if acao.slug else url_for('acao_imagem', id=acao.id, _external=True)
                    return f"/acao/{slug_or_id}/imagem" if acao.slug else f"/acao/{acao.id}/imagem"
            except (AttributeError, KeyError):
                pass
            
            # Fallback para arquivo estático
            try:
                if acao.imagem:
                    return url_for('static', filename=acao.imagem, _external=external)
            except (AttributeError, KeyError, Exception):
                pass
            
            return None
        except Exception as e:
            print(f"Erro ao obter URL da imagem da ação: {e}")
            try:
                if hasattr(acao, 'imagem') and acao.imagem:
                    return url_for('static', filename=acao.imagem, _external=external)
            except:
                pass
            return None
    
    def informativo_imagem_url(informativo, external=False):
        """Helper function para obter URL da imagem do informativo de forma segura"""
        if not informativo:
            return None
        try:
            # Verificar se tem imagem_base64 usando getattr (seguro se coluna não existir)
            imagem_base64 = None
            try:
                imagem_base64 = getattr(informativo, 'imagem_base64', None)
            except (AttributeError, KeyError):
                pass
            
            if imagem_base64:
                slug_or_id = informativo.slug if informativo.slug else informativo.id
                if external:
                    return url_for('informativo_imagem', slug=slug_or_id, _external=True) if informativo.slug else url_for('informativo_imagem', id=informativo.id, _external=True)
                return f"/informativo/{slug_or_id}/imagem" if informativo.slug else f"/informativo/{informativo.id}/imagem"
            
            # Verificar se imagem começa com base64:
            try:
                if informativo.imagem and 'base64:' in str(informativo.imagem):
                    slug_or_id = informativo.slug if informativo.slug else informativo.id
                    if external:
                        return url_for('informativo_imagem', slug=slug_or_id, _external=True) if informativo.slug else url_for('informativo_imagem', id=informativo.id, _external=True)
                    return f"/informativo/{slug_or_id}/imagem" if informativo.slug else f"/informativo/{informativo.id}/imagem"
            except (AttributeError, KeyError):
                pass
            
            # Fallback para arquivo estático
            try:
                if informativo.imagem:
                    return url_for('static', filename=informativo.imagem, _external=external)
            except (AttributeError, KeyError, Exception):
                pass
            
            return None
        except Exception as e:
            print(f"Erro ao obter URL da imagem do informativo: {e}")
            try:
                if hasattr(informativo, 'imagem') and informativo.imagem:
                    return url_for('static', filename=informativo.imagem, _external=external)
            except:
                pass
            return None
    
    def evento_imagem_url(evento, external=False):
        """Helper function para obter URL da imagem do evento de forma segura"""
        if not evento:
            return None
        try:
            # Verificar se tem imagem_base64 usando getattr (seguro se coluna não existir)
            imagem_base64 = None
            try:
                imagem_base64 = getattr(evento, 'imagem_base64', None)
            except (AttributeError, KeyError):
                pass
            
            # Fallback para arquivo estático
            try:
                if evento.imagem:
                    return url_for('static', filename=evento.imagem, _external=external)
            except (AttributeError, KeyError, Exception):
                pass
            
            return None
        except Exception as e:
            print(f"Erro ao obter URL da imagem do evento: {e}")
            try:
                if hasattr(evento, 'imagem') and evento.imagem:
                    return url_for('static', filename=evento.imagem, _external=external)
            except:
                pass
            return None
    
    def qrcode_url():
        """Helper function para obter URL do QR code de forma segura"""
        try:
            # Verificar se tem footer_qrcode_base64
            config_base64 = Configuracao.query.filter_by(chave='footer_qrcode_base64').first()
            if config_base64 and config_base64.valor:
                return "/qrcode/imagem"
            
            # Fallback para arquivo estático
            config = Configuracao.query.filter_by(chave='footer_qrcode').first()
            if config and config.valor:
                from flask import url_for
                return url_for('static', filename=config.valor)
            
            # Fallback padrão
            from flask import url_for
            return url_for('static', filename='images/qrcode.png')
        except Exception as e:
            print(f"Erro ao obter URL do QR code: {e}")
            import traceback
            traceback.print_exc()
            # Fallback final
            try:
                from flask import url_for
                return url_for('static', filename='images/qrcode.png')
            except:
                return None
    
    def certificado_qr_url(certificado):
        rel_path = garantir_qr_certificado(certificado)
        if rel_path:
            try:
                from flask import url_for
                return url_for('static', filename=rel_path.replace('\\', '/'))
            except Exception as e:
                print(f'Erro ao gerar URL do QR do certificado: {e}')
                return None
    
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
    
    def diretoria_foto_url(membro):
        """Helper function para obter URL da foto da diretoria"""
        if not membro or not membro.foto:
            return None
        
        # Se a foto está em base64, usar a rota especial
        if membro.foto.startswith('base64:') or getattr(membro, 'foto_base64', None):
            from flask import url_for
            return url_for('diretoria_foto', id=membro.id)
        
        # Caso contrário, usar arquivo estático
        from flask import url_for
        return url_for('static', filename=membro.foto)
    
    def conselho_foto_url(membro):
        """Helper function para obter URL da foto do conselho fiscal"""
        if not membro or not membro.foto:
            return None
        
        # Se a foto está em base64, usar a rota especial
        if membro.foto.startswith('base64:') or getattr(membro, 'foto_base64', None):
            from flask import url_for
            return url_for('conselho_foto', id=membro.id)
        
        # Caso contrário, usar arquivo estático
        from flask import url_for
        return url_for('static', filename=membro.foto)
    
    # Detectar dispositivo mobile
    is_mobile = is_mobile_device()
    
    return dict(
        slider_imagem_url=slider_imagem_url,
        apoiador_logo_url=apoiador_logo_url,
        projeto_imagem_url=projeto_imagem_url,
        radio_programa_imagem_url=radio_programa_imagem_url,
        acao_imagem_url=acao_imagem_url,
        informativo_imagem_url=informativo_imagem_url,
        diretoria_foto_url=diretoria_foto_url,
        conselho_foto_url=conselho_foto_url,
        qrcode_url=qrcode_url,
        current_user=session.get('admin_username'),
        current_language=session.get('language', 'pt'),
        languages=app.config['LANGUAGES'],
        _=_,
        date=date,  # Disponibilizar date para templates
        user_tem_permissao=user_tem_permissao,
        is_super_admin=session.get('admin_is_super', False),
        dados_associacao=dados_associacao,  # Dados da associação para uso nos templates
        footer_configs=footer_configs,  # Configurações do rodapé
        certificado_esta_valido=certificado_esta_valido,
        certificado_qr_url=certificado_qr_url,
        is_mobile_device=is_mobile  # Detecção de dispositivo mobile
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
            from sqlalchemy import text, inspect
            try:
                # Verificar se é SQLite ou PostgreSQL
                is_sqlite = db.engine.url.drivername == 'sqlite'
                
                with db.engine.connect() as conn:
                    # Verificar se a coluna existe
                    if is_sqlite:
                        result = conn.execute(text("PRAGMA table_info(usuario)"))
                        columns = [row[1] for row in result]
                    else:
                        # PostgreSQL
                        result = conn.execute(text("""
                            SELECT column_name 
                            FROM information_schema.columns 
                            WHERE table_name = 'usuario' AND column_name = 'is_super_admin'
                        """))
                        columns = [row[0] for row in result]
                    
                    if (is_sqlite and 'is_super_admin' not in columns) or (not is_sqlite and len(columns) == 0):
                        # PostgreSQL usa BOOLEAN, SQLite também suporta
                        conn.execute(text("ALTER TABLE usuario ADD COLUMN is_super_admin BOOLEAN DEFAULT FALSE"))
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
        
        # Migração da coluna imagem_base64 já foi feita no início da função
        
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

def _add_column(inspector, conn, table_name, column_name, is_sqlite, column_type='TEXT'):
    """Função auxiliar para adicionar coluna a uma tabela"""
    from sqlalchemy import text
    try:
        column_exists = False
        
        if is_sqlite:
            result = conn.execute(text("PRAGMA table_info({})".format(table_name)))
            columns = [row[1] for row in result]
            column_exists = column_name in columns
        else:
            # PostgreSQL
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT 1 
                    FROM information_schema.columns 
                    WHERE table_name = :table_name 
                    AND column_name = :column_name
                )
            """), {'table_name': table_name, 'column_name': column_name})
            column_exists = result.scalar()
        
        if not column_exists:
            print(f"📝 Adicionando coluna {column_name} à tabela {table_name}...")
            try:
                if is_sqlite:
                    conn.execute(text("ALTER TABLE {} ADD COLUMN {} {}".format(table_name, column_name, column_type)))
                else:
                    # PostgreSQL - usar IF NOT EXISTS via DO block com format dinâmico
                    sql = f"""
                        DO $$ 
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns 
                                WHERE table_name = '{table_name}' 
                                AND column_name = '{column_name}'
                            ) THEN
                                EXECUTE format('ALTER TABLE %I ADD COLUMN %I {column_type}', '{table_name}', '{column_name}');
                            END IF;
                        END $$;
                    """
                    conn.execute(text(sql))
                conn.commit()
                print(f"✅ Coluna {column_name} adicionada à tabela {table_name}.")
            except Exception as e:
                # Se a coluna já existe (erro de duplicação), ignorar
                error_str = str(e).lower()
                if 'duplicate' in error_str or 'already exists' in error_str or ('column' in error_str and 'already' in error_str):
                    print(f"ℹ️ Coluna {table_name}.{column_name} já existe.")
                else:
                    raise
        return True
    except Exception as e:
        print(f"⚠️ Erro ao adicionar coluna {table_name}.{column_name}: {e}")
        import traceback
        traceback.print_exc()
        return False

# Função para inicializar o banco de dados quando necessário
def ensure_db_initialized():
    """Garante que o banco de dados está inicializado"""
    try:
        with app.app_context():
            # Verificar qual banco está sendo usado
            db_type = db.engine.url.drivername
            print(f"📊 Tipo de banco de dados: {db_type}")
            
            # PRIMEIRO: Adicionar colunas base64 se necessário ANTES de qualquer query
            try:
                from sqlalchemy import text, inspect
                inspector = inspect(db.engine)
                
                # Adicionar coluna imagem_base64 à tabela slider_image
                table_exists = 'slider_image' in inspector.get_table_names()
                if table_exists:
                    is_sqlite = db_type == 'sqlite'
                    with db.engine.connect() as conn:
                        if is_sqlite:
                            result = conn.execute(text("PRAGMA table_info(slider_image)"))
                            columns = [row[1] for row in result]
                        else:
                            result = conn.execute(text("""
                                SELECT column_name 
                                FROM information_schema.columns 
                                WHERE table_name = 'slider_image' AND column_name = 'imagem_base64'
                            """))
                            columns = [row[0] for row in result]
                        
                        if (is_sqlite and 'imagem_base64' not in columns) or (not is_sqlite and len(columns) == 0):
                            print("📝 Adicionando coluna imagem_base64 à tabela slider_image...")
                            if is_sqlite:
                                conn.execute(text("ALTER TABLE slider_image ADD COLUMN imagem_base64 TEXT"))
                            else:
                                conn.execute(text("ALTER TABLE slider_image ADD COLUMN imagem_base64 TEXT"))
                            conn.commit()
                            print("✅ Coluna imagem_base64 adicionada.")
                
                # Adicionar coluna logo_base64 à tabela apoiador
                table_exists = 'apoiador' in inspector.get_table_names()
                if table_exists:
                    is_sqlite = db_type == 'sqlite'
                    with db.engine.connect() as conn:
                        if is_sqlite:
                            result = conn.execute(text("PRAGMA table_info(apoiador)"))
                            columns = [row[1] for row in result]
                        else:
                            result = conn.execute(text("""
                                SELECT column_name 
                                FROM information_schema.columns 
                                WHERE table_name = 'apoiador' AND column_name = 'logo_base64'
                            """))
                            columns = [row[0] for row in result]
                        
                        if (is_sqlite and 'logo_base64' not in columns) or (not is_sqlite and len(columns) == 0):
                            print("📝 Adicionando coluna logo_base64 à tabela apoiador...")
                            if is_sqlite:
                                conn.execute(text("ALTER TABLE apoiador ADD COLUMN logo_base64 TEXT"))
                            else:
                                conn.execute(text("ALTER TABLE apoiador ADD COLUMN logo_base64 TEXT"))
                            conn.commit()
                            print("✅ Coluna logo_base64 adicionada.")
                
                # Adicionar coluna imagem_base64 à tabela banner_conteudo
                table_exists = 'banner_conteudo' in inspector.get_table_names()
                if table_exists:
                    is_sqlite = db_type == 'sqlite'
                    with db.engine.connect() as conn:
                        column_exists = False
                        
                        if is_sqlite:
                            result = conn.execute(text("PRAGMA table_info(banner_conteudo)"))
                            columns = [row[1] for row in result]
                            column_exists = 'imagem_base64' in columns
                        else:
                            # PostgreSQL - usar EXISTS para verificação mais robusta
                            result = conn.execute(text("""
                                SELECT EXISTS (
                                    SELECT 1 
                                    FROM information_schema.columns 
                                    WHERE table_name = 'banner_conteudo' 
                                    AND column_name = 'imagem_base64'
                                )
                            """))
                            column_exists = result.scalar()
                        
                        if not column_exists:
                            print("📝 Adicionando coluna imagem_base64 à tabela banner_conteudo...")
                            try:
                                if is_sqlite:
                                    conn.execute(text("ALTER TABLE banner_conteudo ADD COLUMN imagem_base64 TEXT"))
                                else:
                                    # PostgreSQL - usar IF NOT EXISTS via DO block
                                    conn.execute(text("""
                                        DO $$ 
                                        BEGIN
                                            IF NOT EXISTS (
                                                SELECT 1 FROM information_schema.columns 
                                                WHERE table_name = 'banner_conteudo' 
                                                AND column_name = 'imagem_base64'
                                            ) THEN
                                                ALTER TABLE banner_conteudo ADD COLUMN imagem_base64 TEXT;
                                            END IF;
                                        END $$;
                                    """))
                                conn.commit()
                                print("✅ Coluna imagem_base64 adicionada à tabela banner_conteudo.")
                            except Exception as e:
                                if 'duplicate' in str(e).lower() or 'already exists' in str(e).lower():
                                    print("ℹ️ Coluna banner_conteudo.imagem_base64 já existe.")
                                else:
                                    raise
                
                # Adicionar coluna imagem_base64 à tabela banner
                table_exists = 'banner' in inspector.get_table_names()
                if table_exists:
                    is_sqlite = db_type == 'sqlite'
                    with db.engine.connect() as conn:
                        column_exists = False
                        
                        if is_sqlite:
                            result = conn.execute(text("PRAGMA table_info(banner)"))
                            columns = [row[1] for row in result]
                            column_exists = 'imagem_base64' in columns
                        else:
                            # PostgreSQL - usar EXISTS para verificação mais robusta
                            result = conn.execute(text("""
                                SELECT EXISTS (
                                    SELECT 1 
                                    FROM information_schema.columns 
                                    WHERE table_name = 'banner' 
                                    AND column_name = 'imagem_base64'
                                )
                            """))
                            column_exists = result.scalar()
                        
                        if not column_exists:
                            print("📝 Adicionando coluna imagem_base64 à tabela banner...")
                            try:
                                if is_sqlite:
                                    conn.execute(text("ALTER TABLE banner ADD COLUMN imagem_base64 TEXT"))
                                else:
                                    # PostgreSQL - usar IF NOT EXISTS via DO block
                                    conn.execute(text("""
                                        DO $$ 
                                        BEGIN
                                            IF NOT EXISTS (
                                                SELECT 1 FROM information_schema.columns 
                                                WHERE table_name = 'banner' 
                                                AND column_name = 'imagem_base64'
                                            ) THEN
                                                ALTER TABLE banner ADD COLUMN imagem_base64 TEXT;
                                            END IF;
                                        END $$;
                                    """))
                                conn.commit()
                                print("✅ Coluna imagem_base64 adicionada à tabela banner.")
                            except Exception as e:
                                if 'duplicate' in str(e).lower() or 'already exists' in str(e).lower():
                                    print("ℹ️ Coluna banner.imagem_base64 já existe.")
                                else:
                                    raise
                
                # Adicionar colunas base64 para os outros modelos
                # IMPORTANTE: Adicionar também colunas que não são base64 mas foram adicionadas ao modelo
                tables_to_migrate = [
                    ('projeto', 'imagen_base64'),  # Projeto usa "imagen" em vez de "imagem"
                    ('projeto', 'arquivo_pdf'),  # Campo arquivo_pdf (pode ser caminho ou 'base64:...')
                    ('projeto', 'arquivo_pdf_base64'),  # PDF do projeto em base64
                    ('acao', 'imagem_base64'),
                    ('evento', 'imagem_base64'),
                    ('informativo', 'imagem_base64'),
                    ('radio_programa', 'imagem_base64'),
                    ('membro_diretoria', 'foto_base64'),
                    ('membro_conselho_fiscal', 'foto_base64'),
                    ('relatorio_atividade', 'arquivo_base64'),
                    ('associado', 'carteira_pdf_base64'),
                ]
                
                for table_name, column_name in tables_to_migrate:
                    table_exists = table_name in inspector.get_table_names()
                    if table_exists:
                        is_sqlite = db_type == 'sqlite'
                        with db.engine.connect() as conn:
                            _add_column(inspector, conn, table_name, column_name, is_sqlite, 'TEXT')
            except Exception as e:
                print(f"⚠️ Aviso ao verificar colunas base64: {e}")
            
            # Criar todas as tabelas (idempotente - não recria se já existirem)
            db.create_all()
            print("✅ Tabelas do banco de dados verificadas/criadas")
            
            # Executar migração problema_acessibilidade para garantir que a tabela exista
            try:
                import migrate_postgres_problema_acessibilidade as mig_problema
                print('Executando migração problema_acessibilidade (startup)...')
                mig_problema.migrate()
                print('Migração problema_acessibilidade executada com sucesso (startup)')
            except Exception as e:
                print(f'⚠️ Aviso: Não foi possível executar migração problema_acessibilidade no startup: {e}')
                # Tentar criar a tabela manualmente se a migração falhar
                try:
                    from sqlalchemy import inspect, text
                    inspector = inspect(db.engine)
                    if 'problema_acessibilidade' not in inspector.get_table_names():
                        print('Criando tabela problema_acessibilidade manualmente...')
                        is_sqlite = db_type == 'sqlite'
                        with db.engine.connect() as conn:
                            if is_sqlite:
                                conn.execute(text('''
                                    CREATE TABLE IF NOT EXISTS problema_acessibilidade (
                                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                                        tipo_problema VARCHAR(100) NOT NULL,
                                        descricao TEXT NOT NULL,
                                        localizacao VARCHAR(500) NOT NULL,
                                        nome_denunciante VARCHAR(200) NOT NULL,
                                        telefone VARCHAR(100) NOT NULL,
                                        email VARCHAR(200),
                                        anexos TEXT,
                                        status VARCHAR(50) DEFAULT 'novo',
                                        observacoes_admin TEXT,
                                        created_at TIMESTAMP,
                                        updated_at TIMESTAMP
                                    )
                                '''))
                            else:
                                conn.execute(text('''
                                    CREATE TABLE IF NOT EXISTS problema_acessibilidade (
                                        id SERIAL PRIMARY KEY,
                                        tipo_problema VARCHAR(100) NOT NULL,
                                        descricao TEXT NOT NULL,
                                        localizacao VARCHAR(500) NOT NULL,
                                        nome_denunciante VARCHAR(200) NOT NULL,
                                        telefone VARCHAR(100) NOT NULL,
                                        email VARCHAR(200),
                                        anexos TEXT,
                                        status VARCHAR(50) DEFAULT 'novo',
                                        observacoes_admin TEXT,
                                        created_at TIMESTAMP,
                                        updated_at TIMESTAMP
                                    )
                                '''))
                            conn.commit()
                        print('✅ Tabela problema_acessibilidade criada manualmente')
                except Exception as manual_error:
                    print(f'⚠️ Erro ao criar tabela manualmente: {manual_error}')

            # Executar migração certificado para garantir que a tabela exista
            try:
                import migrate_postgres_certificado as mig_cert
                print('Executando migração certificado (startup)...')
                mig_cert.migrate()
                print('Migração certificado executada com sucesso (startup)')
            except Exception as e:
                print(f'⚠️ Aviso: Não foi possível executar migração certificado no startup: {e}')
                try:
                    from sqlalchemy import inspect, text
                    inspector = inspect(db.engine)
                    if 'certificado' not in inspector.get_table_names():
                        print('Criando tabela certificado manualmente...')
                        is_sqlite = db_type == 'sqlite'
                        with db.engine.connect() as conn:
                            if is_sqlite:
                                conn.execute(text('''
                                    CREATE TABLE IF NOT EXISTS certificado (
                                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                                        numero_validacao VARCHAR(50) UNIQUE NOT NULL,
                                        nome_pessoa VARCHAR(200) NOT NULL,
                                        documento VARCHAR(100),
                                        descricao TEXT,
                                        curso VARCHAR(200),
                                        data_emissao TIMESTAMP,
                                        data_validade TIMESTAMP,
                                        status VARCHAR(50) DEFAULT 'valido',
                                        qr_code_path VARCHAR(300),
                                        created_at TIMESTAMP,
                                        updated_at TIMESTAMP
                                    )
                                '''))
                            else:
                                conn.execute(text('''
                                    CREATE TABLE IF NOT EXISTS certificado (
                                        id SERIAL PRIMARY KEY,
                                        numero_validacao VARCHAR(50) UNIQUE NOT NULL,
                                        nome_pessoa VARCHAR(200) NOT NULL,
                                        documento VARCHAR(100),
                                        descricao TEXT,
                                        curso VARCHAR(200),
                                        data_emissao TIMESTAMP,
                                        data_validade TIMESTAMP,
                                        status VARCHAR(50) DEFAULT 'valido',
                                        qr_code_path VARCHAR(300),
                                        created_at TIMESTAMP,
                                        updated_at TIMESTAMP
                                    )
                                '''))
                            conn.commit()
                        print('✅ Tabela certificado criada manualmente')
                except Exception as cert_manual_error:
                    print(f'⚠️ Erro ao criar tabela certificado manualmente: {cert_manual_error}')
            
            # Executar migração reciclagem para garantir que a tabela exista
            try:
                import migrate_postgres_reciclagem as mig_reciclagem
                print('Executando migração reciclagem (startup)...')
                mig_reciclagem.migrate()
                print('Migração reciclagem executada com sucesso (startup)')
            except Exception as e:
                print(f'⚠️ Aviso: Não foi possível executar migração reciclagem no startup: {e}')
                try:
                    from sqlalchemy import inspect, text
                    inspector = inspect(db.engine)
                    if 'reciclagem' not in inspector.get_table_names():
                        print('Criando tabela reciclagem manualmente...')
                        is_sqlite = db_type == 'sqlite'
                        with db.engine.connect() as conn:
                            if is_sqlite:
                                conn.execute(text('''
                                    CREATE TABLE IF NOT EXISTS reciclagem (
                                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                                        tipo_material VARCHAR(50) NOT NULL,
                                        nome_completo VARCHAR(200) NOT NULL,
                                        telefone VARCHAR(20) NOT NULL,
                                        endereco_retirada TEXT NOT NULL,
                                        observacoes TEXT,
                                        status VARCHAR(20) DEFAULT 'pendente',
                                        observacoes_admin TEXT,
                                        created_at TIMESTAMP,
                                        updated_at TIMESTAMP
                                    )
                                '''))
                            else:
                                conn.execute(text('''
                                    CREATE TABLE IF NOT EXISTS reciclagem (
                                        id SERIAL PRIMARY KEY,
                                        tipo_material VARCHAR(50) NOT NULL,
                                        nome_completo VARCHAR(200) NOT NULL,
                                        telefone VARCHAR(20) NOT NULL,
                                        endereco_retirada TEXT NOT NULL,
                                        observacoes TEXT,
                                        status VARCHAR(20) DEFAULT 'pendente',
                                        observacoes_admin TEXT,
                                        created_at TIMESTAMP,
                                        updated_at TIMESTAMP
                                    )
                                '''))
                            conn.commit()
                        print('✅ Tabela reciclagem criada manualmente')
                except Exception as rec_manual_error:
                    print(f'⚠️ Erro ao criar tabela reciclagem manualmente: {rec_manual_error}')
            
            # Verificar se há usuários, se não houver, inicializar dados
            try:
                from sqlalchemy import inspect
                inspector = inspect(db.engine)
                tables = inspector.get_table_names()
                print(f"📋 Tabelas encontradas: {len(tables)}")
                
                if tables and 'usuario' in tables:
                    try:
                        usuario_count = Usuario.query.count()
                        print(f"👥 Usuários no banco: {usuario_count}")
                        if usuario_count == 0:
                            # Se não houver usuários, inicializar o banco completamente
                            print("🔄 Nenhum usuário encontrado. Inicializando banco de dados...")
                            init_db()
                        else:
                            print("✅ Banco de dados já possui dados - não será reinicializado")
                    except Exception as e:
                        print(f"⚠️ Nota: Erro ao verificar usuários: {e}")
                        # Se não conseguir verificar, tentar inicializar
                        try:
                            init_db()
                        except:
                            pass
                else:
                    print("⚠️ Tabela 'usuario' não encontrada - inicializando banco...")
                    init_db()
            except Exception as e:
                print(f"⚠️ Nota: Erro ao verificar tabelas: {e}")
                # Tentar inicializar de qualquer forma
                try:
                    init_db()
                except:
                    pass
    except Exception as e:
        print(f"❌ Aviso: Erro ao inicializar banco de dados: {e}")
        # Não falhar a importação se houver erro no banco
        # O banco será inicializado na primeira requisição

# Cache para evitar verificar migrações em todas as requisições
# Incluir TODOS os modelos que têm colunas base64
# Usar tupla (table, column) como chave para permitir múltiplas colunas por tabela
_migration_cache = {}
_migration_lock = False
_migration_initialized = False

# Controle de atualização do Instagram para evitar múltiplas threads simultâneas
_instagram_update_lock = False
_instagram_last_update_time = None
_instagram_update_interval = timedelta(hours=6)  # Atualizar no máximo a cada 6 horas

def _add_base64_column(inspector, conn, table_name, column_name, is_sqlite):
    """Função auxiliar para adicionar coluna base64 a uma tabela (alias para _add_column)"""
    return _add_column(inspector, conn, table_name, column_name, is_sqlite, 'TEXT')

def ensure_base64_columns(force=False):
    """
    Garante que as colunas base64 existem antes de fazer queries.
    Esta função é CRÍTICA e deve ser executada antes de qualquer query que use modelos com imagens.
    """
    global _migration_cache, _migration_lock, _migration_initialized
    
    # Evitar execuções simultâneas
    if _migration_lock:
        # Aguardar um pouco e tentar novamente
        import time
        time.sleep(0.1)
        if _migration_lock:
            return False
    
    _migration_lock = True
    
    try:
        from sqlalchemy import text, inspect
        from sqlalchemy.exc import ProgrammingError, OperationalError
        
        inspector = inspect(db.engine)
        db_type = db.engine.url.drivername
        is_sqlite = db_type == 'sqlite'
        
        success = True
        
        # Lista de tabelas e suas colunas base64
        # IMPORTANTE: Adicionar também colunas que não são base64 mas foram adicionadas ao modelo
        tables_to_migrate = [
            ('banner', 'imagem_base64'),
            ('banner_conteudo', 'imagem_base64'),
            ('projeto', 'imagen_base64'),  # Projeto usa "imagen" em vez de "imagem"
            ('projeto', 'arquivo_pdf'),  # Campo arquivo_pdf (pode ser caminho ou 'base64:...')
            ('projeto', 'arquivo_pdf_base64'),  # PDF do projeto em base64
            ('acao', 'imagem_base64'),
            ('evento', 'imagem_base64'),
            ('informativo', 'imagem_base64'),
            ('radio_programa', 'imagem_base64'),
            ('membro_diretoria', 'foto_base64'),
            ('membro_conselho_fiscal', 'foto_base64'),
            ('relatorio_atividade', 'arquivo_base64'),
            ('associado', 'carteira_pdf_base64'),
        ]
        
        for table_name, column_name in tables_to_migrate:
            cache_key = (table_name, column_name)  # Usar tupla como chave
            
            # SEMPRE verificar se a coluna realmente existe, não confiar apenas no cache
            # Isso é crítico porque o cache pode estar incorreto após um deploy
            try:
                if table_name in inspector.get_table_names():
                    # Verificar se a coluna realmente existe
                    column_exists = False
                    with db.engine.connect() as conn:
                        if is_sqlite:
                            result = conn.execute(text("PRAGMA table_info({})".format(table_name)))
                            columns = [row[1] for row in result]
                            column_exists = column_name in columns
                        else:
                            # PostgreSQL
                            result = conn.execute(text("""
                                SELECT EXISTS (
                                    SELECT 1 
                                    FROM information_schema.columns 
                                    WHERE table_name = :table_name 
                                    AND column_name = :column_name
                                )
                            """), {'table_name': table_name, 'column_name': column_name})
                            column_exists = result.scalar()
                    
                    # Se a coluna não existe, criar agora
                    if not column_exists:
                        print(f"🔧 Coluna {table_name}.{column_name} não existe. Criando agora...")
                        with db.engine.connect() as conn:
                            result = _add_column(inspector, conn, table_name, column_name, is_sqlite, 'TEXT')
                            if not result:
                                success = False
                                print(f"❌ Falha ao criar coluna {table_name}.{column_name}")
                            else:
                                print(f"✅ Coluna {table_name}.{column_name} criada com sucesso")
                                _migration_cache[cache_key] = True
                    else:
                        # Coluna existe, marcar no cache
                        _migration_cache[cache_key] = True
                else:
                    # Tabela não existe ainda, marcar no cache para não tentar novamente
                    _migration_cache[cache_key] = True
            except Exception as e:
                print(f"⚠️ Erro ao verificar/adicionar coluna {table_name}.{column_name}: {e}")
                import traceback
                traceback.print_exc()
                success = False
                # NÃO marcar como verificado se houve erro - tentar novamente na próxima vez
        
        if success:
            _migration_initialized = True
        
        return success
        
    except Exception as e:
        print(f"⚠️ Erro geral em ensure_base64_columns: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        _migration_lock = False

# Inicializar banco quando o módulo for importado (para gunicorn)
# Isso garante que as tabelas existam antes do servidor iniciar
# Mas não falha a importação se houver problemas
try:
    with app.app_context():
        ensure_db_initialized()
        # Garantir que as colunas base64 existem logo após a inicialização
        ensure_base64_columns(force=True)
except Exception as e:
    print(f"Nota: Banco será inicializado na primeira requisição: {e}")
    pass

def _ensure_informativo_slug_column():
    """Garante que a coluna slug existe na tabela informativo"""
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
        
        # Verificar se a tabela existe
        if 'informativo' not in inspector.get_table_names():
            return
        
        # Verificar se a coluna slug existe
        columns = [col['name'] for col in inspector.get_columns('informativo')]
        if 'slug' not in columns:
            print("Adicionando coluna 'slug' à tabela 'informativo'...")
            db_type = db.engine.url.drivername
            if db_type == 'postgresql':
                db.session.execute(text("ALTER TABLE informativo ADD COLUMN IF NOT EXISTS slug VARCHAR(250)"))
            else:
                # SQLite
                db.session.execute(text("ALTER TABLE informativo ADD COLUMN slug VARCHAR(250)"))
            db.session.commit()
            print("✅ Coluna 'slug' adicionada com sucesso!")
            
            # Gerar slugs para informativos existentes que não têm (usar query raw para evitar problemas)
            result = db.session.execute(text("SELECT id, titulo FROM informativo WHERE slug IS NULL OR slug = ''"))
            informativos_raw = result.fetchall()
            
            if informativos_raw:
                print(f"Gerando slugs para {len(informativos_raw)} informativo(s) existente(s)...")
                for row in informativos_raw:
                    informativo_id = row[0]
                    titulo = row[1]
                    slug = gerar_slug_unico(titulo, Informativo, informativo_id)
                    db.session.execute(
                        text("UPDATE informativo SET slug = :slug WHERE id = :id"),
                        {"slug": slug, "id": informativo_id}
                    )
                db.session.commit()
                print(f"✅ {len(informativos_raw)} slug(s) gerado(s) com sucesso!")
    except Exception as e:
        db.session.rollback()
        print(f"⚠️ Erro ao verificar/adicionar coluna slug: {e}")

def _ensure_slug_columns():
    """Garante que as colunas slug existem nas tabelas necessárias"""
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
        
        # Tabelas que precisam de slug - mapeamento table_name -> model_class
        tables_with_slug = [
            ('projeto', Projeto),
            ('acao', Acao),
            ('evento', Evento),
            ('reunion_presencial', ReunionPresencial),
            ('reunion_virtual', ReunionVirtual)
        ]
        
        for table_name, model_class in tables_with_slug:
            # Verificar se a tabela existe
            if table_name not in inspector.get_table_names():
                continue
            
            # Verificar se a coluna slug existe
            columns = [col['name'] for col in inspector.get_columns(table_name)]
            if 'slug' not in columns:
                print(f"Adicionando coluna 'slug' à tabela '{table_name}'...")
                db_type = db.engine.url.drivername
                if db_type == 'postgresql':
                    db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS slug VARCHAR(250)"))
                else:
                    # SQLite
                    db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN slug VARCHAR(250)"))
                db.session.commit()
                print(f"✅ Coluna 'slug' adicionada à tabela '{table_name}'!")
            
            # Gerar slugs para registros existentes que não têm (usar query raw)
            result = db.session.execute(text(f"SELECT id, titulo FROM {table_name} WHERE slug IS NULL OR slug = ''"))
            records_raw = result.fetchall()
            
            if records_raw:
                print(f"Gerando slugs para {len(records_raw)} registro(s) existente(s) em '{table_name}'...")
                for row in records_raw:
                    record_id = row[0]
                    titulo = row[1]
                    slug = gerar_slug_unico(titulo, model_class, record_id)
                    db.session.execute(
                        text(f"UPDATE {table_name} SET slug = :slug WHERE id = :id"),
                        {"slug": slug, "id": record_id}
                    )
                db.session.commit()
                print(f"✅ {len(records_raw)} slug(s) gerado(s) para '{table_name}'!")
    except Exception as e:
        db.session.rollback()
        print(f"⚠️ Erro ao verificar/adicionar colunas slug: {e}")

# Garantir que migrações sejam executadas ANTES de cada requisição
# Isso é CRÍTICO para evitar erros de coluna não encontrada
@app.before_request
def before_request():
    """Executa migrações antes de cada requisição se necessário"""
    ensure_base64_columns()
    _ensure_slug_columns()
    _ensure_informativo_slug_column()

# ============================================
# SEO: Sitemap e Robots.txt
# ============================================

@app.route('/sitemap.xml')
def sitemap():
    """Gera sitemap.xml dinâmico para SEO"""
    from flask import Response
    from xml.etree.ElementTree import Element, SubElement, tostring
    
    url_root = request.url_root.rstrip('/')
    
    urlset = Element('urlset')
    urlset.set('xmlns', 'http://www.sitemaps.org/schemas/sitemap/0.9')
    
    # Páginas principais (prioridade alta)
    main_pages = [
        ('/', '1.0', 'daily'),
        ('/sobre', '0.9', 'weekly'),
        ('/projetos', '0.9', 'weekly'),
        ('/acoes', '0.9', 'weekly'),
        ('/informativo', '0.8', 'daily'),
        ('/radio', '0.8', 'daily'),
        ('/videos', '0.8', 'weekly'),
        ('/galeria', '0.8', 'weekly'),
        ('/apoiadores', '0.7', 'monthly'),
        ('/agenda-presencial', '0.8', 'weekly'),
        ('/agenda-virtual', '0.8', 'weekly'),
        ('/transparencia', '0.7', 'monthly'),
        ('/problema-acessibilidade/registrar', '0.8', 'monthly'),
        ('/certificados/validar', '0.6', 'monthly'),
    ]
    
    for path, priority, changefreq in main_pages:
        url_elem = SubElement(urlset, 'url')
        SubElement(url_elem, 'loc').text = f"{url_root}{path}"
        SubElement(url_elem, 'changefreq').text = changefreq
        SubElement(url_elem, 'priority').text = priority
        SubElement(url_elem, 'lastmod').text = datetime.utcnow().strftime('%Y-%m-%d')
    
    # Informativos (prioridade média-alta)
    informativos = Informativo.query.filter_by(ativo=True).all()
    for info in informativos:
        url_elem = SubElement(urlset, 'url')
        # Usar slug se disponível, senão usar ID
        url_slug = info.slug if info.slug else str(info.id)
        SubElement(url_elem, 'loc').text = f"{url_root}/informativo/{url_slug}"
        SubElement(url_elem, 'changefreq').text = 'weekly'
        SubElement(url_elem, 'priority').text = '0.8'
        if info.created_at:
            SubElement(url_elem, 'lastmod').text = info.created_at.strftime('%Y-%m-%d')
    
    xml_str = tostring(urlset, encoding='unicode')
    xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str
    
    return Response(xml_str, mimetype='application/xml')


@app.route('/robots.txt')
def robots():
    """Gera robots.txt para SEO"""
    from flask import Response
    url_root = request.url_root.rstrip('/')
    robots_content = f"""User-agent: *
Allow: /
Disallow: /admin/
Disallow: /associado/
Disallow: /voluntario/
Disallow: /login
Disallow: /admin/login

Sitemap: {url_root}/sitemap.xml
"""
    return Response(robots_content, mimetype='text/plain')


if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)

