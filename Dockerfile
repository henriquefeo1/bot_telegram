FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Porta do webhook (deve bater com WEBHOOK_PORT no .env)
EXPOSE 8000

# Persistir o banco fora do container via volume (veja docker-compose.yml)
CMD ["python", "-m", "bot.main"]
