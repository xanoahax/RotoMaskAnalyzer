# RotoMaskAnalyzer 2.2.1

RotoMaskAnalyzer ist eine portable Windows-Desktop-Anwendung zur
reproduzierbaren Auswertung kontinuierlicher Rotoskopie-Alphamasken. Sie
vergleicht `roto_raw` und `roto_corrected` frameweise mit der manuellen Ground
Truth `manual` und erzeugt deterministische CSV-, JSON-, TXT- und PNG-Ergebnisse.

## Aktueller Stand

- Programmversion: `2.2.1`
- Ergebnisschema: `2.0`
- Plattform: Windows
- Unterstützte Python-Versionen: 3.11 bis 3.13
- Repository: [github.com/xanoahax/RotoMaskAnalyzer](https://github.com/xanoahax/RotoMaskAnalyzer)

## Eingabeprojekt

```text
project/
├── project_config.json          # wird bei Bedarf erstellt oder migriert
├── validation_report.txt        # wird bei jeder Prüfung ersetzt
├── clip_01/
│   ├── manual/
│   ├── roto_raw/
│   └── roto_corrected/
└── results/                     # wird bei Bedarf erstellt
```

Clips heißen exakt `clip_XX` und sind ab `clip_01` lückenlos nummeriert. Die
letzte Ziffernfolge vor `.png` ist die eindeutige, lückenlose Frame-Nummer. Die
Dateinamen dürfen je Pflichtordner unterschiedliche Präfixe besitzen; das
Programm ordnet sie anhand dieser terminalen Frame-Nummer einander zu. Zulässig
sind beispielsweise `clip_02_manual_00000.png`,
`clip_02_roto_raw_00000.png` und `clip_02_roto_corrected_00000.png`. Die drei
Ordner müssen exakt dieselben Frame-Nummern enthalten. Ein Clip benötigt
mindestens zwei Frames.

Ein privater Ordner namens `original` ist kein Bestandteil des Programms. Falls
er im Clip liegt, wird er vollständig ignoriert und weder validiert noch
ausgewertet oder dokumentiert.

## Maskenformat und Messung

Jede Maske muss eine vierkanalige RGBA-PNG mit 8 oder 16 Bit pro Sample sein.
Das Programm verwendet immer ausschließlich Alpha, auch wenn der Kanal überall
vollständig transparent oder deckend ist. RGB wird ignoriert. Andere
Kanalanordnungen werden als Validierungsfehler abgelehnt. Die gespeicherten
Alpha-Samples werden ohne Gamma- oder Farbprofiltransformation nach `[0, 1]`
normalisiert.

Für die manuelle Maske `M` und eine Roto-Maske `R` gilt:

```text
soft_iou = Σ min(M, R) / Σ max(M, R)
```

Sind beide Alphamasken vollständig transparent, ist Soft IoU `1,0`; ist genau
eine leer, ist der Wert `0,0`. Es gibt keine Maskenschwelle. Halbtransparente
Pixel gehen mit ihrem tatsächlichen Wert in die Messung ein.

Die Zeitwerte lauten:

```text
soft_iou_delta(t)  = soft_iou(t) - soft_iou(t-1)
soft_iou_change(t) = abs(soft_iou_delta(t))
```

## Konfiguration

```json
{
  "schema_version": "2.0",
  "problem_frame_thresholds": {
    "soft_iou_below": 0.7,
    "soft_iou_change_above": 0.1
  }
}
```

Alte Konfigurationen des vorherigen exakten Schemas werden einmalig migriert.
Die beiden weiterhin relevanten IoU-Schwellen werden übernommen, sofern sie
gültig sind; die Migration erscheint als Warnung im Validierungsbericht.

## Bedienung

1. `RotoMaskAnalyzer.exe` starten.
2. Projektordner auswählen; die vollständige Validierung startet automatisch
   im Hintergrund. Die Oberfläche bleibt dabei bedienbar und zeigt für jede
   geprüfte Datei einen Live-Log sowie den prozentualen Fortschritt. 8-Bit-PNGs
   werden über den schnellen, sample-exakten Decoder geprüft; der verlustfreie
   16-Bit-Pfad bleibt erhalten.
3. Die beiden Soft-IoU-Schwellen prüfen oder ändern.
4. Bei gültigem Projekt `Analyse starten` wählen.
5. Nach Erfolg den aktuellen Ergebnisordner öffnen.

Die Analyse läuft in einem Qt-Hintergrund-Thread. Bei Abbruch oder unerwartetem
Fehler verbleibt im aktuellen Laufordner ausschließlich `analysis_log.txt`;
frühere Läufe werden nicht verändert.

## Ergebnisstruktur

Jeder erfolgreiche Lauf liegt unter `results\YYYY-MM-DD_HHMM`; bei gleicher
Minute folgen `_02`, `_03` usw. Pro Clip entstehen:

```text
clip_XX/
├── clip_summary.csv
├── frame_metrics.csv
├── problem_sequences.csv
├── correction_summary.csv
└── visualizations/
    └── soft_iou_timeline.png
```

Auf Laufebene entstehen `analysis_manifest.json`, `analysis_log.txt` und
`batch_summary.csv`. Das Manifest verwendet Schema `2.0`. Alle CSV-Messwerte
haben sechs Nachkommastellen. Die CSV-Dateien sind für deutsches Excel als
UTF-8 mit BOM, Semikolon-Trennzeichen und Dezimalkomma formatiert. In
`frame_metrics.csv` bezeichnet `filename` den tatsächlichen Dateinamen der in
der jeweiligen Zeile analysierten Roto-Variante.

Die CSV-Kopfzeilen sind:

```text
frame_metrics.csv:
clip_id;variant;frame_number;filename;soft_iou;soft_iou_delta;soft_iou_change;is_problematic;problem_reasons

clip_summary.csv:
clip_id;variant;frame_count;mean_soft_iou;median_soft_iou;min_soft_iou;max_soft_iou;std_soft_iou;mean_soft_iou_change;max_soft_iou_change;problem_frame_count;problem_frame_ratio;longest_problem_sequence

problem_sequences.csv:
clip_id;variant;sequence_id;start_frame;end_frame;length;trigger_reasons;min_soft_iou;max_soft_iou_change

correction_summary.csv:
clip_id;mean_soft_iou_improvement;problem_frame_reduction;problem_frame_ratio_reduction

batch_summary.csv:
clip_id;frame_count;raw_mean_soft_iou;corrected_mean_soft_iou;mean_soft_iou_improvement;raw_problem_frame_count;corrected_problem_frame_count;problem_frame_reduction
```

## Entwicklungsumgebung

Voraussetzung: Windows, Git und Python 3.11 bis 3.13. Der geprüfte Build nutzt
Python 3.13.

```powershell
git clone https://github.com/xanoahax/RotoMaskAnalyzer.git
Set-Location RotoMaskAnalyzer
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
```

Anwendung aus dem Quellbaum starten:

```powershell
.\.venv\Scripts\python.exe -m rotomask_analyzer.app
```

## Verifikation

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m compileall -q src tests
```

## Windows-EXE

Der versionierte PyInstaller-Build erzeugt eine portable, fensterbasierte
Einzeldatei ohne Konsolenfenster:

```powershell
.\build_exe.ps1
```

Ergebnis:

```text
dist\RotoMaskAnalyzer.exe
```

Der interne Packaging-Testhook führt den vollständigen gebündelten Analysekern
auf einem Projekt aus und ist keine zweite Produktoberfläche:

```powershell
$env:ROTOMASK_ANALYZER_PACKAGING_SMOKE_PROJECT='C:\Pfad\zum\Testprojekt'
& .\dist\RotoMaskAnalyzer.exe
$LASTEXITCODE
Remove-Item Env:\ROTOMASK_ANALYZER_PACKAGING_SMOKE_PROJECT
```

Ein gültiges Projekt liefert Exitcode `0`; ein von der Validierung blockiertes
Projekt Exitcode `2`.
