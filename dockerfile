# Imagem base oficial com Python 3.11
FROM python:3.12-slim

# Variável para não criar .pyc
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instala o uv
RUN pip install --no-cache-dir uv

# Cria diretório da aplicação
WORKDIR /app

# Copia os arquivos de dependência primeiro (melhora cache)
COPY uv.lock ./
COPY pyproject.toml ./pyproject.toml

# Instala dependências
# RUN uv pip install -r uv.lock
RUN uv sync

# Copia todo o código do projeto (src/ e secrets/)
COPY main.py ./main.py
COPY src/ ./src/

# Expõe a porta do FastAPI
EXPOSE 8000

# Comando para iniciar o servidor FastAPI
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
