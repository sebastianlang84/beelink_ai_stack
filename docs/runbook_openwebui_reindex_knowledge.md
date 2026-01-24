## Runbook — Open WebUI Knowledge Reindex nach Embedding‑Model‑Wechsel

Ziel: Nach einem Wechsel des Embedding‑Modells die **bestehenden Knowledge Collections** sauber neu indexieren (Embeddings neu berechnen), **ohne** die Original‑Uploads zu verlieren.

> Wichtig: **Vector Storage Reset** löscht Embeddings/Index, nicht automatisch die Dateien.  
> Re‑Index funktioniert nur, wenn **Collections + File‑Links** in der DB vorhanden sind.

---

## 0) Voraussetzungen

- Open WebUI läuft und ist erreichbar.
- Admin‑Zugriff ist möglich (UI oder API).
- Optional: Zugriff auf die Open WebUI Datenbank (`webui.db`) im Container/Volume.

---

## 1) Quick‑Check: Dateien vorhanden?

Im Open WebUI Container/Host prüfen (Pfad je nach Setup):

```
docker exec owui ls -la /app/backend/data/uploads | head -n 5
docker exec owui bash -lc "ls -1 /app/backend/data/uploads | wc -l"
```

Wenn `uploads` leer ist → **nur Restore aus Backup** oder **Neu‑Upload** hilft.

---

## 2) Quick‑Check: Knowledge Collections sichtbar?

API‑Check (von Host oder Container, nutzt `OPEN_WEBUI_API_KEY`):

```
python - <<'PY'
from urllib.request import Request, urlopen
import os

base = "http://<owui-host>:8080"
key = os.environ.get("OPEN_WEBUI_API_KEY") or ""
headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
req = Request(f"{base}/api/v1/knowledge/", headers=headers)
with urlopen(req, timeout=30) as resp:
    print(resp.read().decode("utf-8", errors="replace"))
PY
```

Erwartung: `items` enthält deine Collections.

**Falls `items` leer:** die Collections fehlen in `webui.db` → siehe Schritt 4.

---

## 3) Standard‑Reindex (UI)

Im Open WebUI UI:

1. **Settings → Vector Storage Reset** (falls Modelwechsel, optional)
2. **Reindex Knowledge Base Vectors**

**Wichtig:** Dieser Schritt nutzt vorhandene Collections + File‑Links.

---

## 4) Recovery: Collections fehlen (DB hat Files, aber keine Knowledge‑Rows)

### 4.1 Backup der DB

```
docker exec owui cp /app/backend/data/webui.db /app/backend/data/webui.db.bak
```

### 4.2 IDs der Collections ermitteln

Wenn du die IDs nicht mehr im UI siehst, kannst du sie über die DB‑Links ableiten:

```
docker exec -i owui python - <<'PY'
import sqlite3
conn = sqlite3.connect('/app/backend/data/webui.db')
cur = conn.cursor()
cur.execute("SELECT knowledge_id, COUNT(*) FROM knowledge_file GROUP BY knowledge_id")
print(cur.fetchall())
conn.close()
PY
```

### 4.3 Collections in DB wieder anlegen (Minimal)

> Achtung: direkte DB‑Writes. Nur wenn `items` leer sind.

```
docker exec -i owui python - <<'PY'
import sqlite3, time

conn = sqlite3.connect('/app/backend/data/webui.db')
cur = conn.cursor()

# User-ID aus knowledge_file ableiten (Owner der Files)
cur.execute("SELECT DISTINCT user_id FROM knowledge_file")
user_ids = [r[0] for r in cur.fetchall()]
if not user_ids:
    raise SystemExit("No user_id in knowledge_file")
user_id = user_ids[0]

# Map: knowledge_id -> name (anpassen!)
name_map = {
    # "30db72bd-1086-45ae-964e-505543d3951b": "stocks_crypto",
    # "67242f2f-f286-41c1-8ecc-eef9bf5aef53": "ai_knowledge",
}

now = int(time.time())
cur.execute("SELECT id FROM knowledge")
existing = {r[0] for r in cur.fetchall()}

created = []
for kid, name in name_map.items():
    if kid in existing:
        continue
    cur.execute(
        "INSERT INTO knowledge (id, user_id, name, description, meta, created_at, updated_at, access_control) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (kid, user_id, name, "", "{}", now, now, None),
    )
    created.append((kid, name))

conn.commit()
conn.close()
print("created", created)
PY
```

Danach nochmals Schritt 2 (API‑Check).

---

## 5) Re‑Upload (allgemein, ohne spezielle Tools)

Wenn du sicherstellen willst, dass **neue Embeddings** entstehen:

### 5.1 UI‑Variante (empfohlen)

- Öffne die Collection → Re‑index / Re‑process (je nach UI‑Version).
- Alternativ: Dateien entfernen und erneut hochladen (z. B. aus Export/Backup).

### 5.2 API‑Variante (generisch)

1) File‑IDs der Collection aus DB oder UI ermitteln.  
2) Für jedes File: per API erneut verarbeiten (Endpoint ist versionsabhängig).

---

## 6) Optional: Global Reindex per API

Admin‑Reindex via API (kann lange dauern, blockiert Request):

```
python - <<'PY'
from urllib.request import Request, urlopen
import os

base = "http://<owui-host>:8080"
key = os.environ.get("OPEN_WEBUI_API_KEY") or ""
headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
req = Request(f"{base}/api/v1/knowledge/reindex", headers=headers, method="POST")
with urlopen(req, timeout=3600) as resp:
    print(resp.read().decode("utf-8", errors="replace"))
PY
```

Logs prüfen:

```
docker logs owui --tail 200
```

---

## 7) Validierung (minimal)

- UI: Knowledge → Collection → Files → Count stimmt.
- Retrieval‑Test: Eine Frage stellen, Sources erscheinen.
- Logs: `open_webui.routers.retrieval` zeigt „embeddings generated“.
