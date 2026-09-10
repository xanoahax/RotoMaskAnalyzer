# Bachelorarbeit Neuanalyse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Den Arbeitsstand der Bachelorarbeit vom 06.09.2026, den Analyzer-Lauf 2026-09-06_1237 und alle aktuellen Bildsequenzen vollständig neu auswerten und als detaillierte, schreiborientierte PDF dokumentieren.

**Architecture:** Die Auswertung trennt Quelleninventur, unabhängige Neuberechnung, vollständige visuelle Frameprüfung, clipbezogene Interpretation und kapitelbezogene Schreibunterstützung. Frühere Analyseberichte werden nicht als Quelle verwendet. Die finale PDF wird aus reproduzierbaren Zwischenresultaten erzeugt und vollständig gerendert geprüft.

**Tech Stack:** Python 3.12, NumPy, Pillow, pandas, matplotlib, reportlab, pypdf, pdfplumber, Poppler

**Spec:** Freigegebener Analyseplan im Codex-Task vom 06.09.2026

## Global Constraints

- Ausschließlich Bachelorarbeit Stand 06.09.2026 und Analyzer-Lauf 2026-09-06_1237 verwenden.
- Alle 150 Framepositionen mit Original, manueller Referenz, Raw und korrigierter Maske visuell prüfen.
- Manuelle Maske als Referenz, nicht als objektive Ground Truth, behandeln.
- Globale quantitative Befunde und lokale visuelle Befunde getrennt berichten.
- Korrekturzeit und vollständigen Object-Matte-Workflow eindeutig unterscheiden.
- Fingerkuppen am Baumstamm in Clip 3 als Motivbestandteile behandeln.

---

### Task 1: Quellen- und Methodikaudit

**Files:**
- Read: `C:/Users/Noah Langthaler/Desktop/Bachelor Arbeit Versuch/Bachelorarbeit_mt231057_stand_06.09.2026.pdf`
- Read: `C:/Users/Noah Langthaler/Desktop/Bachelor Arbeit Versuch/project_config.json`
- Read: `C:/Users/Noah Langthaler/Desktop/Bachelor Arbeit Versuch/Definition der Zeiten.txt`

- [x] Gesamte Arbeit lesen und Kapitel 6 bis 9 strukturell prüfen.
- [x] Forschungsfragen, Messdefinitionen, Schwellenwerte und Aussagegrenzen extrahieren.
- [x] Textliche Lücken und Widersprüche mit konkreten Kapitelbezügen dokumentieren.

### Task 2: Quantitative Neuberechnung

**Files:**
- Read: `C:/Users/Noah Langthaler/Desktop/Bachelor Arbeit Versuch/clip_*/manual/*.png`
- Read: `C:/Users/Noah Langthaler/Desktop/Bachelor Arbeit Versuch/clip_*/roto_raw/*.png`
- Read: `C:/Users/Noah Langthaler/Desktop/Bachelor Arbeit Versuch/clip_*/roto_corrected/*.png`
- Read: `C:/Users/Noah Langthaler/Desktop/Bachelor Arbeit Versuch/results/2026-09-06_1237/**/*.csv`

- [x] Eingabedateien, Auflösung, Alphakanäle und Framezuordnung validieren.
- [x] Soft IoU und zeitliche Ableitungen unabhängig neu berechnen.
- [x] Ergebnisse gegen sämtliche Analyzer-Zusammenfassungen abgleichen.
- [x] Zeitersparnis und Beschleunigungsfaktoren aus den aktuellen Zeitdefinitionen berechnen.

### Task 3: Vollständige visuelle Analyse

**Files:**
- Read: `C:/Users/Noah Langthaler/Desktop/Bachelor Arbeit Versuch/clip_*/*/*.png`
- Read: `C:/Users/Noah Langthaler/Desktop/Bachelor Arbeit Versuch/viewer_screengrabs/*.png`

- [x] Für jeden Clip Kontaktbögen für alle 50 Framepositionen erzeugen.
- [x] Alle Kontaktbögen vollständig prüfen.
- [x] Auffällige Phasen und Einzelframes in Originalauflösung kontrollieren.
- [x] Untersegmentierung, Übersegmentierung, Kontur, feine Strukturen, Bewegungsunschärfe, Verdeckung und Jitter dokumentieren.

### Task 4: Analytische Synthese

- [x] Ergebnisse je Clip quantitativ und visuell zusammenführen.
- [x] Korrekturwirkung global, lokal und zeitlich unterscheiden.
- [x] Clipübergreifende Muster, Gegenbefunde und Limitationen ableiten.
- [x] Forschungsfrage und Teilfragen aus den Daten beantworten.

### Task 5: PDF erstellen

**Files:**
- Create: `C:/Users/Noah Langthaler/Documents/Bachelor_Mask Analyzer/output/pdf/Neuanalyse_Bachelorarbeit_Object_Matte_Stand_2026-09-06.pdf`

- [x] Diagramme, Tabellen und visuelle Vergleichstafeln erzeugen.
- [x] Bericht mit Kapitelaudit, Ergebnissen, Interpretation und Schreibunterstützung setzen.
- [x] PDF neu öffnen, Textextraktion und Seitenintegrität prüfen.
- [x] Alle Seiten rendern und visuell auf Layoutfehler kontrollieren.
