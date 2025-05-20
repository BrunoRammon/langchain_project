import pandas as pd
import requests
from datetime import datetime
from workalendar.america import Brazil
import gspread
import gspread
from google.oauth2.service_account import Credentials
from collections import namedtuple

# 3. Autenticação com Google Sheets
SERVICE_ACCOUNT_FILE = 'secrets/dragon-learning-460422-0927fe881fed.json'

# Define the required scopes
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 
          'https://www.googleapis.com/auth/drive']
credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
gc = gspread.authorize(credentials)

SheetMetadata = namedtuple('SheetMetadata', ['spreadsheets_name', 'page_name'])
ORGANOGRAMA = SheetMetadata(spreadsheets_name="Organograma",
                            page_name="Colaboradores")
VACATIONS = SheetMetadata(spreadsheets_name="DRAGON LEARNING AI - Solicitação de recesso (respostas)",
                            page_name="Respostas ao formulário 1")

# 4. Função: carregar organograma
def load_sheet(sheet_metadata):
    sheet_name = sheet_metadata.spreadsheets_name
    aba = sheet_metadata.page_name
    sh = gc.open(sheet_name)
    worksheet = sh.worksheet(aba)
    dados = worksheet.get_all_records()
    return pd.DataFrame(dados)

# 5. Buscar dados via e-mail
def buscar_dados_organograma(email: str) -> dict:
    df = load_sheet(ORGANOGRAMA)
    email = email.lower().strip()
    df.columns = [col.strip().lower() for col in df.columns]
    df = df.rename(columns={"e-mail": "email", "líder": "lider", "tribo": "tribo", "área": "area"})

    linha = df[df["email"] == email]
    if linha.empty:
        return {"erro": f"Email '{email}' não encontrado na aba Colaboradores"}

    linha = linha.iloc[0]
    return {
        "lider": linha["lider"],
        "tribo": linha["tribo"],
        "area": linha["area"]
    }

# 6. Cálculo de dias úteis
def calcular_dias_uteis(data_inicio, data_fim):
    cal = Brazil()
    dias = pd.date_range(start=data_inicio, end=data_fim, freq='D')
    dias_uteis = [d for d in dias if cal.is_working_day(d)]
    return len(dias_uteis)

# 7. Enviar formulário
def enviar_formulario(
    url,
    email,
    lider,
    tribo,
    area,
    contrato,
    acao,
    data_saida=None,
    data_retorno=None,
    qtd_dias=None,
    observacoes=None,
    data_saida_original=None,
    data_retorno_original=None,
    qtd_dias_original=None,
    justificativa=None
):
    dados = {
        "email": email,
        "lider": lider,
        "tribo": tribo,
        "area": area,
        "contrato": contrato,
        "acao": acao
    }

    if acao.lower() == "solicitação":
        dados.update({
            "data_saida": data_saida,
            "data_retorno": data_retorno,
            "qtd_dias": qtd_dias,
            "observacoes": observacoes or ""
        })
    elif acao.lower() == "cancelamento":

        dados.update({
            "data_saida_original": data_saida_original,
            "data_retorno_original": data_retorno_original,
            "qtd_dias_original": qtd_dias_original,
            "justificativa": justificativa or "",
            "data_saida": data_saida,
            "data_retorno": data_retorno,
            "qtd_dias": qtd_dias,
            "observacoes": observacoes or ""
        })

    response = requests.post(url, json=dados)
    print("Status:", response.status_code)
    print("Resposta:", response.text)


