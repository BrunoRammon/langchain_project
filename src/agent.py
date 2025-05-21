import os
from langchain.agents import AgentType, initialize_agent
from langchain_openai import ChatOpenAI
from langchain.tools import StructuredTool
from langchain.memory import ConversationBufferMemory
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional
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
        email: endereço de email do solicitante. Lembre-se de pedir essa informação ao usuário.
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

def consultar_ano_atual()-> str:
    """
    Consulta e retorna o ano atual. Essa ferramenta deve ser usada quando o ano não for citado 
    diretamente na solicitação das férias.
    """
    current_year = datetime.now().strftime('%Y')
    return f"O ano atual é {current_year}"


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
    tool_current_year = StructuredTool.from_function(
        func=consultar_ano_atual,
        parse_docstring=True,
        description="Consulta o ano atual."
    )
    return initialize_agent(
        agent = agent_type,
        tools=[tool_sol_ferias, tool_can_ferias, tool_dias_uteis, tool_current_year],
        llm=llm,
        verbose=True,
        memory=memory
    )

def criar_agente():
    llm = ChatOpenAI(temperature=0, model="gpt-4.1-nano", api_key=OPENAI_API_KEY)
    # tools = FeriasTools()
    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    tools = [
        StructuredTool.from_function(
            func=solicitar_ferias,
            parse_docstring=True,
            description="Registra uma solicitação de férias."
        ),
        StructuredTool.from_function(
            func=cancelar_ferias,
            parse_docstring=True,
            # args_schema=CancelarFeriasInput,
            description="Cancela uma solicitação de férias realizada anteriormente."
        ),
        StructuredTool.from_function(
            func=consultar_dias_uteis,
            parse_docstring=True,
            description="Calcula a quantidade de dias úteis entre duas datas"
        ),
        StructuredTool.from_function(
            func=consultar_ano_atual,
            parse_docstring=True,
            description="Consulta o ano atual."
        ),
    ]
    

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "Você é um assistente que gerencia solicitações de recesso"),
            MessagesPlaceholder("chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )
    agent = create_openai_functions_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True, memory=memory)

if __name__ == "__main__":
    print(AGENT_MODEL)