#!/usr/bin/env python3
"""
Script de migração para adicionar campo slug aos informativos existentes
"""
import sys
import os

# Adicionar o diretório atual ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, Informativo
import unicodedata
import re
import uuid

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

def gerar_slug_unico(titulo, informativo_id=None):
    """Gera um slug único, adicionando número se necessário"""
    base_slug = gerar_slug(titulo)
    slug = base_slug
    
    # Verificar se já existe um informativo com esse slug (exceto o atual)
    contador = 1
    while True:
        query = Informativo.query.filter_by(slug=slug)
        if informativo_id:
            query = query.filter(Informativo.id != informativo_id)
        if not query.first():
            break
        slug = f"{base_slug}-{contador}"
        contador += 1
        if contador > 1000:  # Limite de segurança
            slug = f"{base_slug}-{uuid.uuid4().hex[:8]}"
            break
    
    return slug

def migrate():
    """Adiciona campo slug aos informativos existentes"""
    with app.app_context():
        try:
            # Verificar se a coluna slug já existe
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('informativo')]
            
            if 'slug' not in columns:
                print("Adicionando coluna 'slug' à tabela 'informativo'...")
                # Adicionar coluna slug
                if db.engine.url.drivername == 'postgresql':
                    with db.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE informativo ADD COLUMN IF NOT EXISTS slug VARCHAR(250)"))
                        conn.commit()
                else:
                    # SQLite
                    with db.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE informativo ADD COLUMN slug VARCHAR(250)"))
                        conn.commit()
                print("✅ Coluna 'slug' adicionada com sucesso!")
            else:
                print("✅ Coluna 'slug' já existe!")
            
            # Gerar slugs para informativos que não têm (usar query raw para evitar problemas com colunas faltantes)
            from sqlalchemy import text
            result = db.session.execute(text("SELECT id, titulo FROM informativo WHERE slug IS NULL OR slug = ''"))
            informativos_raw = result.fetchall()
            
            if informativos_raw:
                print(f"\nGerando slugs para {len(informativos_raw)} informativo(s)...")
                for row in informativos_raw:
                    informativo_id = row[0]
                    titulo = row[1]
                    slug = gerar_slug_unico(titulo, informativo_id)
                    
                    # Atualizar usando query raw
                    db.session.execute(
                        text("UPDATE informativo SET slug = :slug WHERE id = :id"),
                        {"slug": slug, "id": informativo_id}
                    )
                    print(f"  - ID {informativo_id}: '{titulo}' -> '{slug}'")
                
                db.session.commit()
                print(f"\n✅ {len(informativos_raw)} slug(s) gerado(s) com sucesso!")
            else:
                print("\n✅ Todos os informativos já possuem slug!")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro na migração: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    return True

if __name__ == '__main__':
    print("=" * 60)
    print("Migração: Adicionar campo slug aos informativos")
    print("=" * 60)
    
    if migrate():
        print("\n✅ Migração concluída com sucesso!")
    else:
        print("\n❌ Migração falhou!")
        sys.exit(1)

