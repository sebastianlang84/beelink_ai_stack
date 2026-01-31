# Open WebUI + Apache Tika (Content Extraction) - Install & Setup

Ziel: Apache Tika als Content-Extraction-Engine fuer RAG/Knowledge-Uploads in Open WebUI nutzen.

## 0) Voraussetzungen
- Docker + Docker Compose
- Open WebUI laeuft bereits (Container) oder wird mit gestartet

Hinweis zu Images:
- `apache/tika:<version>` = minimal (kleiner)
- `apache/tika:<version>-full` = full (inkl. Tesseract OCR + zusaetzliche Parser; besser fuer Scan-PDFs)

Empfehlung:
- Wenn du viele Scan-PDFs hast: `...-full`
- Sonst: minimal reicht oft.

## 1) Compose: Tika zum Open-WebUI-Stack

In diesem Repo ist Tika bereits in `open-webui/docker-compose.yml` enthalten.
Der sichere Default ist: **kein Host-Port** (nur intern im Docker-Netz erreichbar).

Optional: Image-Tag ueber `open-webui/.config.env` steuern:
- `TIKA_IMAGE_TAG=latest-full`

Start (vom Repo-Root):
```bash
docker compose --env-file .env --env-file .config.env --env-file open-webui/.config.env -f open-webui/docker-compose.yml up -d
docker compose -f open-webui/docker-compose.yml ps
```

## 2) Open WebUI konfigurieren (UI)

1. Open WebUI oeffnen
2. Admin Panel -> Settings -> Documents
3. Content Extraction Engine: `Tika`
4. Tika Server URL: `http://tika:9998/tika`
5. Speichern

## 3) Funktionstest

### 3.1 Tika Health (im Docker-Netz)
```bash
docker exec -it owui sh -lc "wget -qO- http://tika:9998/version || true"
```

### 3.2 Logs pruefen
```bash
docker compose -f open-webui/docker-compose.yml logs -f tika
```
Du solltest Requests auf `/tika` sehen, sobald Open WebUI Dokumente ingestiert.

## 4) Wichtige Praxis-Hinweise

### 4.1 Sicherheit
- Vermeide `ports: \"9998:9998\"` ohne IP-Bindung (sonst kann Tika u.U. von aussen erreichbar werden).
- Prefer: kein `ports` (nur Docker-intern) oder `127.0.0.1` Bindung fuer Debug.

### 4.2 Debug-Proxy / NO_PROXY
Wenn Open WebUI ueber den debug-proxy geht (HTTP(S)_PROXY), dann muss `tika` in `OWUI_NO_PROXY` stehen,
damit OWUI den internen Call nicht proxied.

### 4.3 Re-Index / bestehende Dokumente
- Engine-Wechsel wirkt i. d. R. ab dem naechsten Upload/Re-Import.
- Fuer bestehende Knowledge-Basen ggf. neu ingestieren (re-upload / re-index).

## 5) Troubleshooting Quick Checks

1) Tika laeuft?
```bash
docker compose -f open-webui/docker-compose.yml ps | rg tika || true
```

2) Falscher URL-Pfad?
- In Open WebUI meist korrekt: `http://tika:9998/tika` (inkl. `/tika`)

