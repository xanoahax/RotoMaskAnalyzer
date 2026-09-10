# RotoMaskAnalyzer: Soft-Alpha-Versuchsschema

**Datum:** 2026-08-26  
**Status:** fachlich freigegeben  
**Ersetzt:** die widersprechenden Anforderungen des ursprünglichen Master-Prompts

## 1. Ziel und Abgrenzung

RotoMaskAnalyzer vergleicht künftig zwei Rotoskopievarianten mit einer manuell
erstellten Ground-Truth-Alpha-Maske. Die Alphawerte werden kontinuierlich im
Bereich `[0, 1]` ausgewertet und nicht binarisiert.

Das Tool misst bewusst ausschließlich Soft IoU. Änderungen in halbtransparenten
Kanten und Motion-Blur-Ausläufern beeinflussen diesen Wert, werden aber nicht als
eigene Fehlerart klassifiziert. Gradient-, Matting-, Kontur-, Optical-Flow- und
weitere Qualitätsmetriken bleiben außerhalb des Umfangs.

## 2. Eingabeschema

Ein Clip hat folgende für das Programm relevante Struktur:

```text
clip_01/
├── manual/
├── roto_raw/
└── roto_corrected/
```

- `manual` ist die Ground Truth.
- `roto_raw` und `roto_corrected` sind die auszuwertenden Varianten.
- Alle drei Ordner sind Pflichtordner.
- Ein eventuell vorhandener Ordner `original` ist kein Bestandteil des
  Programms. Er wird weder erkannt, validiert, abgeglichen, ausgewertet noch in
  Berichten oder Manifesten erwähnt.
- In allen drei Pflichtordnern müssen exakt dieselben PNG-Dateinamen vorhanden
  sein.
- Die bestehende Clip- und Frame-Erkennung bleibt erhalten: `clip_XX`,
  lückenlose Clip-Nummern, terminale und lückenlose Frame-Nummern sowie
  mindestens zwei Frames pro Clip.
- Korrespondierende Masken eines Frames müssen dieselbe Auflösung besitzen.

## 3. Maskenformat und Kanalregel

- Jede Maske muss eine RGBA-PNG mit vier Kanälen sein.
- 8-Bit- und 16-Bit-Samples bleiben erlaubt.
- Ausschließlich der Alphakanal wird verwendet. RGB wird unabhängig von seinem
  Inhalt vollständig ignoriert.
- Diese Regel gilt auch, wenn Alpha in einem Frame überall `0` oder überall auf
  dem maximalen Samplewert liegt.
- Graustufen-, Graustufen-Alpha-, RGB-, Paletten- und sonstige PNG-Formate ohne
  vierkanaliges RGBA werden mit einem konkreten Validierungsfehler abgelehnt.
- Alpha wird ohne Gamma- oder Farbprofiltransformation durch den Maximalwert der
  Bittiefe dividiert und so nach `[0, 1]` normalisiert.
- Es gibt keinen Maskenschwellenwert und keine binäre Repräsentation im
  Analysepfad.

## 4. Metrik

Für die manuelle Maske `M` und eine Roto-Maske `R` gilt pro Frame:

```text
soft_intersection = Σ min(M, R)
soft_union        = Σ max(M, R)
soft_iou          = soft_intersection / soft_union
```

Die Summen laufen über alle Pixel. Beide Eingaben müssen dieselbe Form haben und
endliche Werte in `[0, 1]` enthalten.

Sonderfälle:

- Sind `M` und `R` vollständig transparent, ist `soft_union = 0` und
  `soft_iou = 1.0`.
- Ist genau eine der Masken vollständig transparent, ist `soft_iou = 0.0`.
- Eine vollständig transparente `manual`-Maske ist deshalb gültig und blockiert
  die Analyse nicht.

Das Tool berechnet die Metrik getrennt für:

1. `manual` gegen `roto_raw`
2. `manual` gegen `roto_corrected`

## 5. Zeitliche Werte und Problemframes

Die bestehende zeitliche Logik wird auf Soft IoU übertragen:

```text
soft_iou_delta(t)  = soft_iou(t) - soft_iou(t-1)
soft_iou_change(t) = abs(soft_iou_delta(t))
```

