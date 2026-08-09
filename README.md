# ChronoLog

Zeiterfassungsapplikation für tägliche Arbeitszeiten, Absenzen und das persönliche Zeitkonto (Über-/Minusstunden) basierend auf konfigurierbaren Soll-Arbeitszeiten (**Chronos**).

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Flask](https://img.shields.io/badge/Flask-3.1-green)
![DuckDB](https://img.shields.io/badge/DuckDB-1.5-yellow)
![License](https://img.shields.io/badge/license-MIT-green)

## Features

- **Zeiterfassung** pro Monat mit flexibler Zeiteingabe (`8:00`, `800`, … → `08:00`)
- Mehrere Einträge pro Tag, Überlappungsprüfung, optionale Beschreibung
- **Zeitkonto**: Vormonat − Sollstunden/Monat + erfasste Stunden (inkl. Absenzen)
- **Absenzen** (eintägig mit Stunden oder mehrtägig mit Soll pro Tag)
- **Chronos-Konfiguration** (Soll pro Arbeitstag + wiederkehrende/einmalige Spezialtage)
- Benutzer- und Admin-Rollen, Sessions mit Idle- und Hard-Timeout
- Monat abschliessen / wieder öffnen
- DuckDB-Persistenz mit automatischen, datenverlustfreien Migrationen beim Start

## Tech-Stack

| Komponente   | Technologie                          |
|-------------|--------------------------------------|
| Backend     | Python 3, Flask                      |
| UI          | Jinja2, HTMX, Tailwind CSS (CDN)     |
| Datenbank   | DuckDB                               |
| Passwörter  | bcrypt                               |
| Config      | YAML (`config.yaml`)                 |
| Deployment  | Docker / Docker Compose              |

## Schnellstart (lokal)

```bash
# Repository klonen und in das Verzeichnis wechseln
cd zeiterfassung

# Virtuelle Umgebung
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Abhängigkeiten
pip install -r requirements.txt

# Starten
python main.py
```

Anschliessend im Browser: **http://localhost:8080**

Detaillierte Anleitung: [INSTALL.md](INSTALL.md)

### Erster Benutzer

Solange noch kein Benutzer existiert, ist die **Registrierung freigeschaltet**.  
Der **erste** registrierte Benutzer wird automatisch **Administrator**.

Empfohlener Ablauf danach:

1. Unter **Admin → Chronos** eine Konfiguration anlegen (z. B. 8.0 h/Tag, Feiertage)
2. Unter **Einstellungen** Chronos, Startmonat/-jahr und initiales Zeitkonto setzen
3. Mit der Zeiterfassung beginnen

## Docker

```bash
docker compose up -d --build
```

Oder manuell:

```bash
docker build -t chronolog:latest .
docker run -d --name chronolog -p 8080:8080 -v chronolog-data:/data chronolog:latest
```

Ausführlich: [INSTALL-DOCKER.md](INSTALL-DOCKER.md)

## Konfiguration

`config.yaml` (gleicher Ordner wie `main.py`, alternativ `-c /pfad/zur/config.yaml`):

```yaml
db_file: data/chronolog.db
allow_user_registration: false
session_timeout_idle_min: 120   # Minuten ohne Aktivität → Logout
session_timeout_hard_min: 600   # Absolute Session-Dauer
web_port: 8080
```

| Parameter | Bedeutung | Default |
|-----------|-----------|---------|
| `db_file` | Pfad zur DuckDB-Datei | `chronolog.db` |
| `allow_user_registration` | Selbstregistrierung erlauben | `false` |
| `session_timeout_idle_min` | Idle-Timeout (Minuten) | `120` |
| `session_timeout_hard_min` | Hartes Timeout (Minuten) | `600` |
| `web_port` | HTTP-Port | `8080` |

## Projektstruktur

```
main.py                 # Einstiegspunkt (einzige .py im Root)
config.yaml             # Applikationskonfiguration
app/
  config.py             # YAML laden
  logger.py             # Farbiges Konsolen-Logging
  security.py           # Passwort, CSRF, Tokens
  db/                   # DuckDB, Migrationen, Repositories
  services/             # Fachlogik (Zeit, Absenzen, Auth, …)
  web/                  # Flask App, Routes, Helpers
templates/              # Jinja2 UI (Deutsch)
static/                 # CSS, JS, Login-Hintergrundbild
Dockerfile
docker-compose.yml
```

## Sicherheit (Kurz)

- Passwort-Hashing mit bcrypt
- Serverseitige Sessions (Cookie nur Session-ID, HttpOnly, SameSite)
- CSRF-Schutz bei zustandsändernden Requests
- Security-Header (CSP, X-Frame-Options, …)
- Parametrisierte SQL-Zugriffe

> Der mitgelieferte Flask-Server ist für Entwicklung und interne Nutzung gedacht. Für öffentliches Produktiv-Deployment empfiehlt sich ein WSGI-Server (z. B. Gunicorn) hinter einem Reverse Proxy.

## Dokumentation

| Datei | Inhalt |
|-------|--------|
| [INSTALL.md](INSTALL.md) | Installation mit Python venv |
| [INSTALL-DOCKER.md](INSTALL-DOCKER.md) | Docker Image & Compose |
| [project_doc/PROJECT.md](project_doc/PROJECT.md) | Fachliche Spezifikation & Annahmen |

## Lizenz

[MIT](https://opensource.org/licenses/MIT)
