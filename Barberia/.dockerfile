# Usar Python 3.11 como base
FROM python:3.11-slim

# Instalar dependencias del sistema necesarias para SQLite
RUN apt-get update && apt-get install -y \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar requirements.txt primero para aprovechar el cache de Docker
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la aplicación
COPY . .

# Crear directorio para la base de datos con permisos correctos
RUN mkdir -p /app/data && chmod 755 /app/data

# Exponer el puerto
EXPOSE 8080

# Comando para ejecutar la aplicación
CMD ["python", "montana_backend.py"]
