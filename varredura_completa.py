import json
import os
import sys
import time
from datetime import datetime
from sds_scraper import SDSScraper, salvar_json
from database import Database

ARQUIVO_DADOS = "dados_dispositivo.json"
USUARIO = "ardlopes@simpress.com.br"
SENHA = "Rodrigo2021."
PAUSA_ENTRE_DISPOSITIVOS = 3


def salvar_no_banco(dados):
    try:
        db = Database()
        db.conectar()
        db.salvar_dispositivo(dados)
        db.fechar()
        return True
    except Exception as e:
        print(f"  -> Erro ao salvar no banco: {e}")
        return False


def varrer_todos(headless=True, progresso_callback=None):
    scraper = SDSScraper(USUARIO, SENHA, headless=headless)
    todos_dados = []
    processados = 0
    aceitos = 0
    ignorados = 0
    erros = 0

    try:
        scraper.login()
        ids = scraper.listar_todos_ids()
        total = len(ids)
        print(f"Total de dispositivos encontrados: {total}")

        if progresso_callback:
            progresso_callback("inicio", total=total)

        for idx, device_id in enumerate(ids, 1):
            try:
                print(f"[{idx}/{total}] Processando ID {device_id}...")
                if progresso_callback:
                    progresso_callback("andamento", idx=idx, total=total, device_id=device_id)

                dados = scraper.extrair_tudo(device_id)
                if dados:
                    todos_dados.append(dados)
                    salvar_no_banco(dados)
                    aceitos += 1
                    print(f"  -> Aceito: {dados['dispositivo'].get('modelo', '?')} - Serial: {dados['dispositivo'].get('N\u00famero de s\u00e9rie', '?')}")
                else:
                    ignorados += 1
                    print(f"  -> Ignorado (modelo fora do padrao)")

                processados += 1
                time.sleep(PAUSA_ENTRE_DISPOSITIVOS)

            except Exception as e:
                erros += 1
                print(f"  -> ERRO: {e}")
                time.sleep(PAUSA_ENTRE_DISPOSITIVOS)

    finally:
        scraper._fechar()

    if todos_dados:
        salvar_json(todos_dados, ARQUIVO_DADOS)
        print(f"\nResumo: {total} encontrados | {aceitos} aceitos | {ignorados} ignorados | {erros} erros")
    else:
        print("Nenhum dado aceito.")

    if progresso_callback:
        progresso_callback("fim", aceitos=aceitos, ignorados=ignorados, erros=erros)

    return {
        "total": total,
        "aceitos": aceitos,
        "ignorados": ignorados,
        "erros": erros
    }


if __name__ == "__main__":
    resultado = varrer_todos(headless=False)
    print(json.dumps(resultado, indent=2))
