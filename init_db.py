#!/usr/bin/env python
"""
Script para inicializar o banco de dados
Execute este script antes de iniciar o servidor em produção
"""
from app import app, db, init_db

if __name__ == '__main__':
    with app.app_context():
        print("Inicializando banco de dados...")
        init_db()
        print("Banco de dados inicializado com sucesso!")

