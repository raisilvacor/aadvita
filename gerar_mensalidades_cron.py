"""
Script para ser executado via cron job/tarefa agendada
Gera mensalidades automaticamente todo mês

Para usar no Windows (Agendador de Tarefas):
- Criar tarefa que executa este script diariamente ou mensalmente

Para usar no Linux (cron):
- Adicionar ao crontab: 0 0 1 * * python /caminho/para/gerar_mensalidades_cron.py
  (executa no dia 1 de cada mês à meia-noite)
"""
import requests
import sys

# URL do seu site (ajuste conforme necessário)
URL = 'http://localhost:5000/api/gerar-mensalidades/aadvita-gerar-mensalidades-2025'

try:
    response = requests.get(URL, timeout=30)
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Sucesso: {data.get('mensensagem', 'Mensalidades geradas')}")
        print(f"   Mensalidades geradas: {data.get('mensalidades_geradas', 0)}")
        sys.exit(0)
    else:
        print(f"❌ Erro: {response.status_code} - {response.text}")
        sys.exit(1)
        
except requests.exceptions.RequestException as e:
    print(f"❌ Erro ao conectar: {str(e)}")
    sys.exit(1)

