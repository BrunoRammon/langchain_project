from langchain.prompts import PromptTemplate

STR_EXTRACTOR_PROMPT = """
Você é um assistente que ajuda a registrar pedidos de férias. Com base no histórico abaixo, extraia os seguintes dados se disponíveis:

- data_inicio: data de início do recesso
- data_fim: data de fim do recesso
- email: endereço de email do solicitante

Histórico da conversa:
{historico}

Responda apenas no formato JSON como este exemplo:
{{
  "data_inicio": "2025-07-29",
  "data_fim": "2025-08-20",
  "email": "joao@example.com"
}}

Se algum dado estiver ausente, use `null`.
"""
EXTRACTOR_PROMPT = PromptTemplate(
    input_variables=["historico"],
    template=STR_EXTRACTOR_PROMPT
)