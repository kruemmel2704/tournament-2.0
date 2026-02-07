import sqlite3
import os

# Konfiguration
OLD_DB = "./instance/tournament.db.old"  # Deine umbenannte alte DB
NEW_DB = "./instance/tournament.db"      # Die neu erstellte leere DB

def get_columns(cursor, table_name):
    """Holt die Spaltennamen einer Tabelle"""
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        return {row[1] for row in cursor.fetchall()}
    except:
        return set()

def migrate():
    if not os.path.exists(OLD_DB):
        print(f"❌ Fehler: '{OLD_DB}' nicht gefunden. Bitte benenne deine alte DB erst um.")
        return
    if not os.path.exists(NEW_DB):
        print(f"❌ Fehler: '{NEW_DB}' nicht gefunden. Starte die App einmal kurz, damit die neue leere DB erstellt wird.")
        return

    print(f"🔄 Starte Migration von {OLD_DB} nach {NEW_DB}...")

    # Verbindungen herstellen
    conn_new = sqlite3.connect(NEW_DB)
    cursor_new = conn_new.cursor()
    
    # Wir hängen die alte DB an die neue Session an, um Daten direkt zu kopieren
    cursor_new.execute(f"ATTACH DATABASE '{OLD_DB}' AS old_db")

    # Liste aller Tabellen in der NEUEN Datenbank (das Ziel)
    cursor_new.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [row[0] for row in cursor_new.fetchall()]

    for table in tables:
        # Checken, ob Tabelle auch in der alten DB existiert
        try:
            cursor_new.execute(f"SELECT 1 FROM old_db.{table} LIMIT 1")
        except sqlite3.OperationalError:
            print(f"⚠️  Tabelle '{table}' existiert nicht in der alten DB. Überspringe...")
            continue

        # Spalten vergleichen
        cols_old = get_columns(cursor_new, f"old_db.{table}")
        cols_new = get_columns(cursor_new, table)

        # Schnittmenge: Nur Spalten kopieren, die in beiden existieren
        common_cols = list(cols_old.intersection(cols_new))
        
        if not common_cols:
            print(f"⚠️  Tabelle '{table}': Keine gemeinsamen Spalten. Überspringe...")
            continue

        cols_string = ", ".join(common_cols)
        
        print(f"✅ Migriere Tabelle '{table}' ({len(common_cols)} Spalten)...")
        
        # SQL Magie: Daten direkt von A nach B schaufeln
        try:
            sql = f"INSERT INTO main.{table} ({cols_string}) SELECT {cols_string} FROM old_db.{table}"
            cursor_new.execute(sql)
            conn_new.commit()
            print(f"   -> Daten erfolgreich kopiert.")
        except Exception as e:
            print(f"   ❌ Fehler beim Kopieren von {table}: {e}")

    # Sonderfall: Member zu TeamMember Migration (Optional)
    # Da die Tabelle 'Member' gelöscht wurde und 'TeamMember' neu ist,
    # wird sie oben nicht automatisch kopiert.
    print("\n🔍 Prüfe auf alte 'Member' Daten...")
    try:
        # Prüfen ob alte Member Tabelle existiert
        cursor_new.execute("SELECT count(*) FROM old_db.Member")
        count = cursor_new.fetchone()[0]
        if count > 0:
            print(f"⚠️  ACHTUNG: {count} alte Einträge in 'Member' gefunden.")
            print("   Diese können nicht automatisch nach 'TeamMember' verschoben werden,")
            print("   da die Struktur (Owner-ID, Activision-ID) fehlt.")
            print("   Bitte füge die Spieler über das Dashboard neu hinzu.")
    except:
        print("   -> Keine alte 'Member' Tabelle gefunden (Gut).")

    # Aufräumen
    conn_new.close()
    print("\n🏁 Migration abgeschlossen!")

if __name__ == "__main__":
    migrate()