# Soft Alpha Schema Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert RotoMaskAnalyzer from binary `reference`-based analysis to continuous RGBA-alpha Soft IoU analysis of `roto_raw` and `roto_corrected` against `manual`.

**Architecture:** Keep the existing separation between discovery/validation, pure numerical analysis, aggregation/output, orchestration, and PySide6 presentation. Replace the input and metric contracts at those boundaries, then update every dependent schema in one direction from core to UI. Preserve transactional results, cooperative cancellation, and the existing packaged-core smoke entry point.

**Tech Stack:** Python 3.11–3.13, NumPy 2.x, PyPNG, Pillow, pandas, Matplotlib, PySide6 6.x, pytest, pytest-qt, Ruff, PyInstaller 6.x, PowerShell on Windows

**Spec:** `docs/superpowers/specs/2026-08-26-soft-alpha-schema-design.md`

## Global Constraints

- `manual` is the only Ground Truth; evaluated variants are exactly `roto_raw` and `roto_corrected`.
- Required clip folders are exactly `manual`, `roto_raw`, and `roto_corrected`; `original` is ignored even when present.
- Mask input is 8- or 16-bit four-channel RGBA PNG; use Alpha unconditionally and ignore RGB.
- Do not binarize and do not retain `mask_threshold`, FP/FN metrics, FP/FN thresholds, or their problem reasons.
- The only spatial metric is `soft_iou = sum(min(M, R)) / sum(max(M, R))`.
- Define an empty/empty pair as `soft_iou = 1.0`; exactly one empty mask produces `0.0`.
- Results, config, and manifest use schema version `2.0`; application/package version becomes `2.0.0`.
- Output field names use `soft_iou`, `soft_iou_delta`, and `soft_iou_change` explicitly.
- Continue to emit deterministic UTF-8 CSV with comma delimiter, CRLF, and exactly six decimal places.
- Preserve background execution, progress, cancellation, logging, transactional output, and cleanup semantics.
- Do not add gradient, matting, contour, Optical Flow, or other quality metrics.
- The workspace currently has no `.git` directory. Do not initialize Git implicitly. Each checkpoint command commits only if the user has initialized a repository by execution time; otherwise it prints the intended commit boundary and continues.

## File Structure

No new runtime module is needed. Modify the existing files along their current responsibilities:

- `src/rotomask_analyzer/config.py`: schema 2.0 defaults, validation, deterministic legacy migration callback.
- `src/rotomask_analyzer/discovery.py`: three-mask-folder frame discovery.
- `src/rotomask_analyzer/mask_io.py`: lossless RGBA Alpha decoding without thresholding.
- `src/rotomask_analyzer/validation.py`: validate only the three RGBA mask streams and report config migration.
- `src/rotomask_analyzer/domain.py`: Soft-IoU-specific immutable result fields.
- `src/rotomask_analyzer/metrics.py`: pure Soft IoU and temporal calculations.
- `src/rotomask_analyzer/problem_detection.py`: two Soft-IoU problem rules and sequence construction.
- `src/rotomask_analyzer/aggregation.py`: Soft-IoU summaries and correction comparison.
- `src/rotomask_analyzer/outputs.py`: schema 2.0 CSV headers and values.
- `src/rotomask_analyzer/manifest.py`: schema 2.0 scientific definitions and Ground Truth role.
- `src/rotomask_analyzer/visualization.py`: `soft_iou_timeline.png`.
- `src/rotomask_analyzer/analysis_service.py`: normalized Alpha data flow and new result filename.
- `src/rotomask_analyzer/gui/main_window.py`: exactly two problem threshold controls.
- `src/rotomask_analyzer/app.py`: retain the packaged-core smoke interface with schema 2.0 config.
- `src/rotomask_analyzer/version.py`, `pyproject.toml`, `README.md`: version and user/build documentation.
- `tests/conftest.py`: reusable RGBA projects with deterministic Alpha values.
- Existing unit, integration, and GUI tests: replace binary/reference assumptions with hand-computed Soft-Alpha cases.

---

### Task 1: Configuration Schema 2.0 and Legacy Migration

**Files:**
- Modify: `src/rotomask_analyzer/config.py`
- Modify: `tests/unit/test_config.py`

**Interfaces:**
- Produces: `DEFAULT_CONFIG` with `schema_version == "2.0"` and two Soft-IoU thresholds.
- Produces: `validate_config(config: object) -> dict[str, Any]`.
- Produces: `load_config(path: Path, *, create_if_missing: bool = False, on_migration: Callable[[str], None] | None = None) -> dict[str, Any]`.
- Consumed later by: validation, GUI, analysis service, manifest, and packaged smoke.

- [ ] **Step 1: Replace config tests with schema 2.0 expectations**

Use exact expectations such as:

```python
EXPECTED = {
    "schema_version": "2.0",
    "problem_frame_thresholds": {
        "soft_iou_below": 0.70,
        "soft_iou_change_above": 0.10,
    },
}


def test_defaults_are_schema_2_soft_iou_only():
    assert DEFAULT_CONFIG == EXPECTED


@pytest.mark.parametrize("name", ["soft_iou_below", "soft_iou_change_above"])
def test_thresholds_must_be_finite_unit_interval(name):
    config = copy.deepcopy(EXPECTED)
    config["problem_frame_thresholds"][name] = math.nan
    with pytest.raises(ConfigError, match=f"{name} muss endlich sein"):
        validate_config(config)


def test_exact_legacy_schema_is_migrated_and_reported(tmp_path):
    path = tmp_path / "project_config.json"
    path.write_text(json.dumps({
        "mask_threshold": 0.5,
        "problem_frame_thresholds": {
            "iou_below": 0.62,
            "iou_change_above": 0.08,
            "false_positive_ref_ratio_above": 0.15,
            "false_negative_ref_ratio_above": 0.15,
        },
    }), encoding="utf-8")
    notes = []
    loaded = load_config(path, on_migration=notes.append)
    assert loaded["problem_frame_thresholds"] == {
        "soft_iou_below": 0.62,
        "soft_iou_change_above": 0.08,
    }
    assert len(notes) == 1
    assert json.loads(path.read_text(encoding="utf-8")) == loaded
```

