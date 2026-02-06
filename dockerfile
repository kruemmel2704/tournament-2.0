# Verwende ein leichtgewichtiges Python-Image
FROM python:3.9-slim

# Arbeitsverzeichnis im Container festlegen
WORKDIR /app

# Abhängigkeiten kopieren und installieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Den gesamten Rest des Codes kopieren
COPY . .

# Port 5000 freigeben (Standard Flask Port)
EXPOSE 5000

# Den Server starten
CMD ["python", "run.py"]