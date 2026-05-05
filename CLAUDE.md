# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WhatsApp chatbot for OAB exam preparation. When someone joins a WhatsApp group, the bot engages them in a consultative conversation to understand their situation, deliver value (tips, info), and invite them to subscribe to a SaaS preparation platform. The bot is 100% automated — no human handoff exists.

Built on FastAPI + MySQL, uses the NVIDIA NIM API (Llama 3.1 70B via OpenAI-compatible client) and the Meta WhatsApp Cloud API.

## Commands

```bash
pip install -r requirements.txt
python main.py
ngrok http 8000
```

No test suite — testing is done manually via WhatsApp with a live webhook.

## Architecture

```
main.py               → FastAPI app init, DB table creation, Uvicorn launch
api/webhook.py        → GET /webhook (verification) + POST /webhook (message handling)
services/
  ai_service.py       → NVIDIA NIM Llama 3.1 70B call, returns JSON {intencao, resposta_sugerida}
  whatsapp.py         → Meta Cloud API v19.0: send text, send interactive buttons, parse incoming
db/
  models.py           → SQLAlchemy models: Usuario, HistoricoConversa
  database.py         → MySQL connection via pymysql, session dependency injection
core/
  prompts.py          → SYSTEM_PROMPT_OAB: conversation rules and sales flow
```

## Message Flow

1. Meta sends POST to `/webhook` → returns 200 OK immediately
2. Actual processing runs in a **FastAPI background task** (required by Meta's 15s timeout)
3. Per-user threading lock prevents out-of-order processing of rapid messages
4. Deduplication cache prevents Meta webhook retries from generating duplicate replies
5. First message from a user → deliver welcome text directly (no AI call)
6. Subsequent messages → last 10 turns fetched, passed to AI with system prompt
7. AI returns `{intencao, resposta_sugerida}`:
   - `continuar_conversa` → send plain text reply
   - `apresentar_oferta` → send text + 3 quick-reply buttons (Quero conhecer / Como funciona? / Agora não)
   - `encerrar_conversa` → send text, set `bot_ativo = False` (user not interested)
8. Button click `agora_nao` is handled directly in the webhook without calling the AI
9. `!reiniciar` command (dev use) resets `bot_ativo=True` and clears history

## AI Response Contract

```json
{"intencao": "continuar_conversa|apresentar_oferta|encerrar_conversa", "resposta_sugerida": "..."}
```

Any JSON parse failure or API error falls back to `continuar_conversa` with a short apology — the bot never goes silent due to an error.

## WhatsApp Button Sending

`whatsapp.enviar_mensagem_com_botoes(numero, texto, botoes)` sends interactive reply buttons.
- Max 3 buttons per message, title max 20 chars
- Incoming button clicks arrive as the button `id` string in `texto_cliente`
- Button IDs handled by the webhook: `"agora_nao"` is intercepted before reaching the AI

## Environment Variables

| Variable | Purpose |
|---|---|
| `DB_USER`, `DB_PASS`, `DB_HOST`, `DB_NAME` | MySQL connection (default DB: `oab_bot_db`) |
| `WHATSAPP_TOKEN` | Meta access token |
| `WHATSAPP_PHONE_ID` | WhatsApp Business phone number ID |
| `WEBHOOK_VERIFY_TOKEN` | Token for Meta webhook verification handshake |
| `NVIDIA_API_KEY` | NVIDIA NIM API key for Llama 3.1 70B |

## Database

Schema in `oab_bot_db.sql`. SQLAlchemy creates tables on startup via `Base.metadata.create_all()`.
Only two tables: `usuarios` and `historico_conversas`.

## Pending / To Configure

- Fill in the `[PREENCHA AQUI]` section in `core/prompts.py` with platform name, price, link, trial, differentials.
- Decide final database (currently MySQL).
- Implement WhatsApp group-join event listener if the bot should proactively DM new group members (currently only responds to incoming messages).
- Customize `BOTOES_OFERTA` in `api/webhook.py` with the real button labels and IDs for the subscription flow.
