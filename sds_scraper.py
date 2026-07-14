import json
import os
import re
import time
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

MODELOS_PERMITIDOS = [
    "LaserJet Managed MFP E52645dn",
    "Color LaserJet Managed MFP E877dn",
]

BASE_URL = "https://hp-sds-latam2.insightportal.net"


class SDSScraper:
    def __init__(self, usuario, senha, headless=False):
        self.usuario = usuario
        self.senha = senha
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/124.0.0.0 Safari/537.36"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        })
        self._logado = False

    def _fechar(self):
        self.session.close()

    def _csrf_token(self, html):
        sopa = BeautifulSoup(html, "html.parser")
        for name in ["_csrf", "csrf", "csrfToken"]:
            inp = sopa.find("input", {"name": name})
            if inp:
                return inp.get("value")
            meta = sopa.find("meta", {"name": name})
            if meta:
                return meta.get("content")
        return None

    def login(self):
        login_url = urljoin(BASE_URL, "/PortalWeb/login")
        r = self.session.get(login_url, timeout=30)
        r.raise_for_status()

        sopa = BeautifulSoup(r.text, "html.parser")
        form = sopa.find("form")
        action = form.get("action") if form else None
        post_url = urljoin(login_url, action) if action else login_url

        csrf = self._csrf_token(r.text)
        dados_form = {}
        if form:
            for inp in form.find_all("input"):
                name = inp.get("name")
                if name:
                    valor = inp.get("value", "")
                    if inp.get("type") == "text" or inp.get("id") == "usernameInput":
                        valor = self.usuario
                    elif inp.get("type") == "password" or inp.get("id") == "passwordInput":
                        valor = self.senha
                    dados_form[name] = valor
        if csrf and "_csrf" not in dados_form:
            dados_form["_csrf"] = csrf

        r2 = self.session.post(
            post_url,
            data=dados_form,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            allow_redirects=True,
            timeout=30,
        )
        r2.raise_for_status()

        if "login" in r2.url.lower():
            raise Exception("Falha no login - pagina de login retornada")

        self._logado = True
        print("[scraper] Login realizado (requests + BS4)")

    def _get(self, url, **kwargs):
        if not self._logado:
            raise Exception("Nao logado. Chame login() primeiro.")
        return self.session.get(url, timeout=kwargs.pop("timeout", 30), **kwargs)

    def _ajax(self, url):
        """Fetch a page with AJAX headers to get XML partial response"""
        return self.session.get(
            url,
            headers={"X-Requested-With": "XMLHttpRequest"},
            timeout=30,
        )

    def _parse_ekm(self, text):
        """Extract HTML content from EKM AJAX XML response"""
        try:
            sopa = BeautifulSoup(text, "xml")
            content = sopa.find("content")
            if content:
                return content.get_text()
        except Exception:
            pass
        # Fallback: try regex
        m = re.search(r"<content><!\[CDATA\[(.*?)\]\]></content>", text, re.DOTALL)
        if m:
            return m.group(1)
        return None

    def extrair_dispositivo(self, device_id):
        dados = {"id": device_id}

        url = f"{BASE_URL}/PortalWeb/devices/{device_id}"
        r = self._ajax(url)
        html = self._parse_ekm(r.text)
        if html:
            sopa = BeautifulSoup(html, "html.parser")
            span_modelo = sopa.select_one("span.entity-name.model")
            if span_modelo:
                dados["modelo"] = span_modelo.get_text(strip=True)
                modelo_ok = any(m in dados["modelo"] for m in MODELOS_PERMITIDOS)
                if not modelo_ok:
                    return None
                dados["breadcrumbs"] = []
                for crumb in sopa.select("#entity-breadcrumbs span.crumb"):
                    nivel = crumb.get("data-crumb-level")
                    nome_el = crumb.select_one("a, span.entity-name")
                    nome = nome_el.get_text(strip=True) if nome_el else ""
                    dados["breadcrumbs"].append({"nivel": nivel, "nome": nome})
                for tr in sopa.select("table.device-summary tbody tr"):
                    th = tr.find("th")
                    td = tr.find("td")
                    if th and td:
                        span_val = td.select_one("span.current-value")
                        dados[th.get_text(strip=True)] = (
                            span_val.get_text(strip=True) if span_val else td.get_text(strip=True)
                        )
                return dados

        return None

    def extrair_contagens_detalhadas(self, device_id):
        url = f"{BASE_URL}/PortalWeb/devices/{device_id}/counts"
        r = self._ajax(url)
        html = self._parse_ekm(r.text)
        if not html:
            return {}

        sopa = BeautifulSoup(html, "html.parser")
        dados = {}

        for t in sopa.find_all("table"):
            cls = " ".join(t.get("class", []))
            cap = t.find("caption")
            caption = cap.get_text(strip=True) if cap else ""

            if "current-count-summary" in cls:
                dados["contagens"] = {}
                for tr in t.find_all("tr"):
                    th = tr.find("th")
                    td = tr.find("td", class_="numerical")
                    if th and td:
                        dados["contagens"][th.get_text(strip=True)] = td.get_text(strip=True)

            elif "Resumo de uso" in caption or "usage" in cls.lower():
                dados["resumo_uso"] = {}
                rows = t.find_all("tr")
                for tr in rows:
                    cells = tr.find_all(["th", "td"])
                    if len(cells) == 4:
                        label = cells[0].get_text(strip=True)
                        if label and label not in ("", "Monocromático", "Colorido", "Total"):
                            dados["resumo_uso"][label] = {
                                "mono": cells[1].get_text(strip=True),
                                "color": cells[2].get_text(strip=True),
                                "total": cells[3].get_text(strip=True),
                            }

            elif "latest-counts" in cls:
                dados["contagens_detalhadas"] = []
                for tr in t.find_all("tr"):
                    tds = tr.find_all("td")
                    if len(tds) >= 5 and tds[0].get_text(strip=True):
                        dados["contagens_detalhadas"].append({
                            "classe": tds[0].get_text(strip=True),
                            "tipo": tds[1].get_text(strip=True),
                            "tamanho": tds[2].get_text(strip=True),
                            "contagem": tds[3].get_text(strip=True),
                            "data": tds[4].get_text(strip=True),
                        })

        return dados

    def extrair_consumiveis(self, device_id):
        url = f"{BASE_URL}/PortalWeb/devices/{device_id}/consumables"
        r = self._ajax(url)
        html = self._parse_ekm(r.text)
        if not html:
            return {"consumiveis": [], "historico_solicitacoes": []}

        sopa = BeautifulSoup(html, "html.parser")
        dados = {"consumiveis": [], "historico_solicitacoes": []}

        for t in sopa.find_all("table"):
            cls = " ".join(t.get("class", []))

            if "current-consumables-list" in cls:
                for tr in t.find_all("tr", class_="consumable-data"):
                    tds = tr.find_all("td")
                    if len(tds) >= 15:
                        # Level might be in span.level-percent or directly in cell text
                        nivel = ""
                        nivel_elem = tds[4].select_one("span.level-percent")
                        if nivel_elem:
                            nivel = nivel_elem.get_text(strip=True)
                        else:
                            nivel = tds[4].get_text(strip=True)
                        dados["consumiveis"].append({
                            "posicao": tds[0].get_text(strip=True),
                            "descricao": tds[1].get_text(strip=True),
                            "tipo": tds[2].get_text(strip=True),
                            "colorido": tds[3].get_text(strip=True),
                            "nivel": nivel,
                            "serial": tds[5].get_text(strip=True),
                            "sku_ajustada": tds[6].get_text(strip=True),
                            "rendimento": tds[7].get_text(strip=True),
                            "sku_pedido": tds[8].get_text(strip=True),
                            "dias_restantes": tds[9].get_text(strip=True),
                            "paginas_restantes": tds[10].get_text(strip=True),
                            "ultima_atualizacao": tds[11].get_text(strip=True),
                            "ciclos_mecanismo": tds[12].get_text(strip=True),
                            "solicitacao": tds[13].get_text(strip=True),
                        })

            elif "device-request-list" in cls:
                for tr in t.find_all("tr"):
                    tds = tr.find_all("td")
                    if len(tds) >= 14:
                        dados["historico_solicitacoes"].append({
                            "data": tds[0].get_text(strip=True),
                            "id_solicitacao": tds[1].get_text(strip=True),
                            "referencia": tds[2].get_text(strip=True),
                            "consumivel": tds[3].get_text(strip=True),
                            "serial": tds[4].get_text(strip=True),
                            "sku_ajustada": tds[5].get_text(strip=True),
                            "rendimento": tds[6].get_text(strip=True),
                            "motivo": tds[7].get_text(strip=True),
                            "nivel_solicitacao": tds[8].get_text(strip=True),
                            "dias_restantes": tds[9].get_text(strip=True),
                            "contagem_mono": tds[10].get_text(strip=True),
                            "contagem_color": tds[11].get_text(strip=True),
                            "status": tds[12].get_text(strip=True),
                            "substituido": tds[13].get_text(strip=True),
                        })

        return dados

    def extrair_alertas(self, device_id):
        url = f"{BASE_URL}/PortalWeb/devices/{device_id}/alerts"
        r = self._ajax(url)
        html = self._parse_ekm(r.text)
        if not html:
            return {"alertas_atuais": [], "frequencia_alertas": [], "alertas_anteriores": []}

        sopa = BeautifulSoup(html, "html.parser")
        dados = {"alertas_atuais": [], "frequencia_alertas": [], "alertas_anteriores": []}

        # Alert Class Counts - the table is inside a div with id alertClassCounts
        for div in sopa.find_all("div", id="alertClassCounts"):
            for t in div.find_all("table"):
                for tr in t.find_all("tr"):
                    th = tr.find("th")
                    td = tr.find("td")
                    if th and td and th.get_text(strip=True) and td.get_text(strip=True):
                        dados["frequencia_alertas"].append({
                            "classe": th.get_text(strip=True),
                            "contagem": td.get_text(strip=True),
                        })

        # Historical alerts
        for div in sopa.find_all("div", id="historicalAlertsList"):
            for t in div.find_all("table"):
                for tr in t.find_all("tr"):
                    tds = tr.find_all("td")
                    if len(tds) >= 9 and tds[0].get_text(strip=True):
                        dados["alertas_anteriores"].append({
                            "data": tds[0].get_text(strip=True),
                            "ciclos_mecanismo": tds[1].get_text(strip=True),
                            "classe": tds[2].get_text(strip=True),
                            "gravidade": tds[3].get_text(strip=True),
                            "treinamento": tds[4].get_text(strip=True),
                            "mib_code": tds[5].get_text(strip=True),
                            "motivo": tds[6].get_text(strip=True),
                            "limpo": tds[7].get_text(strip=True),
                            "duracao": tds[8].get_text(strip=True),
                        })

        # Also try fetching historical alerts
        try:
            from_ts = int(datetime.now().timestamp() * 1000) - 365 * 24 * 3600 * 1000
            hist_url = f"{BASE_URL}/PortalWeb/devices/{device_id}/alerts/historical?from={from_ts}"
            r2 = self._get(hist_url, timeout=15)
            sopa2 = BeautifulSoup(r2.text, "html.parser")
            for tr in sopa2.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) >= 9 and tds[0].get_text(strip=True):
                    dados["alertas_anteriores"].append({
                        "data": tds[0].get_text(strip=True),
                        "ciclos_mecanismo": tds[1].get_text(strip=True),
                        "classe": tds[2].get_text(strip=True),
                        "gravidade": tds[3].get_text(strip=True),
                        "treinamento": tds[4].get_text(strip=True),
                        "mib_code": tds[5].get_text(strip=True),
                        "motivo": tds[6].get_text(strip=True),
                        "limpo": tds[7].get_text(strip=True),
                        "duracao": tds[8].get_text(strip=True),
                    })
        except Exception:
            pass

        return dados

    def listar_todos_ids(self, url_dispositivos=None):
        if url_dispositivos is None:
            url_dispositivos = f"{BASE_URL}/PortalWeb/customers/2062/devices"

        try:
            r = self._get(url_dispositivos)
            sopa = BeautifulSoup(r.text, "html.parser")
        except Exception as e:
            print(f"Erro ao acessar listagem: {e}")
            return []

        ids = set()
        for a in sopa.select("a[href*='/devices/']"):
            href = a.get("href", "")
            match = re.search(r"/devices/(\d+)", href)
            if match:
                ids.add(match.group(1))

        return sorted(ids, key=int)

    def extrair_tudo(self, device_id):
        disp = self.extrair_dispositivo(device_id)
        if disp is None:
            return None
        return {
            "dispositivo": disp,
            "contagens": self.extrair_contagens_detalhadas(device_id),
            "consumiveis": self.extrair_consumiveis(device_id),
            "alertas": self.extrair_alertas(device_id),
            "extraido_em": datetime.now().isoformat(),
        }

    def buscar_por_serial(self, serial):
        url = f"{BASE_URL}/PortalWeb/search?q={serial}&s=devices"
        r = self._get(url)
        sopa = BeautifulSoup(r.text, "html.parser")

        for a in sopa.select("a[href*='/devices/']"):
            href = a.get("href", "")
            match = re.search(r"/devices/(\d+)", href)
            if match:
                return match.group(1)
        return None

    def processar_serial(self, serial):
        device_id = self.buscar_por_serial(serial)
        if device_id:
            return self.extrair_tudo(device_id)
        return None


def salvar_json(dados, caminho="dados_dispositivo.json"):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    print(f"Dados salvos em {caminho}")


def carregar_json(caminho="dados_dispositivo.json"):
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python sds_scraper.py <ID ou numero de serie>")
        sys.exit(1)

    serial = sys.argv[1].strip()
    scraper = SDSScraper("ardlopes@simpress.com.br", "Rodrigo2021.")
    try:
        scraper.login()
        if serial.isdigit():
            dados = scraper.extrair_tudo(serial)
        else:
            dados = scraper.processar_serial(serial)
        if dados:
            salvar_json(dados)
            print(json.dumps(dados, ensure_ascii=False, indent=2)[:500])
            print("...")
        else:
            print("Dispositivo nao encontrado.")
    finally:
        scraper._fechar()
