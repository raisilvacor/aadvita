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

    return 0


def start_gunicorn():
    port = os.environ.get('PORT', '10000')
    # Exec gunicorn replacing current process so Render can manage it
    cmd = ['gunicorn', 'app:app', '--bind', f'0.0.0.0:{port}']
    print('Iniciando gunicorn com:', ' '.join(cmd))
    os.execvp('gunicorn', cmd)


if __name__ == '__main__':
    # Small delay to let DB service become available in some environments
    time.sleep(1)
    run_migration()
    start_gunicorn()
