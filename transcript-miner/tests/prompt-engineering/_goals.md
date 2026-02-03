# Goals (Prompt Engineering / RAG)

Ich baue dieses Test-Folder-Setup, um Prompt-Iteration fuer OWUI/RAG schnell und reproduzierbar zu machen.

## Was ich bezwecken moechte
- Ich will in Open WebUI (OWUI) Fragen stellen koennen zu:
  - Krypto / Bitcoin
  - Aktien / einzelne Companies
  - Gesamtmarkt / Makro (Rates, Liquiditaet, Dollar, Rezession, etc.)
- Ich will, dass RAG bei diesen Fragen **praezise** die richtigen Passagen findet (hohe Retrieval-Praezision) und nicht „gemischte“ Chunks liefert.
- Ich will, dass die Antworten dadurch:
  - fokussierter (weniger Topic-Drift),
  - nachvollziehbarer (klarer Bezug zu Quellen),
  - konsistenter (gleiche Frage -> aehnliche, stabile Struktur) werden.

## Recency/Alter: neuere Infos hoeher gewichten (ohne alte zu ignorieren)
Problem:
- Bei Themen wie Bitcoin/Krypto (und auch Earnings/Guidance bei Aktien) sind Summaries von vor Wochen/Monaten oft faktisch ueberholt.
- Trotzdem sollen alte Summaries nicht weggeworfen werden, weil sie Kontext/Narrativ/Regeln enthalten koennen.

Ziel:
- Neuere Summaries sollen **bevorzugt** im Retrieval auftauchen (time-decay), waehrend aeltere weiterhin auffindbar bleiben.

Moegliche Loesungswege (RAG-seitig):
- Zwei Knowledge-Kanaele/Collections:
  - `investing_recent` (z. B. letzte 14/30 Tage)
  - `investing_archive` (alles aelter)
  -> Query default: recent zuerst; archive nur wenn noetig oder explizit angefragt ("historisch", "langfristig", "since 2024").
- Timestamp/Recency als explizite Retrieval-Hints in jedem Dokument:
  - `published_at`/`fetched_at` muss im Dokument stehen (oder als Frontmatter/Metadata), damit ein Retriever/Reranker Zeit beruecksichtigen kann.
  - Optional: `recency_bucket: today|7d|30d|90d|archive`.
- Reranking mit Zeit-Decay (wenn wir den Retrieval-Stack kontrollieren):
  - Score = semantic_similarity * time_decay(published_at)
  - time_decay z. B. exponentiell fuer Krypto, flacher fuer Fundamentals.
- Prompt-Regel im Chat (Answer-Policy):
  - Wenn mehrere Treffer mit widerspruechlichen Aussagen existieren, bevorzuge die juengsten Quellen und nenne das Datum.
  - Nutze aeltere Quellen nur als Kontext/History, nicht fuer "aktueller Stand".

## Long-term Knowledge: stabile Dossiers (Business Models etc.)
Problem:
- Manche Informationen (Geschaeftsmodell, Produktlinien, Moat, Revenue-Mechanik) aendern sich nicht wochenweise und sollten nicht immer neu aus Videos "re-konstruiert" werden.

Ziel:
- Eigene, langfristige Wissensobjekte pflegen (z. B. Company-Steckbriefe), die mit der Zeit wachsen und bei Fragen zu einer Firma sofort das stabile Fundament liefern.

Ansatz:
- Separater Agent/Prompt (nicht der per-video Summary Agent):
  - Input: (a) bestehendes Dossier, (b) neue Video-Summaries/Transcripts als Delta
  - Output: aktualisiertes Dossier + klare Quellenverweise (Video-ID + Datum)
- Eigene Knowledge-Collection in OWUI:
  - z. B. `company_dossiers` (langfristig/stabil) getrennt von `investing` (laufender News-Stream)
- Struktur fuer ein Dossier (Beispiel):
  - Kurzprofil, Geschaeftsmodell, Umsatztreiber, Kostenstruktur, Wettbewerb, Risiken, Key Metrics, Thesen/Counterthesen, "Was hat sich geaendert?" (Changelog mit Datum)

## Messbar/Praktisch (wie ich es teste)
- Old vs New Summary nebeneinander vergleichen fuer die letzten 10 Videos:
  - Was wird unter Macro/Stocks/Crypto getrennt?
  - Sind die Chunks topic-rein (keine Vermischung)?
  - Sind Key Claims mit kurzen Evidence-Quotes unterfuettert?
- Standard-Testfragen (vorher/nachher):
  - \"Wie ist das Bitcoin-Narrativ?\"
  - \"Welche Makrotreiber wurden genannt?\"
  - \"Was waren Risiken fuer Aktie X?\"
  - \"Gib nur die Zahlen zu BTC.\"