def load_opened_solicitations(email: str)-> str:
    now = datetime.now().strftime('%Y-%m-%d')
    df_vacations = load_sheet(VACATIONS)
    df_vacations = (
        df_vacations
        .query("(`Endereço de e-mail`==@email) & ((`Informe a data de saída solicitada anteriormente:`>@now) | (`Data do primeiro dia de saída`>@now))")
    )
    df_solicitations = (
        df_vacations
        .query('`Você quer fazer`.str.strip()=="Solicitação"')
        [['Carimbo de data/hora', 'Endereço de e-mail',
          'Data do primeiro dia de saída', 'Data de retorno as atividades']]
        .drop_duplicates()
        .rename(columns={
            'Carimbo de data/hora': 'timestamp',
            'Endereço de e-mail': 'email',
            'Data do primeiro dia de saída': 'saida',
            'Data de retorno as atividades': 'retorno',
        })
        .assign(
            timestamp = lambda df: pd.to_datetime(df.timestamp,
                                                  format='%d/%m/%Y %H:%M:%S',
                                                  dayfirst=True),
        )
        .sort_values('timestamp')
    )
    df_canc = (
        df_vacations
        .query('`Você quer fazer`.str.strip()=="Cancelamento"')
        [['Carimbo de data/hora','Endereço de e-mail',
          'Informe a data de saída solicitada anteriormente:',
          'Informe a data de retorno solicitada anteriormente:']]
        .drop_duplicates()
        .rename(columns={
            'Carimbo de data/hora': 'timestamp',
            'Endereço de e-mail': 'email',
            'Informe a data de saída solicitada anteriormente:': 'saida',
            'Informe a data de retorno solicitada anteriormente:': 'retorno',
        })
        .assign(
            timestamp = lambda df: pd.to_datetime(df.timestamp,
                                                  format='%d/%m/%Y %H:%M:%S',
                                                  dayfirst=True),
            flag_canc = 1
        )
        .sort_values('timestamp')
    )
    df_open_solicitations = (
        pd.merge_asof(
            df_solicitations,
            df_canc,
            by=['email', 'saida', 'retorno'],
            on='timestamp',
            direction='forward'
        )
        .query('flag_canc.isna()')
        .drop(columns='flag_canc')
    )
    return df_open_solicitations

# 7. Enviar formulário
def send_forms(
    url,
    email,
    lider,
    tribo,
    area,
    contrato,
    acao,
    data_saida=None,
    data_retorno=None,
    qtd_dias=None,
    observacoes=None,
    data_saida_original=None,
    data_retorno_original=None,
    qtd_dias_original=None,
    justificativa=None
):
    dados = {
        "email": email,
        "lider": lider,
        "tribo": tribo,
        "area": area,
        "contrato": contrato,
        "acao": acao
    }

    if acao.lower().strip() == "solicitação":
        dados.update({
            "data_saida": data_saida,
            "data_retorno": data_retorno,
            "qtd_dias": qtd_dias,
            "observacoes": observacoes or ""
        })
        response = requests.post(url, json=dados)
        print("Status:", response.status_code)
        print("Resposta:", response.text)
        return {
            'status_code': response.status_code,
            'return': 'Solicitação de férias realizada com sucesso.'
        }
    elif acao.lower().strip() == "cancelamento":
        df_open_solicitations = load_opened_solicitations(email)
        if len(df_open_solicitations) == 1:
            data_saida_original = df_open_solicitations['saida'].iloc[0]
            data_retorno_original = df_open_solicitations['retorno'].iloc[0]
            qtd_dias_original = calcular_dias_uteis(data_saida_original, data_retorno_original)
            dados.update({
                "data_saida_original": data_saida_original,
                "data_retorno_original": data_retorno_original,
                "qtd_dias_original": qtd_dias_original,
                "justificativa": justificativa or "",
                "data_saida": data_saida,
                "data_retorno": data_retorno,
                "qtd_dias": qtd_dias,
                "observacoes": observacoes or ""
            })
            response = requests.post(url, json=dados)
            print("Status:", response.status_code)
            print("Resposta:", response.text)
            return {
                'status_code': response.status_code,
                'return': 'Solicitação de cancelamento de férias realizada com sucesso.',
                'data_saida_original': data_saida_original,
                'data_retorno_original': data_retorno_original,
                'qtd_dias_original': qtd_dias_original
            }
        elif len(df_open_solicitations) == 0:
            return {
                'status_code': 202,
                'return': 'Não há férias para serem canceladas.'
            }
        else:
            message = 'Existe mais de um pedido de férias aberto. Consulte o RH para proceder esse cancelamento.'
            raise NotImplementedError(message)
    else:
        message = 'Apenas as opções "Solicitação" e "Cancelamento" estão disponíveis.'
        raise NotImplementedError(message)

if __name__ == "__main__":
    print(load_sheet(ORGANOGRAMA))