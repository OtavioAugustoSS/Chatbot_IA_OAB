import os
import re
import time
import threading
from fastapi import APIRouter, Request, Depends, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from db.database import get_db, SessionLocal
from db.models import Usuario, HistoricoConversa
from services.whatsapp import WhatsAppSender, extrair_informacoes_mensagem
from services.ai_service import AIService

MENSAGEM_BOAS_VINDAS = (
    "Olá! Seja bem-vindo(a) ao grupo! 👋\n"
    "Sou um assistente virtual especializado em preparação para a OAB.\n\n"
    "Me conta: você está estudando para a OAB agora ou já é formado(a)?"
)

# Botões exibidos junto com a apresentação da oferta
BOTOES_OFERTA = [
    {"id": "quero_conhecer", "titulo": "Quero conhecer"},
    {"id": "como_funciona",  "titulo": "Como funciona?"},
    {"id": "agora_nao",      "titulo": "Agora não"},
]

router = APIRouter()
whatsapp = WhatsAppSender()
ai_service = AIService()

# Garante processamento sequencial por usuário para evitar respostas fora de ordem.
_locks_por_telefone: dict[str, threading.Lock] = {}
_meta_lock = threading.Lock()

# Dedupe de message_id: a Meta retransmite o webhook quando não recebe ACK rápido.
_mensagens_processadas: dict[str, float] = {}
_dedupe_lock = threading.Lock()
_DEDUPE_TTL_SEGUNDOS = 600

def _ja_processada(message_id: str) -> bool:
    agora = time.time()
    with _dedupe_lock:
        expirados = [mid for mid, ts in _mensagens_processadas.items() if agora - ts > _DEDUPE_TTL_SEGUNDOS]
        for mid in expirados:
            del _mensagens_processadas[mid]
        if message_id in _mensagens_processadas:
            return True
        _mensagens_processadas[message_id] = agora
        return False

def _lock_do_telefone(telefone: str) -> threading.Lock:
    with _meta_lock:
        if telefone not in _locks_por_telefone:
            _locks_por_telefone[telefone] = threading.Lock()
        return _locks_por_telefone[telefone]

VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "oab_bot_token")


