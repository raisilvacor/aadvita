import os
import sys
import time

from subprocess import Popen


def run_migration():
    # Tentar executar migração completa de voluntario (cria tabelas se não existirem)
    try:
        import migrate_postgres_voluntario_full as mig_vol_full
        print('Executando migração voluntario_full (se aplicável)...')
        code_vol_full = mig_vol_full.migrate()
        if code_vol_full != 0:
            print(f'Migração voluntario_full retornou código {code_vol_full} (continuando startup).')
        else:
            print('Migração voluntario_full finalizada com sucesso.')
    except Exception as e:
        print('Não foi possível importar/rodar migrate_postgres_voluntario_full:', e)
        # continuar

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

    # Tentar executar migração para associado (cria tabela e colunas se necessário)
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

    # Tentar executar migração para mensalidade
    try:
        import migrate_postgres_mensalidade as mig_mensalidade
        print('Executando migração mensalidade (se aplicável)...')
        code_mensal = mig_mensalidade.migrate()
        if code_mensal != 0:
            print(f'Migração mensalidade retornou código {code_mensal} (continuando startup).')
        else:
            print('Migração mensalidade finalizada com sucesso.')
    except Exception as e:
        print('Não foi possível importar/rodar migrate_postgres_mensalidade:', e)
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

    # Tentar executar migração para radio
    try:
        import migrate_postgres_radio as mig_radio
        print('Executando migração radio (se aplicável)...')
        code7 = mig_radio.migrate()
        if code7 != 0:
            print(f'Migração radio retornou código {code7} (continuando startup).')
        else:
            print('Migração radio finalizada com sucesso.')
    except Exception as e:
        print('Não foi possível importar/rodar migrate_postgres_radio:', e)
        # continuar

    # Tentar executar migração para informativo
    try:
        import migrate_postgres_informativo as mig_informativo
        print('Executando migração informativo (se aplicável)...')
        code8 = mig_informativo.migrate()
        if code8 != 0:
            print(f'Migração informativo retornou código {code8} (continuando startup).')
        else:
            print('Migração informativo finalizada com sucesso.')
    except Exception as e:
        print('Não foi possível importar/rodar migrate_postgres_informativo:', e)
        # continuar

    # Tentar executar migração para galeria
    try:
        import migrate_postgres_galeria as mig_galeria
        print('Executando migração galeria (se aplicável)...')
        code9 = mig_galeria.migrate()
        if code9 != 0:
            print(f'Migração galeria retornou código {code9} (continuando startup).')
        else:
            print('Migração galeria finalizada com sucesso.')
    except Exception as e:
        print('Não foi possível importar/rodar migrate_postgres_galeria:', e)
        # continuar

    # Tentar executar migração para reuniones
    try:
        import migrate_postgres_reuniones as mig_reuniones
        print('Executando migração reuniones (se aplicável)...')
        code10 = mig_reuniones.migrate()
        if code10 != 0:
            print(f'Migração reuniones retornou código {code10} (continuando startup).')
        else:
            print('Migração reuniones finalizada com sucesso.')
    except Exception as e:
        print('Não foi possível importar/rodar migrate_postgres_reuniones:', e)
        # continuar

    # Tentar executar migração para projetos
    try:
        import migrate_postgres_projetos as mig_projetos
        print('Executando migração projetos (se aplicável)...')
        code11 = mig_projetos.migrate()
        if code11 != 0:
            print(f'Migração projetos retornou código {code11} (continuando startup).')
        else:
            print('Migração projetos finalizada com sucesso.')
    except Exception as e:
        print('Não foi possível importar/rodar migrate_postgres_projetos:', e)
        # continuar

    # Tentar executar migração para acoes
    try:
        import migrate_postgres_acoes as mig_acoes
        print('Executando migração acoes (se aplicável)...')
        code12 = mig_acoes.migrate()
        if code12 != 0:
            print(f'Migração acoes retornou código {code12} (continuando startup).')
        else:
            print('Migração acoes finalizada com sucesso.')
    except Exception as e:
        print('Não foi possível importar/rodar migrate_postgres_acoes:', e)
        # continuar

    # Tentar executar migração para eventos
    try:
        import migrate_postgres_eventos as mig_eventos
        print('Executando migração eventos (se aplicável)...')
        code13 = mig_eventos.migrate()
        if code13 != 0:
            print(f'Migração eventos retornou código {code13} (continuando startup).')
        else:
            print('Migração eventos finalizada com sucesso.')
    except Exception as e:
        print('Não foi possível importar/rodar migrate_postgres_eventos:', e)
        # continuar

    # Tentar executar migração para usuario/permissao
    try:
        import migrate_postgres_usuario as mig_usuario
        print('Executando migração usuario (se aplicável)...')
        code15 = mig_usuario.migrate()
        if code15 != 0:
            print(f'Migração usuario retornou código {code15} (continuando startup).')
        else:
            print('Migração usuario finalizada com sucesso.')
    except Exception as e:
        print('Não foi possível importar/rodar migrate_postgres_usuario:', e)
        # continuar

    # Tentar executar migração para extras (album, apoiador, tabelas associativas)
    try:
        import migrate_postgres_extras as mig_extras
        print('Executando migração extras (se aplicável)...')
        code14 = mig_extras.migrate()
        if code14 != 0:
            print(f'Migração extras retornou código {code14} (continuando startup).')
        else:
            print('Migração extras finalizada com sucesso.')
    except Exception as e:
        print('Não foi possível importar/rodar migrate_postgres_extras:', e)
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