Also test that an invalid legacy shared value falls back to its new default, while malformed JSON and arbitrary unknown schemas still raise `ConfigError`.

- [ ] **Step 2: Run the focused tests and verify the old schema fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_config.py -v
```

Expected: failures mention missing `schema_version`, unexpected old keys, or unsupported `on_migration`.

- [ ] **Step 3: Implement exact new-schema validation and deterministic legacy migration**

Use an exact-key contract. Add helpers with these semantics:

```python
DEFAULT_CONFIG = {
    "schema_version": "2.0",
    "problem_frame_thresholds": {
        "soft_iou_below": 0.70,
        "soft_iou_change_above": 0.10,
    },
}

LEGACY_TOP_KEYS = {"mask_threshold", "problem_frame_thresholds"}
LEGACY_THRESHOLD_KEYS = {
    "iou_below",
    "iou_change_above",
    "false_positive_ref_ratio_above",
    "false_negative_ref_ratio_above",
}


def _is_exact_legacy_schema(data: object) -> bool:
    return (
        isinstance(data, dict)
        and set(data) == LEGACY_TOP_KEYS
        and isinstance(data.get("problem_frame_thresholds"), dict)
        and set(data["problem_frame_thresholds"]) == LEGACY_THRESHOLD_KEYS
    )


def _migrate_legacy(data: dict[str, Any]) -> dict[str, Any]:
    old = data["problem_frame_thresholds"]
    migrated = copy.deepcopy(DEFAULT_CONFIG)
    for old_name, new_name in (
        ("iou_below", "soft_iou_below"),
        ("iou_change_above", "soft_iou_change_above"),
    ):
        try:
            value = _finite_number(old[old_name], old_name)
            _require_unit_interval(value, old_name)
        except ConfigError:
            continue
        migrated["problem_frame_thresholds"][new_name] = value
    return migrated
```

In `load_config`, detect the exact legacy shape before `validate_config`, save the migrated object atomically through `save_config`, and call `on_migration("project_config.json wurde von Schema 1 auf Schema 2.0 migriert.")` exactly once when supplied. Do not migrate arbitrary malformed objects.

- [ ] **Step 4: Run focused tests to verify schema and migration pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_config.py -v
```

Expected: all config tests pass.

- [ ] **Step 5: Record the configuration checkpoint**

Run:

```powershell
if (Test-Path -LiteralPath .git) {
    git add src/rotomask_analyzer/config.py tests/unit/test_config.py
    git commit -m "feat: migrate configuration to soft alpha schema"
} else {
    Write-Host "Checkpoint: feat: migrate configuration to soft alpha schema (Git unavailable)"
}
```

---

### Task 2: Three-Folder RGBA Discovery and Validation

**Files:**
- Modify: `src/rotomask_analyzer/discovery.py`
- Modify: `src/rotomask_analyzer/mask_io.py`
- Modify: `src/rotomask_analyzer/validation.py`
- Modify: `tests/conftest.py`
- Modify: `tests/unit/test_discovery.py`
- Modify: `tests/unit/test_mask_io.py`
- Modify: `tests/unit/test_validation.py`
- Modify: `tests/unit/test_app.py`

**Interfaces:**
- Produces: `discover_frames()` paths with keys `manual`, `roto_raw`, `roto_corrected` only.
- Produces: `MaskData(alpha: np.ndarray, bit_depth: int)`.
- Produces: `read_mask(path: Path) -> MaskData`; there is no threshold parameter.
- Produces: validation warning code `config_migrated` with `severity="warning"`.
- Consumes: schema 2.0 `load_config(..., on_migration=...)` from Task 1.

- [ ] **Step 1: Rebuild test fixtures as RGBA mask projects**

Make `tests/conftest.py` create only the three required directories and write deterministic Alpha while keeping arbitrary colored RGB:

```python
def write_rgba_mask(
    path: Path,
    *,
    size: tuple[int, int] = (4, 3),
    alpha_value: int = 255,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rgba = np.zeros((size[1], size[0], 4), dtype=np.uint8)
    rgba[:, :, :3] = (10, 20, 30)
    rgba[:, :, 3] = alpha_value
    Image.fromarray(rgba, mode="RGBA").save(path)


@pytest.fixture
def project_factory(tmp_path):
    def create(clips=("clip_01",), frames=("frame_0001.png", "frame_0002.png"), sizes=None):
        project = tmp_path / "ExampleProject"
        for clip_id in clips:
            size = (sizes or {}).get(clip_id, (4, 3))
            for folder in ("manual", "roto_raw", "roto_corrected"):
                for filename in frames:
                    write_rgba_mask(project / clip_id / folder / filename, size=size)
        return project
    return create
```

Update direct test paths from `reference` to `manual`. Add a discovery test that creates an unrelated `original/frame_9999.png` and proves it does not affect discovered frames.

- [ ] **Step 2: Add lossless Alpha-only decoder tests**

Cover exact RGBA requirements and uniform Alpha:

