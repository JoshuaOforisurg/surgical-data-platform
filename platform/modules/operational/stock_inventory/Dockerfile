FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV SURGICAL_PLATFORM_ROOT=/app

WORKDIR /app

COPY modules/operational/stock_inventory/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY modules/operational/stock_inventory/ ./
COPY shared/ ./shared/

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=3)"

CMD ["streamlit", "run", "streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501"]
