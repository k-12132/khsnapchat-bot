FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot.py downloader.py stats_store.py activation.py ./
COPY tests ./tests
RUN python -m unittest discover -s tests -v
RUN useradd --create-home bot
USER bot
CMD ["python", "bot.py"]