```python
def test_rgba_uses_alpha_even_when_rgb_is_colored(tmp_path):
    path = tmp_path / "mask.png"
    Image.fromarray(np.array([[[10, 20, 30, 0], [200, 2, 90, 128], [4, 5, 6, 255]]], dtype=np.uint8), "RGBA").save(path)
    mask = read_mask(path)
    np.testing.assert_allclose(mask.alpha, [[0.0, 128 / 255, 1.0]])
    assert mask.bit_depth == 8


@pytest.mark.parametrize("alpha", [0, 255])
def test_uniform_alpha_is_used_without_rgb_fallback(tmp_path, alpha):
    path = tmp_path / f"uniform_{alpha}.png"
    Image.new("RGBA", (2, 1), (10, 20, 30, alpha)).save(path)
    np.testing.assert_allclose(read_mask(path).alpha, alpha / 255)


@pytest.mark.parametrize("mode", ["L", "LA", "RGB", "P"])
def test_every_non_rgba_layout_is_rejected(tmp_path, mode):
    path = tmp_path / f"{mode}.png"
    Image.new(mode, (2, 1)).save(path)
    with pytest.raises(MaskFormatError, match="RGBA"):
        read_mask(path)
```

Retain a PyPNG-generated 16-bit RGBA test and assert the exact normalized values `32767 / 65535`, `32768 / 65535`, and `1.0`.

- [ ] **Step 3: Add validation tests for the new contract**

Add assertions for:

```python
def test_original_folder_is_completely_ignored(project_factory):
    project = project_factory()
    original = project / "clip_01/original/unmatched_9999.png"
    original.parent.mkdir(parents=True)
    Image.new("L", (99, 99)).save(original)
    result = validate_project(project)
    assert result.valid
    assert "original" not in (project / "validation_report.txt").read_text(encoding="utf-8")


def test_empty_and_full_manual_alpha_are_valid(project_factory):
    project = project_factory()
    for index, value in enumerate((0, 255), start=1):
        write_rgba_mask(project / f"clip_01/manual/frame_{index:04d}.png", alpha_value=value)
    assert validate_project(project).valid
```

Also assert missing `manual`, mismatched three-folder filenames, corrupt RGBA, non-RGBA PNG, and resolution mismatch are blocking errors. Verify a migrated config creates one `config_migrated` warning, remains globally valid, is visible in `ValidationResult.issues`, and appears in `validation_report.txt`.

- [ ] **Step 4: Run input tests and verify they fail against the old four-folder reader**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_discovery.py tests\unit\test_mask_io.py tests\unit\test_validation.py tests\unit\test_app.py -v
```

Expected: failures reference missing `reference`/`original`, old threshold arguments, or accepted non-RGBA input.

- [ ] **Step 5: Implement three-folder discovery**

In `discover_frames`, set:

```python
variants = ("manual", "roto_raw", "roto_corrected")
baseline = filename_sets["manual"]
```

Build `FrameSet.paths` from only those keys. Leave clip numbering and terminal frame-number rules unchanged. Extra directories are not enumerated and therefore cannot influence validation.

- [ ] **Step 6: Implement unconditional lossless RGBA Alpha reading**

Replace `MaskData` and `read_mask` with the narrow contract:

```python
@dataclass(frozen=True)
class MaskData:
    alpha: np.ndarray
    bit_depth: int


def read_mask(path: Path) -> MaskData:
    width, height, rows, info = png.Reader(filename=str(path)).read()
    bit_depth = int(info["bitdepth"])
    if bit_depth not in {8, 16}:
        raise MaskFormatError("unsupported_mask_bit_depth", ...)
    if info.get("palette") is not None or bool(info["greyscale"]) or not bool(info["alpha"]) or int(info["planes"]) != 4:
        raise MaskFormatError("mask_must_be_rgba", f"Maske {path.name} muss eine vierkanalige RGBA-PNG sein.")
    dtype = np.uint16 if bit_depth == 16 else np.uint8
    samples = np.vstack([np.asarray(row, dtype=dtype) for row in rows]).reshape(height, width, 4)
    maximum = float((1 << bit_depth) - 1)
    return MaskData(alpha=samples[:, :, 3].astype(np.float64) / maximum, bit_depth=bit_depth)
```

Preserve the existing exception translation to `unreadable_png`. Remove grayscale fallback, `source_channel`, threshold, and `binary` completely.

- [ ] **Step 7: Implement three-stream validation and migration reporting**

Collect config migration notes before reading clips:

```python
migration_notes: list[str] = []
config = load_config(
    project_path / "project_config.json",
    create_if_missing=True,
    on_migration=migration_notes.append,
)
issues.extend(
    ValidationIssue("config_migrated", note, severity="warning")
    for note in migration_notes
)
```

For every discovered path, call `read_mask(path)` exactly once, derive size from `mask.alpha.shape` as `(width, height)`, and collect its bit depth. Remove the empty-reference check. In the report, print `Geprüfte Pflichtordner: manual, roto_raw, roto_corrected`, `schema_version`, and only the two Soft-IoU threshold values.

- [ ] **Step 8: Run focused input and validation tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_discovery.py tests\unit\test_mask_io.py tests\unit\test_validation.py tests\unit\test_app.py -v
```

Expected: all selected tests pass.

- [ ] **Step 9: Record the input-contract checkpoint**

Run:

```powershell
if (Test-Path -LiteralPath .git) {
    git add src/rotomask_analyzer/discovery.py src/rotomask_analyzer/mask_io.py src/rotomask_analyzer/validation.py tests/conftest.py tests/unit/test_discovery.py tests/unit/test_mask_io.py tests/unit/test_validation.py tests/unit/test_app.py
    git commit -m "feat: validate three rgba alpha streams"
} else {
    Write-Host "Checkpoint: feat: validate three rgba alpha streams (Git unavailable)"
}
```

---

### Task 3: Soft IoU Domain, Metrics, Problems, and Aggregation

**Files:**
- Modify: `src/rotomask_analyzer/domain.py`
- Modify: `src/rotomask_analyzer/metrics.py`
- Modify: `src/rotomask_analyzer/problem_detection.py`
- Modify: `src/rotomask_analyzer/aggregation.py`
- Modify: `tests/unit/test_metrics.py`
- Modify: `tests/unit/test_problem_detection.py`
- Modify: `tests/unit/test_aggregation.py`