@router.get("/webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return PlainTextResponse(challenge)

    raise HTTPException(status_code=403, detail="Token inválido")


def tarefa_em_segundo_plano_ia(telefone: str, texto_cliente: str):
    with _lock_do_telefone(telefone):
        _processar_mensagem(telefone, texto_cliente)


def _processar_mensagem(telefone: str, texto_cliente: str):
    db = SessionLocal()
    try:
        user = db.query(Usuario).filter(Usuario.telefone == telefone).first()
        if not user or not user.bot_ativo:
            return

        historico = (
            db.query(HistoricoConversa)
            .filter(HistoricoConversa.telefone_usuario == telefone)
            .order_by(HistoricoConversa.criado_em.desc())
            .limit(10)
            .all()
        )
        historico.reverse()

        contexto_mensagens = []
        for h in historico:
            if h.mensagem_cliente:
                contexto_mensagens.append({"role": "user", "content": h.mensagem_cliente})
            if h.resposta_bot:
                contexto_mensagens.append({"role": "model", "content": h.resposta_bot.replace("<br>", "\n")})

        # Primeiro contato: entrega a boas-vindas diretamente, sem passar pela IA.
        if not historico:
            _salvar_historico(db, telefone, texto_cliente, MENSAGEM_BOAS_VINDAS.replace("\n", "<br>"))
            whatsapp.enviar_mensagem_texto(telefone, MENSAGEM_BOAS_VINDAS)
            return

        resultado_ia = ai_service.processar_intencao(contexto_mensagens, texto_cliente, user.nome_cliente)
        intencao = resultado_ia.get("intencao", "continuar_conversa")
        resposta_bruta = resultado_ia.get("resposta_sugerida", "Como posso ajudar?")

        _salvar_historico(db, telefone, texto_cliente, resposta_bruta)
        _podar_historico(db, telefone, limite=30)

        resposta_texto = _normalizar_quebras(resposta_bruta)
        print(f"[DEBUG ENVIO] intencao={intencao} | {len(resposta_texto)} chars: {repr(resposta_texto[:100])}")

        if intencao == "encerrar_conversa":
            user.bot_ativo = False
            db.commit()
            whatsapp.enviar_mensagem_texto(telefone, resposta_texto)
            return

        if intencao == "apresentar_oferta":
            try:
                whatsapp.enviar_mensagem_com_botoes(telefone, resposta_texto, BOTOES_OFERTA)
            except Exception:
                # Fallback para texto simples se botões falharem
                whatsapp.enviar_mensagem_texto(telefone, resposta_texto)
            return

        whatsapp.enviar_mensagem_texto(telefone, resposta_texto)

    finally:
        db.close()


def _salvar_historico(db, telefone: str, mensagem_cliente: str, resposta_bot: str):
    db.add(HistoricoConversa(
        telefone_usuario=telefone,
        mensagem_cliente=mensagem_cliente,
        resposta_bot=resposta_bot
    ))
    db.commit()


def _podar_historico(db, telefone: str, limite: int):
    contagem = db.query(HistoricoConversa).filter(
        HistoricoConversa.telefone_usuario == telefone
    ).count()
    if contagem > limite:
        ids_manter = [
            row.id for row in
            db.query(HistoricoConversa.id)
            .filter(HistoricoConversa.telefone_usuario == telefone)
            .order_by(HistoricoConversa.criado_em.desc())
            .limit(limite)
            .all()
        ]
        db.query(HistoricoConversa).filter(
            HistoricoConversa.telefone_usuario == telefone,
            ~HistoricoConversa.id.in_(ids_manter)
        ).delete(synchronize_session=False)
        db.commit()


def _normalizar_quebras(texto: str) -> str:
    texto = re.sub(r"<\s*br\s*/?\s*>", "\n", texto, flags=re.IGNORECASE)
    texto = texto.replace("\\n", "\n")
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


@router.post("/webhook")
async def receive_message(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    body = await request.json()
    telefone, texto_cliente, nome_cliente, message_id = extrair_informacoes_mensagem(body)

    if not telefone or not texto_cliente:
        return {"status": "ok"}

    if message_id and _ja_processada(message_id):
        print(f"⏭️  [DEDUPE] message_id {message_id} já processado, ignorando retry da Meta.")
        return {"status": "ok"}

    if str(texto_cliente).startswith("MÍDIA_"):
        background_tasks.add_task(
            whatsapp.enviar_mensagem_texto,
            telefone,
            "Ainda não consigo processar áudios ou imagens. Pode me enviar uma mensagem de texto? 😊"
        )
        return {"status": "ok"}

    user = db.query(Usuario).filter(Usuario.telefone == telefone).first()
    if not user:
        user = Usuario(telefone=telefone, nome_cliente=nome_cliente, bot_ativo=True)
        db.add(user)
        db.commit()
        db.refresh(user)
    elif nome_cliente and user.nome_cliente != nome_cliente:
        user.nome_cliente = nome_cliente
        db.commit()

    # Comando de desenvolvedor: reinicia o bot e limpa histórico
    if str(texto_cliente).strip().lower() == "!reiniciar":
        user.bot_ativo = True
        db.query(HistoricoConversa).filter(HistoricoConversa.telefone_usuario == telefone).delete()
        db.commit()
        whatsapp.enviar_mensagem_texto(telefone, "Bot reiniciado! Memória limpa. Como posso ajudar?")
        return {"status": "ok"}

    if not user.bot_ativo:
        print(f"🔒 [MSG IGNORADA] Bot inativo para {telefone}.")
        return {"status": "ok"}

    # Botão "agora não" já responde sem chamar a IA
    if texto_cliente == "agora_nao":
        whatsapp.enviar_mensagem_texto(
            telefone,
            "Tudo bem! Se mudar de ideia, é só me chamar. Bons estudos! 🎓"
        )
        user.bot_ativo = False
        db.commit()
        return {"status": "ok"}

    print(f"-> Enviando para IA em 2º plano. [{telefone}]: '{texto_cliente}'")
    background_tasks.add_task(tarefa_em_segundo_plano_ia, telefone, texto_cliente)

    return {"status": "ok"}
