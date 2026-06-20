FROM python:3.12-slim

WORKDIR /app

# Nur die Pakete die das Dashboard braucht
RUN pip install --no-cache-dir \
    streamlit \
    requests \
    folium \
    streamlit-folium \
    plotly \
    pandas

COPY app.py .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]