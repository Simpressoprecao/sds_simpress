"""
Script para varredura autônoma do SDS.
Pode rodar local (Windows) ou via cron no cPanel.

Faz a varredura no SDS e salva os dados no MySQL (configurado em config_db.json).
"""

import sys, os, json

CAMINHO = os.path.dirname(os.path.abspath(__file__))
os.chdir(CAMINHO)

CONFIG_DB_REMOTO = {
    "host": "SEU_HOST_MYSQL_CPANEL",
    "port": 3306,
    "user": "SEU_USUARIO_MYSQL",
    "password": "SUA_SENHA_MYSQL",
    "database": "SEU_BANCO_MYSQL"
}

def main():
    # Configura o banco remoto
    with open("config_db.json", "w", encoding="utf-8") as f:
        json.dump(CONFIG_DB_REMOTO, f, ensure_ascii=False, indent=2)

    print("Conectando ao MySQL remoto...")
    from database import Database, carregar_config_db
    db = Database()
    try:
        db.conectar()
        db.criar_tabelas()
        print("Tabelas criadas/verificadas com sucesso!")
    except Exception as e:
        print(f"Erro ao conectar no MySQL: {e}")
        return

    print("Iniciando varredura SDS...")
    from varredura_completa import varrer_todos
    from app import salvar_no_banco

    dispositivos = varrer_todos()

    if not dispositivos:
        print("Nenhum dispositivo encontrado na varredura!")
        return

    print(f"Varredura concluida: {len(dispositivos)} dispositivos")
    print("Salvando no MySQL remoto...")

    for i, dados in enumerate(dispositivos, 1):
        try:
            salvar_no_banco(dados)
            print(f"  [{i}/{len(dispositivos)}] OK - {dados.get('dispositivo', {}).get('N\u00famero de s\u00e9rie', '?')}")
        except Exception as e:
            print(f"  [{i}/{len(dispositivos)}] ERRO: {e}")

    print("Sincronizacao concluida com sucesso!")


if __name__ == "__main__":
    main()
