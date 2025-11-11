#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para popular a tabela o_que_fazemos_servico com os dados iniciais
"""

import sqlite3
import os

# Verificar se o banco existe
db_paths = [
    'instance/aadvita.db',
    'instance/database.db',
    'aadvita.db'
]

db_path = None
for path in db_paths:
    if os.path.exists(path):
        db_path = path
        break

if not db_path:
    print("Banco de dados não encontrado!")
    exit(1)

print(f"Usando banco de dados: {db_path}")

# Serviços iniciais baseados na imagem
servicos_iniciais = [
    # Coluna 1
    {
        'titulo': 'Biblioteca',
        'descricao': 'Acervo em Braille de 821 exemplares, 1.365 livros em versão audiobook e 1.415 exemplares em tinta.',
        'cor_icone': '#dc2626',
        'icone_svg': '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M19 3H5C3.9 3 3 3.9 3 5V19C3 20.1 3.9 21 5 21H19C20.1 21 21 20.1 21 19V5C21 3.9 20.1 3 19 3ZM19 19H5V5H19V19ZM17 12H7V10H17V12ZM15 16H7V14H15V16ZM17 8H7V6H17V8Z" fill="white"/></svg>',
        'ordem': 1,
        'coluna': 1,
        'ativo': True
    },
    {
        'titulo': 'Orientação e Mobilidade',
        'descricao': 'Orientação e mobilidade de acordo com os diagnósticos funcionais.',
        'cor_icone': '#14b8a6',
        'icone_svg': '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M8 4L8 20M16 4L16 20M8 12L16 12" stroke="white" stroke-width="2.5" stroke-linecap="round"/><circle cx="8" cy="8" r="1.5" fill="white"/><circle cx="16" cy="8" r="1.5" fill="white"/><circle cx="8" cy="16" r="1.5" fill="white"/><circle cx="16" cy="16" r="1.5" fill="white"/></svg>',
        'ordem': 2,
        'coluna': 1,
        'ativo': True
    },
    {
        'titulo': 'Psicologia',
        'descricao': 'Acompanhamento para os deficientes visuais em grupo e individualizado.',
        'cor_icone': '#eab308',
        'icone_svg': '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 2V8M8 6L12 8L16 6M8 12C8 12 9 14 12 14C15 14 16 12 16 12M12 14V20M6 18L12 20L18 18" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/><circle cx="12" cy="4" r="1.5" fill="white"/></svg>',
        'ordem': 3,
        'coluna': 1,
        'ativo': True
    },
    {
        'titulo': 'Esporte',
        'descricao': 'Aulas de Goalball, Futebol de 5, Atletismo e Ginástica Funcional.',
        'cor_icone': '#22c55e',
        'icone_svg': '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="12" r="9" stroke="white" stroke-width="2" fill="none"/><path d="M8 10C8 10 9 12 12 12C15 12 16 10 16 10" stroke="white" stroke-width="2" stroke-linecap="round"/><path d="M9 15C9 15 10 17 12 17C14 17 15 15 15 15" stroke="white" stroke-width="2" stroke-linecap="round"/></svg>',
        'ordem': 4,
        'coluna': 1,
        'ativo': True
    },
    # Coluna 2
    {
        'titulo': 'Educação',
        'descricao': 'Com mais de 50 colaboradores, temos um corpo docente pronto para a alfabetização e contraturno escolar.',
        'cor_icone': '#22c55e',
        'icone_svg': '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 3L4 8V16L12 21L20 16V8L12 3Z" stroke="white" stroke-width="2" stroke-linejoin="round" fill="none"/><path d="M12 21V12" stroke="white" stroke-width="2"/><path d="M4 8L12 12L20 8" stroke="white" stroke-width="2"/><path d="M4 16L12 12L20 16" stroke="white" stroke-width="2"/></svg>',
        'ordem': 1,
        'coluna': 2,
        'ativo': True
    },
    {
        'titulo': 'Informática e novas tecnologias',
        'descricao': 'Uso de tecnologias para trabalhar a autoconfiança dos alunos.',
        'cor_icone': '#0d9488',
        'icone_svg': '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="2" y="4" width="20" height="14" rx="2" stroke="white" stroke-width="2" fill="none"/><path d="M2 8H22" stroke="white" stroke-width="2"/><rect x="4" y="11" width="16" height="5" rx="1" fill="white"/></svg>',
        'ordem': 2,
        'coluna': 2,
        'ativo': True
    },
    {
        'titulo': 'Rádio',
        'descricao': 'Estúdio que, desde 2011, usa vozes para transformar vidas.',
        'cor_icone': '#eab308',
        'icone_svg': '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 2C10.34 2 9 3.34 9 5V11C9 12.66 10.34 14 12 14C13.66 14 15 12.66 15 11V5C15 3.34 13.66 2 12 2Z" fill="white"/><path d="M19 10V11C19 14.87 15.87 18 12 18C8.13 18 5 14.87 5 11V10" stroke="white" stroke-width="2" stroke-linecap="round"/><path d="M12 18V22M8 22H16" stroke="white" stroke-width="2" stroke-linecap="round"/></svg>',
        'ordem': 3,
        'coluna': 2,
        'ativo': True
    },
    {
        'titulo': 'Projetos',
        'descricao': 'Projetos que ampliam o acesso de pessoas com deficiência visual a obras escritas por meio de audiobooks.',
        'cor_icone': '#3b82f6',
        'icone_svg': '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M3 12H5M7 8H9M7 16H9M11 6H13M11 18H13M15 8H17M15 16H17M19 12H21" stroke="white" stroke-width="2.5" stroke-linecap="round"/><circle cx="5" cy="12" r="1.5" fill="white"/><circle cx="9" cy="8" r="1.5" fill="white"/><circle cx="9" cy="16" r="1.5" fill="white"/><circle cx="13" cy="6" r="1.5" fill="white"/><circle cx="13" cy="18" r="1.5" fill="white"/><circle cx="17" cy="8" r="1.5" fill="white"/><circle cx="17" cy="16" r="1.5" fill="white"/><circle cx="21" cy="12" r="1.5" fill="white"/></svg>',
        'ordem': 4,
        'coluna': 2,
        'ativo': True
    },
    # Coluna 3
    {
        'titulo': 'Ensino em Braille',
        'descricao': 'Salas de recursos encorajam os deficientes visuais na busca por um lugar participativo na sociedade.',
        'cor_icone': '#dc2626',
        'icone_svg': '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="6" cy="7" r="1.5" fill="white"/><circle cx="10" cy="7" r="1.5" fill="white"/><circle cx="14" cy="7" r="1.5" fill="white"/><circle cx="18" cy="7" r="1.5" fill="white"/><circle cx="6" cy="12" r="1.5" fill="white"/><circle cx="10" cy="12" r="1.5" fill="white"/><circle cx="14" cy="12" r="1.5" fill="white"/><circle cx="18" cy="12" r="1.5" fill="white"/><circle cx="6" cy="17" r="1.5" fill="white"/><circle cx="10" cy="17" r="1.5" fill="white"/><circle cx="14" cy="17" r="1.5" fill="white"/><circle cx="18" cy="17" r="1.5" fill="white"/></svg>',
        'ordem': 1,
        'coluna': 3,
        'ativo': True
    },
    {
        'titulo': 'Música',
        'descricao': 'Com a Musicografia Braille, os educandos encantam por onde passam.',
        'cor_icone': '#a855f7',
        'icone_svg': '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 3V15M12 15L8 11M12 15L16 11M5 18H19C19.5523 18 20 17.5523 20 17V19C20 19.5523 19.5523 20 19 20H5C4.44772 20 4 19.5523 4 19V17C4 17.5523 4.44772 18 5 18Z" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><circle cx="9" cy="6" r="1.5" fill="white"/><circle cx="15" cy="6" r="1.5" fill="white"/></svg>',
        'ordem': 2,
        'coluna': 3,
        'ativo': True
    },
    {
        'titulo': 'Serviço Social',
        'descricao': 'Autonomia, inclusão social e melhoria na qualidade de vida dos usuários.',
        'cor_icone': '#ec4899',
        'icone_svg': '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 21.35L10.55 20.03C5.4 15.36 2 12.28 2 8.5C2 5.42 4.42 3 7.5 3C9.24 3 10.91 3.81 12 5.09C13.09 3.81 14.76 3 16.5 3C19.58 3 22 5.42 22 8.5C22 12.28 18.6 15.36 13.45 20.03L12 21.35Z" fill="white"/></svg>',
        'ordem': 3,
        'coluna': 3,
        'ativo': True
    },
    {
        'titulo': 'Terapia Ocupacional',
        'descricao': 'Treino de atividades para estimular a independência, autonomia e integração do indivíduo na sociedade. Estimulação Visual',
        'cor_icone': '#14b8a6',
        'icone_svg': '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="8" r="4" stroke="white" stroke-width="2" fill="none"/><path d="M6 21V19C6 17.3431 7.34315 16 9 16H15C16.6569 16 18 17.3431 18 19V21" stroke="white" stroke-width="2" stroke-linecap="round"/></svg>',
        'ordem': 4,
        'coluna': 3,
        'ativo': True
    }
]

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Verificar se já existem serviços
    cursor.execute("SELECT COUNT(*) FROM o_que_fazemos_servico")
    count = cursor.fetchone()[0]
    
    if count > 0:
        print(f"Já existem {count} serviços cadastrados. Pulando população inicial.")
        print("Para recriar os serviços, delete-os primeiro pelo admin.")
    else:
        # Inserir serviços
        for servico in servicos_iniciais:
            cursor.execute("""
                INSERT INTO o_que_fazemos_servico 
                (titulo, descricao, cor_icone, icone_svg, ordem, coluna, ativo, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """, (
                servico['titulo'],
                servico['descricao'],
                servico['cor_icone'],
                servico['icone_svg'],
                servico['ordem'],
                servico['coluna'],
                1 if servico['ativo'] else 0
            ))
        
        conn.commit()
        print(f"{len(servicos_iniciais)} serviços criados com sucesso!")
    
    conn.close()
    
except Exception as e:
    print(f"Erro ao popular serviços: {str(e)}")
    import traceback
    traceback.print_exc()
    exit(1)

