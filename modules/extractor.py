import json
import logging
import os
import re
import httpx
from typing import Any

logger = logging.getLogger("impcon.extractor")

MAX_CHARS = 10000
OLLAMA_HOST = os.environ.get("IMPCON_OLLAMA_URL", "http://localhost:11434")

PROMPT = """Você é especialista em análise jurídica. Analise o contrato abaixo e extraia todas as informações relevantes.

RETORNE SOMENTE UM JSON VÁLIDO. Sem texto adicional, sem markdown, sem ```json. Apenas o JSON puro.

Estrutura obrigatória (use listas vazias [] se não houver dados):
{{
  "resumo": "resumo executivo em 2-3 frases",
  "tipo_contrato": "ex: Prestação de Serviços / Compra e Venda / Locação / Parceria / etc",
  "partes": [
    {{"nome": "nome completo", "tipo": "Contratante ou Contratado ou Fiador ou Testemunha", "papel": "descrição do papel"}}
  ],
  "datas": [
    {{"descricao": "o que esta data representa", "data": "DD/MM/YYYY ou null", "tipo": "inicio ou fim ou pagamento ou entrega ou vencimento"}}
  ],
  "valores": [
    {{"descricao": "descrição", "valor": "R$ X,XX ou texto descritivo", "periodicidade": "mensal ou anual ou unico ou null"}}
  ],
  "obrigacoes": [
    {{"parte": "nome de quem deve cumprir", "descricao": "o que deve ser feito", "prazo": "prazo ou null"}}
  ],
  "penalidades": [
    {{"condicao": "quando se aplica", "penalidade": "qual é a penalidade"}}
  ],
  "clausulas_principais": [
    {{"numero": "número ou vazio", "titulo": "título da cláusula", "resumo": "resumo em 1-2 frases"}}
  ]
}}

CONTRATO:
{text}"""

EMPTY_RESULT: dict[str, Any] = {
    "resumo": "",
    "tipo_contrato": "",
    "partes": [],
    "datas": [],
    "valores": [],
    "obrigacoes": [],
    "penalidades": [],
    "clausulas_principais": [],
}


async def extract_contract_data(text: str, model: str) -> dict[str, Any]:
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n\n[...documento truncado para análise...]"

    prompt = PROMPT.format(text=text)
    url = f"{OLLAMA_HOST}/api/generate"

    logger.info(f"Enviando requisição de extração para Ollama em {url} com modelo '{model}'...")

    try:
        # Timeout estendido (600s = 10 min) para permitir processamento em CPUs sem GPU sem estourar ReadTimeout
        async with httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=10.0)) as client:
            resp = await client.post(
                url,
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.05, "num_predict": 2048},
                },
            )
            if resp.status_code != 200:
                logger.error(f"Erro na resposta do Ollama (HTTP {resp.status_code}): {resp.text}")
            resp.raise_for_status()

            data = resp.json()
            raw = data.get("response", "").strip()
            logger.info("Resposta recebida com sucesso do Ollama.")
            return _parse(raw)
    except Exception as e:
        logger.exception(f"Falha na comunicação com Ollama em {url}: {e}")
        raise


def _parse(raw: str) -> dict[str, Any]:
    if not raw:
        logger.warning("Resposta bruta do modelo veio vazia.")
        return dict(EMPTY_RESULT)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Resposta não veio como JSON direto, tentando extrair objeto JSON com regex...")

    match = re.search(r"\{[\s\S]*\}", raw)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError as err:
            logger.error(f"Falha ao decodificar JSON extraído por regex: {err}")

    logger.error(f"Não foi possível interpretar a resposta da IA. Conteúdo bruto: {raw[:200]}...")
    return dict(EMPTY_RESULT)
