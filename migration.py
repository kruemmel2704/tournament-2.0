from sqlalchemy import create_engine, MetaData, Table, select
import os

# Konfiguration (Pfade müssen stimmen!)
OLD_DB_PATH = os.path.abspath("./instance/tournament.db.old")
NEW_DB_PATH = os.path.abspath("./instance/tournament.db")

# Connection Strings für SQLAlchemy
OLD_DB_URI = f"sqlite:///{OLD_DB_PATH}"
NEW_DB_URI = f"sqlite:///{NEW_DB_PATH}"

def migrate():
    print("🚀 Starte Migration mit SQLAlchemy...")

    if not os.path.exists(OLD_DB_PATH):
        print(f"❌ FEHLER: Alte DB nicht gefunden: {OLD_DB_PATH}")
        return
    if not os.path.exists(NEW_DB_PATH):
        print(f"❌ FEHLER: Neue DB nicht gefunden: {NEW_DB_PATH}")
        return

    # 1. Verbindung zu beiden Datenbanken herstellen
    old_engine = create_engine(OLD_DB_URI)
    new_engine = create_engine(NEW_DB_URI)

    # 2. Struktur (Schema) einlesen
    old_meta = MetaData()
    old_meta.reflect(bind=old_engine)
    
    new_meta = MetaData()
    new_meta.reflect(bind=new_engine)

    # Verbindungen öffnen
    with old_engine.connect() as old_conn, new_engine.begin() as new_conn:
        # Wir gehen alle Tabellen der NEUEN Datenbank durch
        for table_name, new_table in new_meta.tables.items():
            
            # Check: Gibt es die Tabelle auch in der alten DB?
            if table_name not in old_meta.tables:
                print(f"⚠️  Tabelle '{table_name}' existiert nicht in alter DB. Überspringe...")
                continue
            
            old_table = old_meta.tables[table_name]

            # 3. Gemeinsame Spalten finden
            # Wir nehmen nur Spalten, die in BEIDEN Tabellen existieren
            common_columns = set(c.name for c in new_table.columns) & set(c.name for c in old_table.columns)
            
            if not common_columns:
                print(f"⚠️  Tabelle '{table_name}': Keine gemeinsamen Spalten. Überspringe...")
                continue

            print(f"✅ Migriere '{table_name}' ({len(common_columns)} Spalten)...")

            # 4. Daten holen und einfügen
            # SELECT col1, col2... FROM old_table
            sel_stmt = select(*(old_table.c[col] for col in common_columns))
            rows = old_conn.execute(sel_stmt).fetchall()

            if rows:
                # Daten in Dictionaries umwandeln für den Insert
                # (SQLAlchemy Core Insert unterstützt Listen von Dictionaries)
                data_to_insert = [
                    {col: row._mapping[col] for col in common_columns}
                    for row in rows
                ]
                
                # INSERT INTO new_table ...
                new_conn.execute(new_table.insert(), data_to_insert)
                print(f"   -> {len(rows)} Zeilen kopiert.")
            else:
                print("   -> Tabelle war leer.")

    print("\n🏁 Migration erfolgreich abgeschlossen!")

if __name__ == "__main__":
    migrate()