**Interfaces:**
- Produces: `compute_soft_iou(manual: np.ndarray, roto: np.ndarray) -> float`.
- Produces: `temporal_metrics(soft_ious: list[float]) -> list[tuple[float | None, float | None]]`.
- Produces: `FrameMetric` fields `soft_iou`, `soft_iou_delta`, `soft_iou_change`.
- Produces: matching `ProblemSequence`, `VariantSummary`, and `CorrectionSummary` Soft-IoU fields.
- Consumed later by: outputs, visualization, manifest, and analysis service.

- [ ] **Step 1: Write hand-computed Soft IoU tests**

Use values whose result is independently calculable:

```python
def test_fractional_alpha_uses_min_max_soft_iou():
    manual = np.array([[0.0, 0.25], [0.5, 1.0]])
    roto = np.array([[0.0, 0.75], [0.25, 1.0]])
    # min sum = 0 + .25 + .25 + 1 = 1.5
    # max sum = 0 + .75 + .5 + 1 = 2.25
    assert compute_soft_iou(manual, roto) == pytest.approx(2 / 3)


def test_both_empty_is_perfect_and_one_empty_is_zero():
    empty = np.zeros((2, 2))
    nonempty = np.array([[0.0, 0.5], [0.0, 0.0]])
    assert compute_soft_iou(empty, empty) == 1.0
    assert compute_soft_iou(empty, nonempty) == 0.0
    assert compute_soft_iou(nonempty, empty) == 0.0


@pytest.mark.parametrize("bad", [np.array([[np.nan]]), np.array([[np.inf]]), np.array([[-0.1]]), np.array([[1.1]])])
def test_soft_iou_rejects_nonfinite_or_out_of_range_values(bad):
    with pytest.raises(ValueError):
        compute_soft_iou(np.zeros_like(bad), bad)
```

Retain temporal tests but rename their data to Soft IoU and keep exact signed delta rounding.

- [ ] **Step 2: Write new domain/problem/aggregation tests**

Construct `FrameMetric` with only these metric fields:

```python
FrameMetric(
    clip_id="clip_01",
    variant="roto_raw",
    frame_number=2,
    filename="frame_0002.png",
    soft_iou=0.60,
    soft_iou_delta=-0.20,
    soft_iou_change=0.20,
)
```

Assert strict boundaries and reason order:

```python
THRESHOLDS = {"soft_iou_below": 0.70, "soft_iou_change_above": 0.10}
assert detect_problem_reasons(metric_at_exact_boundaries, THRESHOLDS) == ()
assert detect_problem_reasons(metric_below_and_changed, THRESHOLDS) == (
    "low_soft_iou",
    "high_soft_iou_change",
)
```

Aggregate `[1.0, 0.5, 0.0]` and assert mean/median `0.5`, population standard deviation `0.408248290463863`, temporal mean/max, problem counts, and longest sequence. Compare raw mean `0.5` with corrected mean `0.9` and assert `mean_soft_iou_improvement == 0.4` with no FP/FN attributes.

- [ ] **Step 3: Run core tests and verify failures**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_metrics.py tests\unit\test_problem_detection.py tests\unit\test_aggregation.py -v
```

Expected: failures identify missing `compute_soft_iou` and old domain fields.

- [ ] **Step 4: Replace binary spatial metrics with validated Soft IoU**

Implement:

```python
def compute_soft_iou(manual: np.ndarray, roto: np.ndarray) -> float:
    manual = np.asarray(manual, dtype=np.float64)
    roto = np.asarray(roto, dtype=np.float64)
    if manual.shape != roto.shape:
        raise ValueError("Manuelle und Roto-Maske müssen dieselbe Form besitzen.")
    if manual.ndim != 2:
        raise ValueError("Alpha-Masken müssen zweidimensional sein.")
    if not np.isfinite(manual).all() or not np.isfinite(roto).all():
        raise ValueError("Alpha-Masken müssen ausschließlich endliche Werte enthalten.")
    if np.any((manual < 0) | (manual > 1)) or np.any((roto < 0) | (roto > 1)):
        raise ValueError("Alpha-Maskenwerte müssen in [0, 1] liegen.")
    soft_union = float(np.maximum(manual, roto).sum(dtype=np.float64))
    if soft_union == 0.0:
        return 1.0
    soft_intersection = float(np.minimum(manual, roto).sum(dtype=np.float64))
    return soft_intersection / soft_union
```

Delete `SpatialMetrics`, bool coercion, and all FP/FN calculations. Keep `temporal_metrics` as the single implementation of delta/change logic.

- [ ] **Step 5: Rename domain records consistently**

Define exactly:

```python
@dataclass
class FrameMetric:
    clip_id: str
    variant: str
    frame_number: int
    filename: str
    soft_iou: float
    soft_iou_delta: float | None
    soft_iou_change: float | None
    is_problematic: bool = False
    problem_reasons: tuple[str, ...] = ()
```

Rename `ProblemSequence.min_iou`/`max_iou_change` to `min_soft_iou`/`max_soft_iou_change`; rename all IoU fields in `VariantSummary` with the `soft_` prefix; and reduce `CorrectionSummary` to `clip_id`, `mean_soft_iou_improvement`, `problem_frame_reduction`, and `problem_frame_ratio_reduction`.

Use these exact record shapes:

```python
@dataclass(frozen=True)
class ProblemSequence:
    clip_id: str
    variant: str
    sequence_id: int
    start_frame: int
    end_frame: int
    length: int
    trigger_reasons: tuple[str, ...]
    min_soft_iou: float
    max_soft_iou_change: float | None


@dataclass(frozen=True)
class VariantSummary:
    clip_id: str
    variant: str
    frame_count: int
    mean_soft_iou: float
    median_soft_iou: float
    min_soft_iou: float
    max_soft_iou: float
    std_soft_iou: float
    mean_soft_iou_change: float | None
    max_soft_iou_change: float | None
    problem_frame_count: int
    problem_frame_ratio: float
    longest_problem_sequence: int


