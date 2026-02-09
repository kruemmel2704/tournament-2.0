#!/bin/bash

# --- KONFIGURATION ---
DB_PATH="./instance/tournament.db"       # Pfad zur aktuellen DB
DB_OLD_PATH="./instance/tournament.db.old" # Pfad für das Backup
MIGRATION_SCRIPT="migration.py"          # Name deines Python-Scripts

echo "🚀 Starte Deployment-Prozess..."

# 1. Docker Container herunterfahren
echo "🛑 Stoppe Docker Container..."
docker compose down

# 2. Git Pull (Neuesten Code holen)
echo "⬇️  Ziehe aktuellen Code von Git..."
git pull

# 3. Datenbank umbenennen (Backup)
if [ -f "$DB_PATH" ]; then
    echo "📦 Verschiebe alte Datenbank zu $DB_OLD_PATH..."
    mv "$DB_PATH" "$DB_OLD_PATH"
else
    echo "⚠️  Keine Datenbank unter $DB_PATH gefunden. Überspringe Backup."
fi

# 4. Docker kurz starten (damit Flask die neue leere DB erstellt)
echo "🏗️  Starte Container kurzzeitig, um neue DB-Struktur zu generieren..."
docker compose up -d

# Wir warten kurz, damit der Container Zeit hat, hochzufahren und db.create_all() auszuführen
echo "⏳ Warte 10 Sekunden auf Initialisierung..."
sleep 10

# 5. Docker wieder stoppen (für saubere Migration)
echo "⏸️  Stoppe Container für die Daten-Migration..."
docker compose stop

# 6. Migrations-Tool laufen lassen
if [ -f "$MIGRATION_SCRIPT" ]; then
    echo "🔄 Führe Migrations-Skript aus ($MIGRATION_SCRIPT)..."
    # Wir führen das Python-Skript auf dem Host aus. 
    # Voraussetzung: Python ist auf dem Server installiert.
    python3 "$MIGRATION_SCRIPT"
else
    echo "❌ FEHLER: Migrations-Skript $MIGRATION_SCRIPT nicht gefunden!"
    exit 1
fi

# 7. Docker final starten
echo "✅ Migration beendet. Starte Container endgültig..."
docker compose up -d --build

echo "🎉 Fertig! Das System ist wieder online."