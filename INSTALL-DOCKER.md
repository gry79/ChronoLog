# ChronoLog – Installation mit Docker

## Voraussetzungen

- Docker Engine 20+
- Optional: Docker Compose v2

## Image bauen

Im Projektverzeichnis (dort, wo das `Dockerfile` liegt):

```bash
docker build -t chronolog:latest .
```

## Image von GitHub Actions (GHCR)

Bei jedem Push auf `main` baut der Workflow [`.github/workflows/docker-image.yml`](../.github/workflows/docker-image.yml) das Image und published es in die **GitHub Container Registry**:

```text
ghcr.io/<github-user>/chronolog:latest
ghcr.io/<github-user>/chronolog:<git-sha>
```

Beispiel (Repository-Owner `gry79`):

```bash
# Optional: anmelden (bei privatem Package nötig)
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

docker pull ghcr.io/gry79/chronolog:latest
docker run -d --name chronolog -p 8080:8080 -v chronolog-data:/data ghcr.io/gry79/chronolog:latest
```

Hinweise:

- Pull Requests bauen das Image nur zur Prüfung, pushen es aber **nicht**.
- Unter GitHub → *Packages* kann das Package auf **Public** gestellt werden, damit kein Login nötig ist.
- Beim ersten Publish muss die Package-Sichtbarkeit ggf. einmalig freigeschaltet werden.

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

`docker compose down` / `docker stop` senden **SIGTERM**. ChronoLog beendet den Webserver daraufhin bewusst (nicht erst nach dem Docker-Default-Timeout von ~10 s).

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