@dataclass(frozen=True)
class CorrectionSummary:
    clip_id: str
    mean_soft_iou_improvement: float
    problem_frame_reduction: int
    problem_frame_ratio_reduction: float
```

- [ ] **Step 6: Reduce problem rules and aggregation to Soft IoU**

Set:

```python
REASON_ORDER = ("low_soft_iou", "high_soft_iou_change")
```

Use only the two strict rules. Sequence construction takes its minimum from `metric.soft_iou` and changes from `metric.soft_iou_change`. Aggregation uses NumPy over `soft_iou` only and returns the renamed summary fields. Correction comparison computes corrected minus raw for mean Soft IoU and raw minus corrected for problem reductions.

- [ ] **Step 7: Run focused core tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_metrics.py tests\unit\test_problem_detection.py tests\unit\test_aggregation.py -v
```

Expected: all selected tests pass.

- [ ] **Step 8: Record the numerical-core checkpoint**

Run:

```powershell
if (Test-Path -LiteralPath .git) {
    git add src/rotomask_analyzer/domain.py src/rotomask_analyzer/metrics.py src/rotomask_analyzer/problem_detection.py src/rotomask_analyzer/aggregation.py tests/unit/test_metrics.py tests/unit/test_problem_detection.py tests/unit/test_aggregation.py
    git commit -m "feat: compute and aggregate soft iou"
} else {
    Write-Host "Checkpoint: feat: compute and aggregate soft iou (Git unavailable)"
}
```

---

### Task 4: Schema 2.0 CSV, Manifest, and Timeline

**Files:**
- Modify: `src/rotomask_analyzer/outputs.py`
- Modify: `src/rotomask_analyzer/manifest.py`
- Modify: `src/rotomask_analyzer/visualization.py`
- Modify: `tests/unit/test_outputs.py`
- Modify: `tests/unit/test_manifest.py`
- Modify: `tests/unit/test_visualization.py`

**Interfaces:**
- Consumes: Soft-IoU domain records from Task 3 and schema 2.0 config from Task 1.
- Produces: deterministic CSV schemas from design section 7.
- Produces: `build_manifest(...)` with manifest `schema_version == "2.0"`.
- Produces: `write_soft_iou_timeline(path, clip_id, metrics, summaries, *, soft_iou_below)`.

- [ ] **Step 1: Replace output snapshot expectations with exact new headers**

Assert headers literally, including:

```python
assert rows[0] == [
    "clip_id", "variant", "frame_number", "filename", "soft_iou",
    "soft_iou_delta", "soft_iou_change", "is_problematic", "problem_reasons",
]
assert rows[1][4:7] == ["0.666667", "", ""]
```

Add exact expectations for `clip_summary.csv`, `problem_sequences.csv`, `correction_summary.csv`, and `batch_summary.csv` from the design. Assert obsolete strings `false_positive`, `false_negative`, and `reference` do not appear in any generated CSV.

- [ ] **Step 2: Replace manifest expectations with scientific schema 2.0**

Assert exact key content:

```python
assert manifest["schema_version"] == "2.0"
assert manifest["variants"] == ["manual", "roto_raw", "roto_corrected"]
assert manifest["ground_truth_role"] == "manual dient als Ground Truth der Auswertung"
assert manifest["metric_definitions"] == {
    "soft_iou": "sum(min(M, R)) / sum(max(M, R)); bei Union 0 gilt 1.0",
    "soft_iou_delta": "soft_iou(t) - soft_iou(t-1)",
    "soft_iou_change": "abs(soft_iou_delta)",
}
assert manifest["problem_frames"]["reason_codes"] == [
    "low_soft_iou", "high_soft_iou_change"
]
```

Serialize the JSON and assert it contains none of `reference`, `original`, `mask_threshold`, `false_positive`, `false_negative`, or `binar` case-insensitively.

- [ ] **Step 3: Update timeline tests**

Call `write_soft_iou_timeline` with Soft-IoU domain records. Assert the PNG exists, has nonzero dimensions, the figure is closed, and the target filename used by integration is `soft_iou_timeline.png`.

- [ ] **Step 4: Run focused output tests and verify failures**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_outputs.py tests\unit\test_manifest.py tests\unit\test_visualization.py -v
```

Expected: failures show old CSV fields, manifest schema 1.0, and missing renamed timeline function.

- [ ] **Step 5: Implement the five exact CSV schemas**

Replace headers and row mappings field-for-field from design section 7. Keep `_float`, `_write_csv`, sort order `roto_raw` then `roto_corrected`, CRLF, and six decimal places unchanged. Remove every FP/FN column and access.

- [ ] **Step 6: Implement manifest schema 2.0**

Build only the new variant list, config, Soft-IoU definitions, two problem rules, two reason codes, Ground Truth statement, validation status, clips, timestamp, and software version. Avoid compatibility aliases to old field names because old and new numerical results are not semantically interchangeable.

- [ ] **Step 7: Rename and update the timeline writer**

Rename the function to `write_soft_iou_timeline`; plot `row.soft_iou`; read `summary.mean_soft_iou`; label title, axis, and threshold as `Soft IoU`; retain fixed `[0, 1]` Y range, two lines, problem markers, headless Agg backend, and figure cleanup.

- [ ] **Step 8: Run focused output tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_outputs.py tests\unit\test_manifest.py tests\unit\test_visualization.py -v
```

Expected: all selected tests pass.

- [ ] **Step 9: Record the output-schema checkpoint**

Run:

```powershell
if (Test-Path -LiteralPath .git) {
    git add src/rotomask_analyzer/outputs.py src/rotomask_analyzer/manifest.py src/rotomask_analyzer/visualization.py tests/unit/test_outputs.py tests/unit/test_manifest.py tests/unit/test_visualization.py
    git commit -m "feat: export soft iou schema 2 results"
} else {
    Write-Host "Checkpoint: feat: export soft iou schema 2 results (Git unavailable)"
}
```

