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

    # Tentar executar migração para tabela SOS
    try:
        import migrate_postgres_sos as mig_sos
        print('Executando migração SOS (se aplicável)...')
        code2 = mig_sos.migrate()
        if code2 != 0:
            print(f'Migração SOS retornou código {code2} (continuando startup).')
        else:
            print('Migração SOS finalizada com sucesso.')
    except Exception as e:
        print('Não foi possível importar/rodar migrate_postgres_sos:', e)
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
