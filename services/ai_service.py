import os
import json
from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
from core.prompts import SYSTEM_PROMPT_OAB

class AIService:
    def __init__(self):
        self.client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=os.getenv("NVIDIA_API_KEY")
        )
        self.model_name = "meta/llama-3.1-70b-instruct"

    def processar_intencao(self, historico_mensagens, mensagem_atual, nome_cliente=None):
        try:
            messages_payload = [{"role": "system", "content": SYSTEM_PROMPT_OAB}]

            if nome_cliente:
                messages_payload.append({
                    "role": "system",
                    "content": f"O usuário atual se chama '{nome_cliente}'. Use o nome para personalizar o atendimento quando apropriado."
                })

            for msg in historico_mensagens:
                role = "assistant" if msg.get("role") in ["bot", "model", "assistant"] else "user"
                messages_payload.append({"role": role, "content": msg.get("content", "")})

            messages_payload.append({"role": "user", "content": mensagem_atual})

            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages_payload,
                temperature=0.4,
                max_tokens=2048,
                response_format={"type": "json_object"}
            )

            response_text = completion.choices[0].message.content.strip()
            print(f"[DEBUG IA RAW] {repr(response_text[:300])}")

            if response_text.startswith("```json"):
                response_text = response_text[7:]
            elif response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            dados = json.loads(response_text)

            if "intencao" not in dados and "choices" in dados:
                inner = dados["choices"][0]["message"]["content"]
                dados = json.loads(inner) if isinstance(inner, str) else inner

            return {
                "intencao": dados.get("intencao", "continuar_conversa"),
                "resposta_sugerida": dados.get("resposta_sugerida", "Desculpe, tive um problema ao processar. Como posso ajudar?")
            }

        except json.JSONDecodeError as e:
            print(f"[ERRO JSON NVIDIA] Falha ao processar saida da IA: {e}")
            _gravar_erro(f"[ERRO JSON] {e}\nTexto recebido: {response_text if 'response_text' in dir() else 'N/A'}")
            return {
                "intencao": "continuar_conversa",
                "resposta_sugerida": "Desculpe, tive um probleminha aqui. Pode repetir sua mensagem?"
            }
        except Exception as e:
            print(f"[ERRO AI SERVICE NVIDIA] {e}")
            _gravar_erro(f"[ERRO AI SERVICE NVIDIA] {e}")
            return {
                "intencao": "continuar_conversa",
                "resposta_sugerida": "Tive um erro de comunicação. Pode tentar novamente em instantes?"
            }


def _gravar_erro(mensagem: str):
    log_path = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "erro_ia_debug.txt")
    )
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(mensagem)