---

### Task 5: End-to-End Analysis Service and Transactional Results

**Files:**
- Modify: `src/rotomask_analyzer/analysis_service.py`
- Modify: `src/rotomask_analyzer/app.py` only if signature changes require it
- Modify: `tests/integration/test_successful_run.py`
- Modify: `tests/integration/test_cancelled_run.py`
- Modify: `tests/integration/test_failed_run_cleanup.py`

**Interfaces:**
- Consumes: `read_mask(path).alpha`, `compute_soft_iou`, `temporal_metrics`, Soft-IoU domain/output APIs.
- Produces: the unchanged public `AnalysisService.run(...) -> AnalysisRunResult` contract.
- Produces: successful result trees containing `soft_iou_timeline.png` and schema 2.0 files.
- Preserves: `ROTOMASK_ANALYZER_PACKAGING_SMOKE_PROJECT` behavior in `app.py`.

- [ ] **Step 1: Rewrite successful-run integration assertions**

Create RGBA masks with intermediate Alpha that produce different hand-computed raw and corrected scores. Assert:

```python
assert (run_dir / "clip_01/visualizations/soft_iou_timeline.png").is_file()
assert not (run_dir / "clip_01/visualizations/iou_timeline.png").exists()
manifest = json.loads((run_dir / "analysis_manifest.json").read_text(encoding="utf-8"))
assert manifest["schema_version"] == "2.0"
rows = list(csv.DictReader((run_dir / "clip_01/frame_metrics.csv").open(encoding="utf-8")))
assert len(rows) == frame_count * 2
assert set(rows[0]) == {
    "clip_id", "variant", "frame_number", "filename", "soft_iou",
    "soft_iou_delta", "soft_iou_change", "is_problematic", "problem_reasons",
}
```

Keep checks for 100% only after finalization, previous run preservation, and valid logs.

- [ ] **Step 2: Retain cancellation and failure cleanup tests with RGBA fixtures**

For both cancellation and injected `after_frame`/`before_verification` failures, assert the current run directory contains exactly `analysis_log.txt`, previous successful runs remain unchanged, and the log has the correct terminal status.

- [ ] **Step 3: Run integration tests and verify the old orchestration fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\integration -v
```

Expected: failures reference `frame.paths["reference"]`, threshold arguments, old metric objects, or the old timeline filename.

- [ ] **Step 4: Rewire frame analysis to normalized Alpha and Soft IoU**

Inside each variant loop, compute all spatial values first and then obtain all
temporal values from the pure `temporal_metrics` function so delta logic has one
implementation:

```python
scored_frames: list[tuple[FrameSet, float]] = []
for position, frame in enumerate(frames, start=1):
    _raise_if_cancelled(cancel_check)
    manual = read_mask(frame.paths["manual"]).alpha
    roto = read_mask(frame.paths[variant]).alpha
    scored_frames.append((frame, compute_soft_iou(manual, roto)))
    completed_pairs += 1
    status = f"{clip.clip_id} – Frame {position}/{len(frames)} – {variant}"
    percent = min(95, int(completed_pairs / total_pairs * 95))
    progress_callback(percent, status)
    logger.write(f"Fortschritt: {percent}% – {status}")
    fault_injector("after_frame")

temporal = temporal_metrics([soft_iou for _, soft_iou in scored_frames])
for (frame, soft_iou), (soft_iou_delta, soft_iou_change) in zip(
    scored_frames, temporal, strict=True
):
    metric = FrameMetric(
        clip_id=clip.clip_id,
        variant=variant,
        frame_number=frame.number,
        filename=frame.filename,
        soft_iou=soft_iou,
        soft_iou_delta=soft_iou_delta,
        soft_iou_change=soft_iou_change,
    )
    metric.problem_reasons = detect_problem_reasons(
        metric, config["problem_frame_thresholds"]
    )
    metric.is_problematic = bool(metric.problem_reasons)
    variant_metrics.append(metric)
```

Use the new problem thresholds and renamed output/timeline writer. Change output verification to require `visualizations/soft_iou_timeline.png`. Keep total work units at `frames * 2`, cleanup, exception wrapping, and transactional move behavior unchanged.

- [ ] **Step 5: Run all integration tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\integration -v
```

Expected: all integration tests pass.

- [ ] **Step 6: Record the orchestration checkpoint**

Run:

```powershell
if (Test-Path -LiteralPath .git) {
    git add src/rotomask_analyzer/analysis_service.py src/rotomask_analyzer/app.py tests/integration
    git commit -m "feat: run transactional soft alpha analysis"
} else {
    Write-Host "Checkpoint: feat: run transactional soft alpha analysis (Git unavailable)"
}
```

---

### Task 6: Two-Threshold PySide6 Interface

**Files:**
- Modify: `src/rotomask_analyzer/gui/main_window.py`
- Modify: `tests/gui/test_main_window.py`

**Interfaces:**
- Consumes: schema 2.0 config and unchanged `ValidationResult`/worker APIs.
- Produces: `threshold_inputs` with exactly `soft_iou_below` and `soft_iou_change_above`.
- Preserves: project selection, validation display, worker thread, progress, cancellation, and open-results state machine.

- [ ] **Step 1: Write GUI tests for exactly two controls**

Assert:

```python
assert set(window.threshold_inputs) == {"soft_iou_below", "soft_iou_change_above"}
assert window.threshold_inputs["soft_iou_below"].value() == 0.70
assert window.threshold_inputs["soft_iou_change_above"].value() == 0.10
assert window._current_config() == {
    "schema_version": "2.0",
    "problem_frame_thresholds": {
        "soft_iou_below": 0.70,
        "soft_iou_change_above": 0.10,
    },
}
```

