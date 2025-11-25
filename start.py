import os
import sys
import time

from subprocess import Popen


def run_migration():
    # Import locally to surface errors clearly
    try:
        import migrate_postgres_voluntario as mig
    except Exception as e:
        print('Não foi possível importar migrate_postgres_voluntario:', e)
        return 1

    try:
        print('Executando migração Postgres (se aplicável)...')
        code = mig.migrate()
        if code != 0:
            print(f'Migração retornou código {code} (continuando startup).')
        else:
            print('Migração finalizada com sucesso.')
    except Exception as e:
        print('Erro ao executar migração:', e)
        # Continuar startup mesmo se a migração falhar — admin pode executar manualmente

    # Tentar executar migração para associado (coluna foto_base64)
    try:
        import migrate_postgres_associado as mig_ass
        print('Executando migração associado (se aplicável)...')
        code3 = mig_ass.migrate()
        if code3 != 0:
            print(f'Migração associado retornou código {code3} (continuando startup).')
        else:
            print('Migração associado finalizada com sucesso.')
    except Exception as e:
        print('Não foi possível importar/rodar migrate_postgres_associado:', e)
        # continuar
    
    # Tentar executar migração para problema_acessibilidade
    try:
        import migrate_postgres_problema_acessibilidade as mig_problema
        print('Executando migração problema_acessibilidade (se aplicável)...')
        code4 = mig_problema.migrate()
        if code4 != 0:
            print(f'Migração problema_acessibilidade retornou código {code4} (continuando startup).')
        else:
            print('Migração problema_acessibilidade finalizada com sucesso.')
    except Exception as e:
        print('Não foi possível importar/rodar migrate_postgres_problema_acessibilidade:', e)
        # continuar

    # Tentar executar migração para certificados
    try:
        import migrate_postgres_certificado as mig_certificado
        print('Executando migração certificado (se aplicável)...')
        code5 = mig_certificado.migrate()
        if code5 != 0:
            print(f'Migração certificado retornou código {code5} (continuando startup).')
        else:
            print('Migração certificado finalizada com sucesso.')
    except Exception as e:
        print('Não foi possível importar/rodar migrate_postgres_certificado:', e)
        # continuar
    
    # Tentar executar migração para reciclagem
    try:
        import migrate_postgres_reciclagem as mig_reciclagem
        print('Executando migração reciclagem (se aplicável)...')
        code6 = mig_reciclagem.migrate()
        if code6 != 0:
            print(f'Migração reciclagem retornou código {code6} (continuando startup).')
        else:
            print('Migração reciclagem finalizada com sucesso.')
    except Exception as e:
        print('Não foi possível importar/rodar migrate_postgres_reciclagem:', e)
        # continuar
    return 0


def start_gunicorn():
    port = os.environ.get('PORT', '10000')
    # Exec gunicorn replacing current process so Render can manage it
    cmd = ['gunicorn', 'app:app', '--bind', f'0.0.0.0:{port}']
    print('Iniciando gunicorn com:', ' '.join(cmd))
    os.execvp('gunicorn', cmd)


if __name__ == '__main__':
    # Allow more time for DB service to become available; migration script will also retry
    time.sleep(5)
    run_migration()
    start_gunicorn()
