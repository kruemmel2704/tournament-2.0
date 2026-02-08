from sqlalchemy import create_engine, MetaData, Table, select, text
import os

# Konfiguration
OLD_DB_PATH = os.path.abspath("./instance/tournament.db.old")
NEW_DB_PATH = os.path.abspath("./instance/tournament.db")

# Connection Strings
OLD_DB_URI = f"sqlite:///{OLD_DB_PATH}"
NEW_DB_URI = f"sqlite:///{NEW_DB_PATH}"

def migrate():
    print("🚀 Starte VOLLSTÄNDIGE Migration (Alles wird überschrieben)...")

    if not os.path.exists(OLD_DB_PATH):
        print(f"❌ FEHLER: Alte DB nicht gefunden: {OLD_DB_PATH}")
        return
    if not os.path.exists(NEW_DB_PATH):
        print(f"❌ FEHLER: Neue DB nicht gefunden: {NEW_DB_PATH}")
        return

    # Engines erstellen
    old_engine = create_engine(OLD_DB_URI)
    new_engine = create_engine(NEW_DB_URI)

    # Metadaten (Struktur) laden
    old_meta = MetaData()
    old_meta.reflect(bind=old_engine)
    
    new_meta = MetaData()
    new_meta.reflect(bind=new_engine)

    # Transaktion starten
    with old_engine.connect() as old_conn, new_engine.begin() as new_conn:
        
        # Foreign Keys ausschalten (wichtig beim Leeren der Tabellen)
        new_conn.execute(text("PRAGMA foreign_keys=OFF"))

        for table_name, new_table in new_meta.tables.items():
            
            # Check: Existiert Tabelle im Backup?
            if table_name not in old_meta.tables:
                print(f"⚠️  Tabelle '{table_name}' fehlt im Backup. Überspringe...")
                continue
            
            old_table = old_meta.tables[table_name]

            # Gemeinsame Spalten finden
            common_columns = set(c.name for c in new_table.columns) & set(c.name for c in old_table.columns)
            
            if not common_columns:
                print(f"⚠️  Tabelle '{table_name}': Keine gemeinsamen Spalten.")
                continue

            print(f"✅ Migriere '{table_name}'...")

            # 1. ZIEL-TABELLE KOMPLETT LEEREN
            # Damit stellen wir sicher, dass ALLE alten Daten Platz haben
            # und keine "Unique Constraint" Fehler auftreten.
            new_conn.execute(new_table.delete())

            # 2. ALTE DATEN HOLEN
            sel_stmt = select(*(old_table.c[col] for col in common_columns))
            rows = old_conn.execute(sel_stmt).fetchall()

            # 3. DATEN EINFÜGEN
            if rows:
                data_to_insert = [
                    {col: row._mapping[col] for col in common_columns}
                    for row in rows
                ]
                new_conn.execute(new_table.insert(), data_to_insert)
                print(f"   -> {len(rows)} Zeilen wiederhergestellt.")
            else:
                print("   -> Tabelle war leer.")

        # Foreign Keys wieder an
        new_conn.execute(text("PRAGMA foreign_keys=ON"))

    print("\n🏁 Migration abgeschlossen! Alle alten Daten sind jetzt aktiv.")

if __name__ == "__main__":
    migrate()