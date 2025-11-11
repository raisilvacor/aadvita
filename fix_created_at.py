"""
Script para atualizar a data de created_at dos associados para a data atual
"""
import sqlite3
from datetime import datetime

# Conectar ao banco de dados
conn = sqlite3.connect('instance/aadvita.db')
cursor = conn.cursor()

# Atualizar todos os associados com a data atual
cursor.execute("""
    UPDATE associado 
    SET created_at = datetime('now', 'localtime')
    WHERE created_at IS NOT NULL
""")

# Verificar quantos registros foram atualizados
cursor.execute("SELECT COUNT(*) FROM associado")
count = cursor.fetchone()[0]

conn.commit()
conn.close()

print(f"Atualizados {count} associados com a data atual: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