Für den ersten Frame bleiben beide Werte leer beziehungsweise `null`.

Die Konfiguration enthält nur noch:

```json
{
  "schema_version": "2.0",
  "problem_frame_thresholds": {
    "soft_iou_below": 0.70,
    "soft_iou_change_above": 0.10
  }
}
```

Ein Frame ist problematisch, wenn mindestens eine der folgenden strikt
ausgewerteten Regeln gilt:

```text
soft_iou < soft_iou_below
soft_iou_change > soft_iou_change_above
```

Die Ursache-Codes lauten in stabiler Reihenfolge:

1. `low_soft_iou`
2. `high_soft_iou_change`

Die bestehende Bildung zusammenhängender Problemsequenzen bleibt erhalten.
FP-/FN-Regeln, -Schwellenwerte und -Ursache-Codes entfallen vollständig.

Eine vorhandene Konfiguration des alten Schemas wird nicht stillschweigend als
neue Konfiguration interpretiert. Die Anwendung erkennt sie eindeutig, ersetzt
sie durch das neue Standardschema und dokumentiert die Migration im sichtbaren
Validierungsstatus und in `validation_report.txt`. Die beiden gemeinsamen
Schwellenwerte werden dabei übernommen, sofern sie gültig sind:
`iou_below` wird zu `soft_iou_below`, `iou_change_above` wird zu
`soft_iou_change_above`. Nicht mehr relevante Werte werden verworfen.

## 6. Aggregation und Korrekturvergleich

Pro Variante bleiben folgende Aggregate erhalten:

- Mittelwert, Median, Minimum, Maximum und Populationsstandardabweichung von
  `soft_iou`
- Mittelwert und Maximum der vorhandenen `soft_iou_change`-Werte
- Anzahl und Anteil der Problemframes
- Länge der längsten Problemsequenz

Der Korrekturvergleich enthält:

- `mean_soft_iou_improvement = corrected_mean_soft_iou - raw_mean_soft_iou`
- Reduktion der Problemframe-Anzahl
- Reduktion des Problemframe-Anteils

FP-/FN-Aggregate und deren Korrekturänderungen entfallen.

## 7. Ergebnisdateien und Schemas

Die transaktionale Laufstruktur, CSV-Konventionen, Logs und sechs
Nachkommastellen bleiben bestehen. Zur klaren Trennung von alten binären
Ergebnissen verwendet das Manifest `schema_version = "2.0"`, und die Felder
tragen ausdrücklich den Präfix `soft_`.

### `frame_metrics.csv`

```csv
clip_id,variant,frame_number,filename,soft_iou,soft_iou_delta,soft_iou_change,is_problematic,problem_reasons
```

### `clip_summary.csv`

```csv
clip_id,variant,frame_count,mean_soft_iou,median_soft_iou,min_soft_iou,max_soft_iou,std_soft_iou,mean_soft_iou_change,max_soft_iou_change,problem_frame_count,problem_frame_ratio,longest_problem_sequence
```

### `problem_sequences.csv`

```csv
clip_id,variant,sequence_id,start_frame,end_frame,length,trigger_reasons,min_soft_iou,max_soft_iou_change
```

### `correction_summary.csv`

```csv
clip_id,mean_soft_iou_improvement,problem_frame_reduction,problem_frame_ratio_reduction
```

### `batch_summary.csv`

```csv
clip_id,frame_count,raw_mean_soft_iou,corrected_mean_soft_iou,mean_soft_iou_improvement,raw_problem_frame_count,corrected_problem_frame_count,problem_frame_reduction
```

Das Manifest nennt `manual` ausdrücklich als Ground Truth, dokumentiert die
Min-/Max-Formel sowie beide Sonderfälle und führt als Varianten `manual`,
`roto_raw` und `roto_corrected`. Es enthält keine Referenz auf `reference`,
`original`, Binarisierung, Maskenschwelle oder FP/FN.

## 8. Visualisierung und GUI

- Pro Clip wird weiterhin genau eine Zeitliniengrafik erzeugt. Sie heißt
  `soft_iou_timeline.png` und zeigt beide Varianten, die
  `soft_iou_below`-Linie und die Problemframes auf einer Y-Achse von `0` bis
  `1`.
