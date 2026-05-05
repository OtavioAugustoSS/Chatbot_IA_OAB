# Chatbot IA - Preparação OAB

Assistente virtual de WhatsApp para engajar advogados e bacharéis em Direito, conduzindo conversas consultivas e convidando-os a assinar uma plataforma SaaS de preparação para o Exame da OAB.

Construído em **Python (FastAPI)** com **MySQL** e conectado à **Meta Cloud API (WhatsApp)** e à **NVIDIA NIM API (Llama 3.1 70B)**.

---

## Pré-requisitos

### 1. Conta Meta for Developers (WhatsApp)
- Anote o **Número de Identificação do Telefone** (`WHATSAPP_PHONE_ID`).
- Gere um **Token de Acesso** (`WHATSAPP_TOKEN`).
- Configure o Webhook apontando para a URL pública do servidor.

### 2. NVIDIA NIM API
- Gere sua chave em [build.nvidia.com](https://build.nvidia.com).
- Salve como `NVIDIA_API_KEY`.

### 3. Banco de Dados MySQL
- Rode o script `oab_bot_db.sql` para criar o banco e as tabelas.

---

## Configuração

Crie um arquivo `.env` na raiz do projeto:

```env
DB_USER=root
DB_PASS=sua_senha
DB_HOST=localhost
DB_NAME=oab_bot_db

WHATSAPP_PHONE_ID=seu_phone_id
WHATSAPP_TOKEN=seu_token
WEBHOOK_VERIFY_TOKEN=oab_bot_token

NVIDIA_API_KEY=sua_chave_nvidia
```

---

## Rodando localmente

```bash
# Instalar dependências
pip install -r requirements.txt

# Subir o servidor
python main.py

# Expor via ngrok para o webhook da Meta
ngrok http 8000
```

Configure o webhook na Meta:
- **URL de callback:** `https://xxxx.ngrok-free.app/webhook`
- **Verify token:** valor do seu `WEBHOOK_VERIFY_TOKEN`
- **Inscrever-se em:** `messages`

---

## Comandos internos

- `!reiniciar` — reativa o bot e limpa o histórico de conversa de um usuário (útil para testes).
