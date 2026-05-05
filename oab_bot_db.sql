CREATE DATABASE IF NOT EXISTS oab_bot_db;

USE oab_bot_db;

CREATE TABLE IF NOT EXISTS usuarios (
    telefone VARCHAR(20) PRIMARY KEY,
    nome_cliente VARCHAR(100),
    bot_ativo BOOLEAN DEFAULT TRUE,
    data_ultima_interacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS historico_conversas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    telefone_usuario VARCHAR(20),
    mensagem_cliente TEXT,
    resposta_bot TEXT,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (telefone_usuario) REFERENCES usuarios(telefone) ON DELETE CASCADE
);
