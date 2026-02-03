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

