import os
import requests
from dotenv import load_dotenv

load_dotenv()


class WhatsAppSender:
    def __init__(self):
        self.token = os.getenv("WHATSAPP_TOKEN")
        self.phone_id = os.getenv("WHATSAPP_PHONE_ID")
        self.url = f"https://graph.facebook.com/v19.0/{self.phone_id}/messages"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def enviar_mensagem_texto(self, numero: str, texto: str):
        payload = {
            "messaging_product": "whatsapp",
            "to": numero,
            "type": "text",
            "text": {"body": texto}
        }
        response = requests.post(self.url, headers=self.headers, json=payload)
        print("====== RETORNO FACEBOOK (TEXTO) ======")
        print(response.text)
        return response.json()

    def enviar_mensagem_com_botoes(self, numero: str, texto: str, botoes: list[dict]):
        """
        Envia uma mensagem interativa com até 3 botões de resposta rápida.

        botoes: lista de dicts com chaves 'id' (até 256 chars) e 'titulo' (até 20 chars).
        Exemplo:
            [
                {"id": "quero_saber_mais", "titulo": "Quero saber mais"},
                {"id": "ver_planos",       "titulo": "Ver planos"},
                {"id": "agora_nao",        "titulo": "Agora não"},
            ]
        """
        if not botoes or len(botoes) > 3:
            raise ValueError("enviar_mensagem_com_botoes exige entre 1 e 3 botões.")

        buttons_payload = [
            {
                "type": "reply",
                "reply": {
                    "id": b["id"],
                    "title": b["titulo"][:20]
                }
            }
            for b in botoes
        ]

        payload = {
            "messaging_product": "whatsapp",
            "to": numero,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": texto},
                "action": {"buttons": buttons_payload}
            }
        }
        response = requests.post(self.url, headers=self.headers, json=payload)
        print("====== RETORNO FACEBOOK (BOTÕES) ======")
        print(response.text)
        return response.json()


def extrair_informacoes_mensagem(body: dict):
    """
    Extrai dados brutos do webhook da Meta Cloud API.
    Retorna: (telefone, texto, nome, message_id)

    Para mensagens de texto: texto é o conteúdo digitado.
    Para cliques em botões: texto é o ID do botão (ex: "quero_saber_mais").
    """
    try:
        entry = body.get('entry', [])[0]
        changes = entry.get('changes', [])[0]
        value = changes.get('value', {})
        messages = value.get('messages', [])

        if not messages:
            return None, None, None, None

        message = messages[0]
        numero_cliente = message.get('from')
        tipo = message.get('type')
        message_id = message.get('id')

        nome_cliente = ""
        contacts = value.get('contacts', [])
        if contacts:
            nome_cliente = contacts[0].get('profile', {}).get('name', '')

        if tipo == 'text':
            texto = message.get('text', {}).get('body')
            return numero_cliente, texto, nome_cliente, message_id

        if tipo == 'interactive':
            tipo_interativo = message.get('interactive', {}).get('type')
            if tipo_interativo == 'button_reply':
                botao_id = message.get('interactive', {}).get('button_reply', {}).get('id')
                return numero_cliente, botao_id, nome_cliente, message_id

        return numero_cliente, f"MÍDIA_{tipo}", nome_cliente, message_id

    except Exception:
        return None, None, None, None
