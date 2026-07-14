-- SDS Simpress - Schema MySQL
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
