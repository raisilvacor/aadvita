"""
Script para atualizar a data de created_at dos associados para a data atual
"""
from app import app, db
from models import Associado
from datetime import datetime

with app.app_context():
    # Buscar todos os associados
    associados = Associado.query.all()
    
    # Atualizar created_at para a data atual
    for associado in associados:
        associado.created_at = datetime.now()
    
    db.session.commit()
    print(f"Atualizados {len(associados)} associados com a data atual: {datetime.now().strftime('%d/%m/%Y')}")