- In der GUI entfällt das Eingabefeld für die Maskenschwelle.
- Sichtbar und editierbar bleiben nur `soft_iou_below` und
  `soft_iou_change_above`.
- Statusmeldungen, Validierungsübersicht, Hintergrundausführung, Abbruch und
  Öffnen des Ergebnisordners bleiben funktional unverändert.
- Deutsche Texte verwenden `manuelle Maske` beziehungsweise `Ground Truth` und
  vermeiden den alten Begriff `Referenzmaske`, wo dieser ein technisches
  Verzeichnis oder Feld bezeichnet.

## 9. Fehlerbehandlung

Die Analyse darf insbesondere nicht starten bei:

- fehlendem Pflichtordner,
- nicht identischen PNG-Dateisätzen,
- PNG ohne exaktes RGBA-Format,
- nicht unterstützter Bittiefe,
- beschädigter PNG,
- unterschiedlicher Auflösung korrespondierender Masken,
- ungültiger Clip- oder Frame-Nummerierung,
- ungültiger Konfiguration.

Vollständig transparente oder vollständig deckende Alphakanäle sind keine
Fehler oder Warnungen. Abbruch, unerwartete Fehler und transaktionales Cleanup
behalten das bisherige Verhalten bei.

## 10. Test- und Abnahmestrategie

Die Umsetzung erfolgt testgetrieben. Bestehende binäre Tests werden nicht nur
umbenannt, sondern durch handberechnete RGBA-/Soft-Alpha-Fälle ersetzt.

Mindestens abzudecken sind:

1. exakte Soft-IoU-Werte für kleine Matrizen mit Zwischenwerten,
2. perfekte Übereinstimmung, disjunkte Alpha-Massen und Teilüberlappung,
3. beide Masken leer ergibt `1.0`, nur eine leer ergibt `0.0`,
4. ausschließlich Alpha wird verwendet, auch bei überall `0` oder überall
   maximalem Alpha und beliebigem RGB,
5. verlustfreie Normalisierung von 8- und 16-Bit-RGBA,
6. Ablehnung aller nicht vierkanaligen RGBA-Formate,
7. ausschließlich die drei neuen Pflichtordner; `original` wird ignoriert,
8. neue Config einschließlich deterministischer Migration des alten Schemas,
9. beide Problemregeln und ihre strikt ausgewerteten Grenzen,
10. Aggregate, Korrekturvergleich und alle neuen CSV-Kopfzeilen,
11. Manifest 2.0 ohne alte Begriffe oder Metriken,
12. lesbare `soft_iou_timeline.png`,
13. vollständiger Integrationstest, Abbruchtest und Fehler-Cleanup,
14. GUI-Zustände mit genau zwei Schwellwerteingaben,
15. vollständige Testsuite, Lint, PyInstaller-Build und Windows-Smoke-Test.

## 11. Betroffene Komponenten

Die bestehende Trennung bleibt erhalten. Änderungen betreffen insbesondere:

- `discovery.py`: drei Pflichtordner
- `mask_io.py`: zwingendes RGBA, immer Alpha, keine Binarisierung
- `validation.py`: neues Schema und erlaubte leere `manual`-Frames
- `metrics.py`: Soft-IoU-Kern
- `domain.py`, `problem_detection.py`, `aggregation.py`: neue Felder und nur
  zwei Problemregeln
- `config.py` und GUI: neues Konfigurationsschema
- `outputs.py`, `manifest.py`, `visualization.py`: Schema 2.0 und Soft-Namen
- Analyseorchestrierung, README, Tests, Build und Smoke-Test

## 12. Erfolgskriterien

Die Änderung ist abgeschlossen, wenn ein Projekt mit `manual`, `roto_raw` und
`roto_corrected` vollständig validiert und auf Basis seiner RGBA-Alphakanäle
analysiert wird, alle Ergebnisse ausschließlich Soft IoU verwenden, kein alter
Analysepfad oder Exportbegriff verbleibt, alle Prüfungen erfolgreich sind und
die neu gebaute portable Windows-Anwendung den positiven und negativen
Smoke-Test besteht.
