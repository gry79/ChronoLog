# ChronoLog – Installation (Python venv)

## Voraussetzungen

- Python 3.10 oder neuer
- pip

## Installation

```bash
# Repository-Verzeichnis
cd zeiterfassung

# Virtuelle Umgebung anlegen und aktivieren
python3 -m venv .venv
source .venv/bin/activate          # Linux / macOS
# .venv\Scripts\activate           # Windows

# Abhängigkeiten installieren
pip install -r requirements.txt
```

## Konfiguration

Die Datei `config.yaml` liegt im gleichen Verzeichnis wie `main.py`.

```yaml
db_file: data/chronolog.db
allow_user_registration: false
session_timeout_idle_min: 120
session_timeout_hard_min: 600
web_port: 8080
```

Alternativer Konfigurationspfad:

```bash
python main.py -c /pfad/zu/config.yaml
```

## Start

```bash
source .venv/bin/activate
python main.py
```

Die Applikation ist erreichbar unter: **http://localhost:8080**

### Erster Benutzer

Solange noch kein Benutzer existiert, ist die Registrierung freigeschaltet – unabhängig von `allow_user_registration`.  
Der **erste** registrierte Benutzer wird automatisch **Administrator**.

Danach gilt `allow_user_registration` aus der Konfiguration. Administratoren können weitere Benutzer unter **Admin → Benutzer** anlegen.

### Empfohlener Erststart

1. Applikation starten und registrieren (wird Admin).
2. Unter **Admin → Chronos** eine Chronos-Konfiguration anlegen (z.B. «Standard 8.0h»).
3. Unter **Einstellungen** Chronos zuweisen, Startmonat/-jahr und initiales Zeitkonto setzen.
4. Mit der Zeiterfassung beginnen.

## Datenbank

DuckDB-Datei wird beim Start automatisch erstellt und migriert (`db_file`).  
Migrationen sind additiv und verlieren keine Daten.

## Deinstallation

```bash
deactivate
rm -rf .venv data/chronolog.db data/.secret_key
```
