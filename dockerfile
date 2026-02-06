# Wir nutzen ein schlankes Python-Image
FROM python:3.9-slim

# Arbeitsverzeichnis im Container
WORKDIR /app

# Installiere System-Abhängigkeiten (falls nötig für manche Pakete)
RUN apt-get update && apt-get install -y gcc

# Kopiere die Requirements und installiere sie
# (Erstelle eine requirements.txt mit: Flask Flask-SQLAlchemy Flask-Login)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Wir kopieren den Code HIER NICHT fest rein, 
# sondern nutzen im docker-compose ein "Volume".
# Das erlaubt dir, am Code zu arbeiten, ohne neu zu builden.

# Port freigeben
EXPOSE 5000

# Start-Befehl
CMD ["python", "app.py"]