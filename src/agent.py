import os
from langchain.agents import AgentType, initialize_agent
from langchain_openai import ChatOpenAI
from langchain.tools import tool, StructuredTool
from langchain.memory import ConversationBufferMemory
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional
from langchain.chains import LLMChain
import json
from dotenv import load_dotenv
from src.register import buscar_dados_organograma, calcular_dias_uteis, send_forms
from src.prompts import EXTRACTOR_PROMPT
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=ROOT_DIR / "secrets" / ".env")

GOOGLE_FORM_API_URL = os.getenv('GOOGLE_FORM_API_URL')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
AGENT_MODEL = os.getenv('AGENT_MODEL')

def solicitar_ferias(data_saida: str, data_retorno: str, email: str,
                        observacoes: str = "") -> str:
    """
    Registra uma solicitação de período de férias.

    Args:
        data_saida: string no formato YYYY-MM-DD com a data do início das férias.
        data_retorno: string no formato YYYY-MM-DD com a data do retorno das férias.
        email: endereço de email do solicitante.
        observacoes: parametro opcional

    Returns:
        Uma frase indicando o sucesso ou erro na solicitação.
    """
    dados = buscar_dados_organograma(email)
    if "erro" in dados:
        return dados["erro"]

    qtd_dias = calcular_dias_uteis(data_saida, data_retorno)

    response_dict = send_forms(
        url=GOOGLE_FORM_API_URL,
        email=email,
        lider=dados["lider"],
        tribo=dados["tribo"],
        area=dados["area"],
        contrato="Prestador de Serviços",
        acao="Solicitação",
        data_saida=data_saida,
        data_retorno=data_retorno,
        qtd_dias=qtd_dias,
        observacoes=observacoes
    )
    return f"Solicitação de férias enviada com sucesso! Período: {data_saida} a {data_retorno} ({qtd_dias} dias úteis)."


class CancelarFeriasInput(BaseModel):
    email: str = Field(..., description="Endereço de e-mail completo do solicitante. Deve conter '@' e um domínio como '.com', '.com.br', '.io', etc. Ex: nome.sobrenome@datarisk.io")
    justificativa: Optional[str] = Field(
        "O usuário não justificou o cancelamento",
        description="Motivo para o cancelamento (opcional)"
    )

def cancelar_ferias(email: str, justificativa: Optional[str] = "O usuário não justificou o cancelamento") -> str:
    """
    Cancela um período de férias previamente solicitado.


    Args:
        email: Endereço de e-mail completo do solicitante. Deve conter '@' e um domínio como '.com', '.com.br', '.io', etc. Ex: nome.sobrenome@datarisk.io.
        justificativa: parametro opcional. Como a justificativa pode ser algo sensível tenha discrição ao pedir essa informação, deixando claro que ele só precisa fornecer uma justificativa caso se sinta a vontade.

    Returns:
        Uma frase indicando o sucesso ou erro na solicitação.
    """
    dados = buscar_dados_organograma(email)
    if "erro" in dados:
        return dados["erro"]

    response_dict = send_forms(
        url=GOOGLE_FORM_API_URL,
        email=email,
        lider=dados["lider"],
        tribo=dados["tribo"],
        area=dados["area"],
        contrato="Prestador de Serviços",
        acao="Cancelamento",
        justificativa=justificativa
    )
    if response_dict['status_code'] == 200:
        data_saida_original = response_dict['data_saida_original']
        data_retorno_original = response_dict['data_retorno_original']
        qtd_dias_original = response_dict['qtd_dias_original']

        return (
            "Cancelamento de férias enviado com sucesso! "
            f"Período cancelado: {data_saida_original} a {data_retorno_original}, "
            f"Totalizando {qtd_dias_original} dias úteis."
        )
    elif response_dict['status_code'] == 202:
        return response_dict['return']


def consultar_dias_uteis(data_inicio: str, data_fim: str) -> str:
    """
    Calcula a quantidade de dias úteis entre duas datas.
    Args:
        data_inicio: string no formato YYYY-MM-DD com a data do início das férias.
        data_fim: string no formato YYYY-MM-DD com a data do retorno das férias.

    Returns:
        Uma frase informando a quantidade de dias úteis entre as duas datas dadas.
    """
    dias = calcular_dias_uteis(data_inicio, data_fim)
    return f"Entre {data_inicio} e {data_fim} há {dias} dias úteis."

def criar_agente(agent_type=AgentType.OPENAI_FUNCTIONS):
    llm = ChatOpenAI(temperature=0, model=AGENT_MODEL, api_key=OPENAI_API_KEY)
    memory = ConversationBufferMemory(memory_key="chat_history")
    tool_sol_ferias = StructuredTool.from_function(
        func=solicitar_ferias,
        parse_docstring=True,
        description="Registra uma solicitação de férias."
    )
    tool_can_ferias = StructuredTool.from_function(
        func=cancelar_ferias,
        parse_docstring=True,
        # args_schema=CancelarFeriasInput,
        description="Cancela uma solicitação de férias realizada anteriormente."
    )
    tool_dias_uteis = StructuredTool.from_function(
        func=consultar_dias_uteis,
        parse_docstring=True,
        description="Calcula a quantidade de dias úteis entre duas datas"
    )
    return initialize_agent(
        agent = agent_type,
        tools=[tool_sol_ferias,tool_can_ferias,tool_dias_uteis],
        llm=llm,
        verbose=True,
        memory=memory
    )

# # 1. Slots a serem preenchidos
# slots = {
#     "data_inicio": None,
#     "data_fim": None,
#     "email": None
# }
# # 4. Configurações
# def create_extractor_chain():
#     llm = ChatOpenAI(temperature=0, model=AGENT_MODEL, api_key=OPENAI_API_KEY)
#     memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
#     extrator_chain = LLMChain(llm=llm, prompt=EXTRACTOR_PROMPT)
#     return extrator_chain

# extrator_chain = create_extractor_chain()
# def atualizar_slots(memory):
#     historico = "\n".join([f"{m.type.upper()}: {m.content}" for m in memory.chat_memory.messages])
#     resposta = extrator_chain.run(historico)
#     try:
#         dados = json.loads(resposta)
#         for k in slots:
#             if dados.get(k) and not slots[k]:
#                 slots[k] = dados[k]
#     except Exception as e:
#         print("Erro ao extrair dados:", e)
#         print("Resposta recebida:", resposta)

# def query_agent(entrada_usuario, agent):
#     resposta = agent(entrada_usuario)
#     atualizar_slots(agent.memory)
#     if all(slots.values()):
#         return solicitar_ferias(**slots)
#     return resposta

if __name__ == "__main__":
    print(AGENT_MODEL)