Update fake validation configs to schema 2.0. Retain existing state-machine tests for disabled/enabled controls, progress, cancel, success, and failure.

- [ ] **Step 2: Run GUI tests and verify old five-control UI fails**

Run:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m pytest tests\gui\test_main_window.py -v
```

Expected: failures show five old keys and old config shape.

- [ ] **Step 3: Implement the two Soft-IoU controls**

Replace threshold definitions with:

```python
threshold_definitions = [
    ("soft_iou_below", "Problemframe: Soft IoU unter", 0.0, 1.0, 0.70),
    ("soft_iou_change_above", "Problemframe: Soft-IoU-Änderung über", 0.0, 1.0, 0.10),
]
```

Remove the unused `sys` import. `_load_thresholds` iterates only the nested threshold mapping. `_current_config` returns `schema_version: "2.0"` and the two controls. Warning issues such as `config_migrated` remain visible but do not disable Start because `ValidationResult.valid` ignores warning severity.

- [ ] **Step 4: Run GUI tests**

Run:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m pytest tests\gui\test_main_window.py -v
```

Expected: all GUI tests pass.

- [ ] **Step 5: Record the GUI checkpoint**

Run:

```powershell
if (Test-Path -LiteralPath .git) {
    git add src/rotomask_analyzer/gui/main_window.py tests/gui/test_main_window.py
    git commit -m "feat: expose soft iou problem thresholds"
} else {
    Write-Host "Checkpoint: feat: expose soft iou problem thresholds (Git unavailable)"
}
```

---

### Task 7: Documentation, Version, and Repository-Wide Semantic Audit

**Files:**
- Modify: `README.md`
- Modify: `pyproject.toml`
- Modify: `src/rotomask_analyzer/version.py`
- Modify: `tests/unit/test_app.py`
- Modify where found: production/tests containing obsolete schema language

**Interfaces:**
- Produces: application/package version `2.0.0` and current end-user contract.
- Documents: exact folder tree, Alpha rules, formula, empty-pair behavior, config, outputs, tests, build, and smoke commands.

- [ ] **Step 1: Add a version consistency test**

In `tests/unit/test_app.py`, parse `pyproject.toml` and assert:

```python
assert __version__ == "2.0.0"
assert tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]["version"] == __version__
```

- [ ] **Step 2: Update package and runtime version**

Set `project.version = "2.0.0"` in `pyproject.toml` and `__version__ = "2.0.0"` in `version.py`.

- [ ] **Step 3: Rewrite README around schema 2.0**

Document this exact input tree:

```text
clip_01/
├── manual/
├── roto_raw/
└── roto_corrected/
```

State that `original` is private user material outside the program and is ignored. Document strict RGBA 8/16-bit input, unconditional Alpha use, RGB ignore behavior, continuous normalization, min/max Soft IoU formula, empty/empty `1.0`, the two thresholds, all CSV names/headers, `soft_iou_timeline.png`, and the exact verification/build commands used below.

- [ ] **Step 4: Run a semantic stale-term audit**

Run:

```powershell
rg -n --glob '!build/**' --glob '!dist/**' --glob '!artifacts/**' --glob '!src/rotomask_analyzer.egg-info/**' --glob '!docs/superpowers/**' "reference|mask_threshold|false_positive|false_negative|binary|binar|iou_timeline\.png|original/" src tests README.md
```

Expected: no matches that describe or implement the old input/analysis/output contract. Legitimate Python concepts such as a binary executable must be phrased so they cannot be confused with mask binarization.

- [ ] **Step 5: Fix every semantic stale-term match**

Rename test helpers, variables, error messages, function imports, report labels, and documentation text to `manual`, `alpha`, or `soft_iou` as appropriate. Do not edit generated `src/rotomask_analyzer.egg-info` by hand; editable reinstall/build refreshes it.

- [ ] **Step 6: Run version and full test collection**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest --collect-only -q
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: collection succeeds and all tests pass.

- [ ] **Step 7: Record the documentation/version checkpoint**

Run:

```powershell
if (Test-Path -LiteralPath .git) {
    git add README.md pyproject.toml src tests
    git commit -m "docs: describe soft alpha schema 2"
} else {
    Write-Host "Checkpoint: docs: describe soft alpha schema 2 (Git unavailable)"
}
```

---

### Task 8: Full Verification, Portable Build, and Positive/Negative Smoke Tests

**Files:**
- Modify only if a verified failure requires it: `packaging/RotoMaskAnalyzer.spec`
- Modify only if a verified failure requires it: `build_exe.ps1`
- Refresh through editable install/build: `src/rotomask_analyzer.egg-info/*`
- Create only as temporary test data outside source: a valid and invalid RGBA smoke project

**Interfaces:**
- Consumes: complete application from Tasks 1–7.
- Produces: `dist/RotoMaskAnalyzer.exe` version 2.0.0 and evidence from tests, lint, packaged positive smoke, packaged negative smoke, and GUI launch smoke.

- [ ] **Step 1: Refresh the editable installation**

Run:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Expected: exit code 0 and package metadata reports `rotomask-analyzer 2.0.0`.

- [ ] **Step 2: Run the complete automated suite from a clean Python process**

Run:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: exit code 0; record the exact pass count.

- [ ] **Step 3: Run Ruff**

