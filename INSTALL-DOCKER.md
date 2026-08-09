# ChronoLog – Installation mit Docker

## Voraussetzungen

- Docker Engine 20+
- Optional: Docker Compose v2

## Image bauen

Im Projektverzeichnis (dort, wo das `Dockerfile` liegt):

```bash
docker build -t chronolog:latest .
```

## Container starten (Kommandozeile)

```bash
docker run -d \
  --name chronolog \
  -p 8080:8080 \
  -v chronolog-data:/data \
  chronolog:latest
```

- Port **8080** im Container wird auf den Host gemappt.
- Volume **chronolog-data** speichert die DuckDB-Datenbank und den Secret-Key unter `/data`.

Applikation: **http://localhost:8080**

### Logs anzeigen

```bash
docker logs -f chronolog
```

### Container stoppen / entfernen

```bash
docker stop chronolog
docker rm chronolog
```

Volume (inkl. Datenbank) entfernen:

```bash
docker volume rm chronolog-data
```

## Docker Compose

```bash
docker compose up -d --build
```

Stoppen:

```bash
docker compose down
```

Volume behalten (Standard bei `down`). Mit Daten löschen:

```bash
docker compose down -v
```

## Eigene Konfiguration

`config.yaml` anpassen und einbinden:

```bash
docker run -d \
  --name chronolog \
  -p 8080:8080 \
  -v chronolog-data:/data \
  -v "$(pwd)/config.yaml:/app/config.yaml:ro" \
  chronolog:latest
```

**Hinweis:** In Docker zeigt `db_file` standardmässig auf `/data/chronolog.db` (siehe Dockerfile).  
Wenn Sie eine eigene `config.yaml` mounten, setzen Sie `db_file` entsprechend auf einen Pfad unter `/data`, damit die Daten im Volume bleiben.

Beispiel:

```yaml
db_file: /data/chronolog.db
allow_user_registration: false
session_timeout_idle_min: 120
session_timeout_hard_min: 600
web_port: 8080
```

## Erster Login

Siehe [INSTALL.md](INSTALL.md) – der erste registrierte Benutzer wird Administrator.
