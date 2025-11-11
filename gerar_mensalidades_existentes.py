# -*- coding: utf-8 -*-
"""
Script para gerar mensalidades de 1 ano para associados já cadastrados
Execute este script uma vez para aplicar a nova lógica aos associados existentes
"""
import sys
import io
from datetime import datetime, date, timedelta
from calendar import monthrange

# Configurar encoding para Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Importar o app Flask
from app import app, db
from app import Associado, Mensalidade

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

def gerar_mensalidades_ano(associado, forcar_regeneracao=False):
    """
    Gera mensalidades para 1 ano (12 meses) para um associado
    - Primeira mensalidade: vencimento em 3 dias úteis após cadastro/aprovação
    - Próximas 11 mensalidades: vencimento fixo no mesmo dia do mês do cadastro/aprovação
    """
    # Verificar se já existe alguma mensalidade para este associado
    mensalidades_existentes = Mensalidade.query.filter_by(associado_id=associado.id).all()
    
    if mensalidades_existentes and not forcar_regeneracao:
        return False  # Já existe mensalidade, não gerar
    
    # Se forçar regeneração, deletar mensalidades existentes
    if mensalidades_existentes and forcar_regeneracao:
        for mensalidade in mensalidades_existentes:
            db.session.delete(mensalidade)
        db.session.commit()
        print(f"    → Mensalidades antigas removidas")
    
    # Verificar se o associado tem valor de mensalidade configurado
    if not associado.valor_mensalidade or associado.valor_mensalidade <= 0:
        return False  # Não tem valor configurado, não gerar
    
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
    
    return True

def main():
    with app.app_context():
        print("=" * 60)
        print("GERANDO MENSALIDADES PARA ASSOCIADOS EXISTENTES")
        print("=" * 60)
        print()
        
        # Buscar todos os associados aprovados com valor de mensalidade
        associados = Associado.query.filter_by(
            status='aprovado'
        ).filter(Associado.valor_mensalidade > 0).all()
        
        total_associados = len(associados)
        gerados = 0
        ja_existentes = 0
        sem_valor = 0
        
        print(f"Total de associados aprovados com mensalidade: {total_associados}")
        print()
        
        for associado in associados:
            try:
                # Verificar se já tem mensalidades
                tem_mensalidades = Mensalidade.query.filter_by(associado_id=associado.id).first()
                
                if tem_mensalidades:
                    print(f"⚠ [{associado.nome_completo}] - Já possui mensalidades cadastradas")
                    print(f"    → Forçando regeneração com nova lógica...")
                    # Forçar regeneração para aplicar a nova lógica
                    sucesso = gerar_mensalidades_ano(associado, forcar_regeneracao=True)
                else:
                    # Gerar mensalidades normalmente
                    sucesso = gerar_mensalidades_ano(associado)
                
                if sucesso:
                    db.session.commit()
                    print(f"✅ [{associado.nome_completo}] - 12 mensalidades geradas com sucesso!")
                    gerados += 1
                else:
                    sem_valor += 1
                    
            except Exception as e:
                db.session.rollback()
                print(f"❌ [{associado.nome_completo}] - Erro: {str(e)}")
        
        print()
        print("=" * 60)
        print("RESUMO:")
        print(f"  ✅ Mensalidades geradas: {gerados}")
        print(f"  ⚠ Já existentes: {ja_existentes}")
        print(f"  ⚠ Sem valor configurado: {sem_valor}")
        print("=" * 60)

if __name__ == '__main__':
    main()

