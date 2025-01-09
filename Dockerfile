# Imagen base de Python
FROM python:3.10-slim

# Establecer directorio de trabajo
WORKDIR /app

# Copiar dependencias e instalarlas
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Instalar ffmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copiar el resto de los archivos
COPY . .

# Exponer puerto (opcional para API)
EXPOSE 5000

# Comando para ejecutar el bot
CMD ["python", "src/bot/main.py"]
