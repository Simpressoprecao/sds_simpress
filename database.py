import os
import json
from datetime import datetime

try:
    import pymysql
    import pymysql.cursors
    TEM_PYMYSQL = True
except ImportError:
    pymysql = None
    TEM_PYMYSQL = False

ARQUIVO_CONFIG_DB = "config_db.json"

CONFIG_PADRAO = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "",
    "database": "sds_simpress"
}


def carregar_config_db():
    if os.path.exists(ARQUIVO_CONFIG_DB):
        with open(ARQUIVO_CONFIG_DB, "r", encoding="utf-8") as f:
            return json.load(f)
    return dict(CONFIG_PADRAO)


def salvar_config_db(config):
    with open(ARQUIVO_CONFIG_DB, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


class Database:
    def __init__(self, config=None):
        self.config = config or carregar_config_db()
        self.conexao = None

    def conectar(self):
        if not TEM_PYMYSQL:
            raise ImportError("pymysql nao instalado. Execute: pip install pymysql")
        self.conexao = pymysql.connect(
            host=self.config["host"],
            port=self.config.get("port", 3306),
            user=self.config["user"],
            password=self.config["password"],
            database=self.config["database"],
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor
        )
        return self.conexao

    def fechar(self):
        if self.conexao:
            self.conexao.close()
            self.conexao = None

    def criar_tabelas(self):
        con = self.conectar()
        with con.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS dispositivos (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    id_sds VARCHAR(20) NOT NULL UNIQUE,
                    serial VARCHAR(50) NOT NULL,
                    modelo VARCHAR(200),
                    cliente VARCHAR(200),
                    contrato VARCHAR(200),
                    zona VARCHAR(200),
                    localizacao VARCHAR(200),
                    ip VARCHAR(50),
                    hostname VARCHAR(100),
                    mac VARCHAR(50),
                    firmware VARCHAR(100),
                    sku VARCHAR(50),
                    status_monitor VARCHAR(100),
                    contador_pb VARCHAR(20),
                    contador_color VARCHAR(20),
                    ultima_atualizacao VARCHAR(50),
                    data_extracao DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    dados_json JSON,
                    INDEX idx_serial (serial),
                    INDEX idx_id_sds (id_sds)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS contagens (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    dispositivo_id INT NOT NULL,
                    chave VARCHAR(100),
                    valor VARCHAR(50),
                    data_leitura VARCHAR(50),
                    FOREIGN KEY (dispositivo_id) REFERENCES dispositivos(id) ON DELETE CASCADE,
                    INDEX idx_dispositivo (dispositivo_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS consumiveis (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    dispositivo_id INT NOT NULL,
                    posicao VARCHAR(20),
                    descricao VARCHAR(200),
                    tipo VARCHAR(50),
                    nivel VARCHAR(20),
                    serial_consumivel VARCHAR(100),
                    rendimento VARCHAR(50),
                    paginas_restantes VARCHAR(50),
                    FOREIGN KEY (dispositivo_id) REFERENCES dispositivos(id) ON DELETE CASCADE,
                    INDEX idx_dispositivo (dispositivo_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS alertas (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    dispositivo_id INT NOT NULL,
                    data VARCHAR(50),
                    classe VARCHAR(100),
                    gravidade VARCHAR(50),
                    motivo TEXT,
                    duracao VARCHAR(50),
                    FOREIGN KEY (dispositivo_id) REFERENCES dispositivos(id) ON DELETE CASCADE,
                    INDEX idx_dispositivo (dispositivo_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS os_chamados (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    numero_os VARCHAR(20) NOT NULL UNIQUE,
                    serial VARCHAR(50),
                    modelo VARCHAR(100),
                    cep VARCHAR(20),
                    localidade VARCHAR(200),
                    abertura VARCHAR(50),
                    previsao VARCHAR(50),
                    finalizado VARCHAR(50),
                    descricao TEXT,
                    observacao TEXT,
                    status VARCHAR(50),
                    ocorrencia TEXT,
                    data_importacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_serial (serial),
                    INDEX idx_status (status),
                    INDEX idx_modelo (modelo)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS troca_antecipada (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    loja VARCHAR(200),
                    cep VARCHAR(20),
                    uf VARCHAR(10),
                    modelo VARCHAR(100),
                    serial VARCHAR(50) NOT NULL,
                    data_leitura VARCHAR(50),
                    percentual_toner VARCHAR(20),
                    cor_toner VARCHAR(30),
                    ip VARCHAR(50),
                    data_atendimento VARCHAR(50),
                    descricao TEXT,
                    status VARCHAR(50),
                    data_finalizacao VARCHAR(50),
                    email VARCHAR(100),
                    contato TEXT,
                    retorno_acao TEXT,
                    retorno TEXT,
                    col18 VARCHAR(100),
                    data_importacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_serial (serial),
                    INDEX idx_status (status),
                    INDEX idx_modelo (modelo),
                    INDEX idx_uf (uf)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        con.commit()

    def salvar_dispositivo(self, dados):
        disp = dados.get("dispositivo", {})
        contagens_raw = dados.get("contagens", {})
        contagens = (contagens_raw.get("contagens", {})
                     if isinstance(contagens_raw, dict) else {})
        if not contagens:
            contagens = disp.get("contagens", {})
        id_sds = disp.get("id", "")
        serial = disp.get("N\u00famero de s\u00e9rie", "")
        modelo = disp.get("modelo", "")
        cliente = ""
        contrato = ""
        for crumb in disp.get("breadcrumbs", []):
            if crumb.get("nivel") == "customers":
                cliente = crumb.get("nome", "")
            elif crumb.get("nivel") == "contracts":
                contrato = crumb.get("nome", "")

        contador_pb = contagens.get("P\u00e1ginas monocrom\u00e1ticas",
                       contagens.get("Monocrom\u00e1tico (equivalente A4)", ""))
        contador_color = contagens.get("Colorido (equivalente A4)", "")

        con = self.conectar()
        with con.cursor() as cur:
            dados_json = json.dumps(dados, ensure_ascii=False)
            sql = """
                INSERT INTO dispositivos
                    (id_sds, serial, modelo, cliente, contrato, zona, localizacao,
                     ip, hostname, mac, firmware, sku, status_monitor,
                     contador_pb, contador_color, ultima_atualizacao, dados_json)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                    modelo=VALUES(modelo), cliente=VALUES(cliente),
                    contrato=VALUES(contrato), zona=VALUES(zona),
                    localizacao=VALUES(localizacao), ip=VALUES(ip),
                    hostname=VALUES(hostname), mac=VALUES(mac),
                    firmware=VALUES(firmware), sku=VALUES(sku),
                    status_monitor=VALUES(status_monitor),
                    contador_pb=VALUES(contador_pb),
                    contador_color=VALUES(contador_color),
                    ultima_atualizacao=VALUES(ultima_atualizacao),
                    dados_json=VALUES(dados_json),
                    data_extracao=CURRENT_TIMESTAMP
            """
            cur.execute(sql, (
                id_sds, serial, modelo, cliente, contrato,
                disp.get("Zona", ""), disp.get("Localiza\u00e7\u00e3o", ""),
                disp.get("Endere\u00e7o IP", ""), disp.get("Nome do host", ""),
                disp.get("Endere\u00e7o MAC", ""), disp.get("Firmware", ""),
                disp.get("SKU", ""), disp.get("Status do monitor", ""),
                contador_pb, contador_color,
                disp.get("\u00daltima atualiza\u00e7\u00e3o", "")
            ))

            disp_id = cur.lastrowid
            if not disp_id:
                cur.execute("SELECT id FROM dispositivos WHERE id_sds = %s", (id_sds,))
                row = cur.fetchone()
                disp_id = row["id"] if row else None

            if disp_id:
                cur.execute("DELETE FROM contagens WHERE dispositivo_id = %s", (disp_id,))
                cur.execute("DELETE FROM consumiveis WHERE dispositivo_id = %s", (disp_id,))
                cur.execute("DELETE FROM alertas WHERE dispositivo_id = %s", (disp_id,))

                c_contagens = dados.get("contagens", {})
                if isinstance(c_contagens, dict):
                    for chave, valor in c_contagens.items():
                        if isinstance(valor, dict):
                            continue
                        cur.execute(
                            "INSERT INTO contagens (dispositivo_id, chave, valor) VALUES (%s,%s,%s)",
                            (disp_id, chave, str(valor))
                        )

                consumiveis = dados.get("consumiveis", {})
                for cons in consumiveis.get("consumiveis", []):
                    cur.execute(
                        """INSERT INTO consumiveis
                           (dispositivo_id, posicao, descricao, tipo, nivel,
                            serial_consumivel, rendimento, paginas_restantes)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (disp_id, cons.get("posicao", ""), cons.get("descricao", ""),
                         cons.get("tipo", ""), cons.get("nivel", ""),
                         cons.get("serial", ""), cons.get("rendimento", ""),
                         cons.get("paginas_restantes", ""))
                    )

                alertas = dados.get("alertas", {})
                for al in alertas.get("alertas_anteriores", []):
                    cur.execute(
                        """INSERT INTO alertas
                           (dispositivo_id, data, classe, gravidade, motivo, duracao)
                           VALUES (%s,%s,%s,%s,%s,%s)""",
                        (disp_id, al.get("data", ""), al.get("classe", ""),
                         al.get("gravidade", ""), al.get("motivo", ""),
                         al.get("duracao", ""))
                    )

        con.commit()
        return disp_id

    def listar_dispositivos(self):
        con = self.conectar()
        with con.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("""
                SELECT d.id, d.id_sds, d.serial, d.modelo, d.cliente, d.zona,
                       d.localizacao, d.ip, d.hostname, d.mac, d.firmware,
                       d.sku, d.contador_pb, d.contador_color,
                       d.ultima_atualizacao, d.data_extracao,
                       d.dados_json,
                       COALESCE(a.total_alertas, 0) AS total_alertas
                FROM dispositivos d
                LEFT JOIN (
                    SELECT dispositivo_id, COUNT(*) AS total_alertas
                    FROM alertas
                    GROUP BY dispositivo_id
                ) a ON a.dispositivo_id = d.id
                ORDER BY d.cliente, d.serial
            """)
            rows = cur.fetchall()
            resultado = []
            for row in rows:
                contagens = {}
                pb_val = row.get("contador_pb", "")
                color_val = row.get("contador_color", "")
                if row.get("dados_json"):
                    try:
                        parsed = json.loads(row["dados_json"])
                        item_contagens = parsed.get("contagens", {}).get("contagens", {})
                        if isinstance(item_contagens, dict):
                            contagens = item_contagens
                        if not pb_val:
                            pb_val = contagens.get("P\u00e1ginas monocrom\u00e1ticas",
                                     contagens.get("Monocrom\u00e1tico (equivalente A4)", ""))
                        if not color_val:
                            color_val = contagens.get("Colorido (equivalente A4)", "")
                    except (json.JSONDecodeError, TypeError):
                        pass
                disp = {
                    "N\u00famero de s\u00e9rie": row.get("serial", ""),
                    "modelo": row.get("modelo", ""),
                    "Endere\u00e7o IP": row.get("ip", ""),
                    "Localiza\u00e7\u00e3o": row.get("localizacao", ""),
                    "Zona": row.get("zona", ""),
                    "hostname": row.get("hostname", ""),
                    "\u00daltima atualiza\u00e7\u00e3o": str(row.get("ultima_atualizacao", "")),
                    "cliente": row.get("cliente", ""),
                    "Endere\u00e7o MAC": row.get("mac", ""),
                    "Firmware": row.get("firmware", ""),
                    "Vers\u00e3o do firmware": row.get("firmware", ""),
                    "SKU": row.get("sku", ""),
                    "breadcrumbs": [{"nome": row.get("cliente", ""), "nivel": "customers"}],
                    "contagens": contagens,
                }
                item = {
                    "dispositivo": disp,
                    "contagens": contagens,
                    "total_alertas": row.get("total_alertas", 0),
                    "serial": row.get("serial", ""),
                    "modelo": row.get("modelo", ""),
                    "cliente": row.get("cliente", ""),
                    "contador_pb": pb_val,
                    "contador_color": color_val,
                    "ultima_atualizacao": str(row.get("ultima_atualizacao", "")),
                }
                if row.get("dados_json"):
                    try:
                        parsed = json.loads(row["dados_json"])
                        item["consumiveis"] = parsed.get("consumiveis", {})
                        item["alertas"] = parsed.get("alertas", {})
                    except (json.JSONDecodeError, TypeError):
                        item["consumiveis"] = {}
                        item["alertas"] = {}
                else:
                    item["consumiveis"] = {}
                    item["alertas"] = {}
                resultado.append(item)
            return resultado

    def buscar_dispositivo(self, termo):
        con = self.conectar()
        with con.cursor() as cur:
            cur.execute("""
                SELECT id, id_sds, serial, modelo, cliente, zona, localizacao,
                       ip, hostname, mac, firmware, sku, status_monitor,
                       contador_pb, contador_color, ultima_atualizacao,
                       data_extracao
                FROM dispositivos
                WHERE serial = %s OR id_sds = %s
                LIMIT 1
            """, (termo, termo))
            return cur.fetchone()

    def obter_dados_completos(self, disp_id):
        con = self.conectar()
        with con.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT * FROM dispositivos WHERE id = %s", (disp_id,))
            disp = cur.fetchone()
            if not disp:
                return None

            cur.execute("SELECT * FROM contagens WHERE dispositivo_id = %s", (disp_id,))
            disp["contagens"] = cur.fetchall()

            cur.execute("SELECT * FROM consumiveis WHERE dispositivo_id = %s", (disp_id,))
            disp["consumiveis"] = cur.fetchall()

            cur.execute("SELECT * FROM alertas WHERE dispositivo_id = %s", (disp_id,))
            disp["alertas"] = cur.fetchall()

            return disp

    def obter_dados_para_excel(self):
        con = self.conectar()
        with con.cursor() as cur:
            cur.execute("""
                SELECT serial, contador_pb, contador_color, ultima_atualizacao
                FROM dispositivos
                ORDER BY serial
            """)
            return cur.fetchall()


def criar_schema_sql(caminho="schema.sql"):
    sql = """-- SDS Simpress - Schema MySQL
-- Execute este script no phpMyAdmin / cPanel para criar o banco

CREATE DATABASE IF NOT EXISTS sds_simpress
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE sds_simpress;

CREATE TABLE IF NOT EXISTS dispositivos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_sds VARCHAR(20) NOT NULL UNIQUE,
    serial VARCHAR(50) NOT NULL,
    modelo VARCHAR(200),
    cliente VARCHAR(200),
    contrato VARCHAR(200),
    zona VARCHAR(200),
    localizacao VARCHAR(200),
    ip VARCHAR(50),
    hostname VARCHAR(100),
    mac VARCHAR(50),
    firmware VARCHAR(100),
    sku VARCHAR(50),
    status_monitor VARCHAR(100),
    contador_pb VARCHAR(20),
    contador_color VARCHAR(20),
    ultima_atualizacao VARCHAR(50),
    data_extracao DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    dados_json JSON,
    INDEX idx_serial (serial),
    INDEX idx_id_sds (id_sds)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS contagens (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dispositivo_id INT NOT NULL,
    chave VARCHAR(100),
    valor VARCHAR(50),
    data_leitura VARCHAR(50),
    FOREIGN KEY (dispositivo_id) REFERENCES dispositivos(id) ON DELETE CASCADE,
    INDEX idx_dispositivo (dispositivo_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS consumiveis (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dispositivo_id INT NOT NULL,
    posicao VARCHAR(20),
    descricao VARCHAR(200),
    tipo VARCHAR(50),
    nivel VARCHAR(20),
    serial_consumivel VARCHAR(100),
    rendimento VARCHAR(50),
    paginas_restantes VARCHAR(50),
    FOREIGN KEY (dispositivo_id) REFERENCES dispositivos(id) ON DELETE CASCADE,
    INDEX idx_dispositivo (dispositivo_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS alertas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dispositivo_id INT NOT NULL,
    data VARCHAR(50),
    classe VARCHAR(100),
    gravidade VARCHAR(50),
    motivo TEXT,
    duracao VARCHAR(50),
    FOREIGN KEY (dispositivo_id) REFERENCES dispositivos(id) ON DELETE CASCADE,
    INDEX idx_dispositivo (dispositivo_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(sql)
    print(f"Schema salvo em {caminho}")


if __name__ == "__main__":
    criar_schema_sql()
    print("Arquivo schema.sql criado. Execute no phpMyAdmin do cPanel.")