Run:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
```

Expected: `All checks passed!` and exit code 0.

- [ ] **Step 4: Re-run the stale-contract audit**

Run:

```powershell
rg -n --glob '!build/**' --glob '!dist/**' --glob '!artifacts/**' --glob '!src/rotomask_analyzer.egg-info/**' --glob '!docs/superpowers/**' "reference|mask_threshold|false_positive|false_negative|binary|binar|iou_timeline\.png|original/" src tests README.md
```

Expected: no obsolete-contract matches.

- [ ] **Step 5: Build the portable Windows executable**

Run:

```powershell
.\build_exe.ps1
```

Expected: exit code 0 and `dist\RotoMaskAnalyzer.exe` exists with nonzero size.

- [ ] **Step 6: Create valid and invalid temporary RGBA smoke projects**

Use a temporary directory under `$env:TEMP`, never the workspace root. Generate two frames in each of `manual`, `roto_raw`, and `roto_corrected` with Pillow RGBA. In the valid project, use Alpha values including `0`, `64`, `128`, and `255`. In the invalid project, replace one Roto PNG with RGB so validation must fail. Use `apply_patch` only for repository files; this temporary fixture is generated by an inline read-only-to-repo Python command:

```powershell
$smokeRoot = Join-Path $env:TEMP "RotoMaskAnalyzer-soft-alpha-smoke"
if (Test-Path -LiteralPath $smokeRoot) { Remove-Item -LiteralPath $smokeRoot -Recurse -Force }
New-Item -ItemType Directory -Path $smokeRoot | Out-Null
$env:ROTOMASK_SMOKE_ROOT = $smokeRoot
@'
import os
from pathlib import Path
import numpy as np
from PIL import Image

root = Path(os.environ["ROTOMASK_SMOKE_ROOT"])
for project_name in ("valid", "invalid"):
    project = root / project_name
    for folder in ("manual", "roto_raw", "roto_corrected"):
        for number in (1, 2):
            rgba = np.zeros((3, 4, 4), dtype=np.uint8)
            rgba[:, :, :3] = (20, 40, 60)
            rgba[:, :, 3] = np.array([[0, 64, 128, 255]] * 3, dtype=np.uint8)
            path = project / "clip_01" / folder / f"frame_{number:04d}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(rgba, "RGBA").save(path)
bad = root / "invalid/clip_01/roto_raw/frame_0002.png"
Image.new("RGB", (4, 3), (1, 2, 3)).save(bad)
'@ | .\.venv\Scripts\python.exe -
```

Expected: both project trees exist and the workspace source tree is unchanged.

- [ ] **Step 7: Run the packaged positive full-core smoke test**

Run:

```powershell
$env:ROTOMASK_ANALYZER_PACKAGING_SMOKE_PROJECT = Join-Path $smokeRoot "valid"
& .\dist\RotoMaskAnalyzer.exe
$positiveExit = $LASTEXITCODE
Remove-Item Env:\ROTOMASK_ANALYZER_PACKAGING_SMOKE_PROJECT
if ($positiveExit -ne 0) { throw "Positiver EXE-Smoke-Test fehlgeschlagen: $positiveExit" }
```

Expected: exit code 0, a successful timestamped result directory, schema 2.0 manifest, three-folder validation report, Soft-IoU CSV fields, and `soft_iou_timeline.png`.

- [ ] **Step 8: Run the packaged negative validation smoke test**

Run:

```powershell
$env:ROTOMASK_ANALYZER_PACKAGING_SMOKE_PROJECT = Join-Path $smokeRoot "invalid"
& .\dist\RotoMaskAnalyzer.exe
$negativeExit = $LASTEXITCODE
Remove-Item Env:\ROTOMASK_ANALYZER_PACKAGING_SMOKE_PROJECT
if ($negativeExit -ne 2) { throw "Negativer EXE-Smoke-Test lieferte $negativeExit statt 2" }
```

Expected: exit code 2, validation blocks analysis, and no successful results directory is produced.

- [ ] **Step 9: Run a packaged GUI startup smoke test**

Run:

```powershell
$process = Start-Process -FilePath (Resolve-Path .\dist\RotoMaskAnalyzer.exe) -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 5
if ($process.HasExited) { throw "GUI-EXE beendete sich unerwartet mit $($process.ExitCode)" }
Stop-Process -Id $process.Id
```

Expected: the process remains alive for five seconds and terminates cleanly when stopped by the smoke harness.

- [ ] **Step 10: Inspect the valid packaged result contract**

Run:

```powershell
$validProject = Join-Path $smokeRoot "valid"
$latestRun = Get-ChildItem -LiteralPath (Join-Path $validProject "results") -Directory | Sort-Object Name | Select-Object -Last 1
Get-Content -Raw (Join-Path $latestRun.FullName "analysis_manifest.json")
Get-Content -Raw (Join-Path $latestRun.FullName "clip_01\frame_metrics.csv")
Get-ChildItem -Recurse -File $latestRun.FullName | Select-Object FullName,Length
```

Expected: manifest schema 2.0, only Soft-IoU metric definitions, exactly two metric rows per frame, and every expected output file is present and nonempty.

- [ ] **Step 11: Remove temporary smoke data after evidence is recorded**

Resolve and verify the target remains under `$env:TEMP`, then remove only that explicit directory:

```powershell
$resolvedSmoke = (Resolve-Path -LiteralPath $smokeRoot).Path
$resolvedTemp = (Resolve-Path -LiteralPath $env:TEMP).Path
if (-not $resolvedSmoke.StartsWith($resolvedTemp, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Unsicheres Smoke-Cleanup-Ziel: $resolvedSmoke"
}
Remove-Item -LiteralPath $resolvedSmoke -Recurse -Force
```

Expected: only the temporary smoke tree is removed; repository build artifacts remain.

- [ ] **Step 12: Record the release checkpoint**

Run:

```powershell
if (Test-Path -LiteralPath .git) {
    git add README.md pyproject.toml src tests packaging build_exe.ps1
    git commit -m "build: release rotomask analyzer 2.0.0"
} else {
    Write-Host "Checkpoint: build: release rotomask analyzer 2.0.0 (Git unavailable)"
}
```

Final evidence must report the exact pytest count, Ruff result, EXE path and size, positive smoke exit code `0`, negative smoke exit code `2`, GUI startup result, and any actual deviation. Do not claim a check that was not executed.
