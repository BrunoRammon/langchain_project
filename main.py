from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from src.agent import criar_agente

app = FastAPI()
agente = criar_agente()

class Requisicao(BaseModel):
    pergunta: str

@app.post("/agent/")
def executar_agente(req: Requisicao):
    try:
        resposta = agente.run(req.pergunta)
        return {"resposta": resposta}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
