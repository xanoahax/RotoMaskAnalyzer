from pathlib import Path

import pytest

from rotomask_analyzer.discovery import DiscoveryError, discover_clips, discover_frames


def test_clips_are_exactly_matched_sorted_and_unrelated_folders_ignored(tmp_path):
    for name in ("clip_02", "clip_01", "clip_1", "clip_001", "notes", "results"):
        (tmp_path / name).mkdir()

    clips = discover_clips(tmp_path)

    assert [(clip.clip_id, clip.number) for clip in clips] == [
        ("clip_01", 1),
        ("clip_02", 2),
    ]


@pytest.mark.parametrize(
    ("folders", "code"),
    [
        (("clip_02",), "missing_clip_01"),
        (("clip_01", "clip_03"), "clip_number_gap"),
    ],
)
def test_invalid_clip_numbering_is_rejected(tmp_path, folders, code):
    for folder in folders:
        (tmp_path / folder).mkdir()

    with pytest.raises(DiscoveryError) as raised:
        discover_clips(tmp_path)

    assert raised.value.code == code


def test_frames_are_numerically_sorted_and_keep_full_filename(project_factory):
    project = project_factory(frames=("shot_0010.png", "shot_0009.png"))

    frames = discover_frames(project / "clip_01")

    assert [(frame.number, frame.filename) for frame in frames] == [
        (9, "shot_0009.png"),
        (10, "shot_0010.png"),
    ]
    assert set(frames[0].paths) == {"manual", "roto_raw", "roto_corrected"}
    assert frames[0].paths["manual"] == Path(project / "clip_01/manual/shot_0009.png")


def test_frames_are_matched_by_terminal_number_when_variant_prefixes_differ(
    project_factory,
):
    project = project_factory(frames=())
    clip = project / "clip_01"
    names_by_variant = {
        "manual": ("clip_02_manual_00000.png", "clip_02_manual_00001.png"),
        "roto_raw": ("clip_02_roto_raw_00000.png", "clip_02_roto_raw_00001.png"),
        "roto_corrected": (
            "clip_02_roto_corrected_00000.png",
            "clip_02_roto_corrected_00001.png",
        ),
    }
    for variant, filenames in names_by_variant.items():
        for filename in filenames:
            (clip / variant).mkdir(parents=True, exist_ok=True)
            (clip / variant / filename).write_bytes(b"png contents are not read during discovery")

    frames = discover_frames(clip)

    assert [frame.number for frame in frames] == [0, 1]
    assert frames[0].filenames == {
        "manual": "clip_02_manual_00000.png",
        "roto_raw": "clip_02_roto_raw_00000.png",
        "roto_corrected": "clip_02_roto_corrected_00000.png",
    }
    assert frames[0].paths["manual"] == clip / "manual/clip_02_manual_00000.png"
    assert frames[0].paths["roto_raw"] == clip / "roto_raw/clip_02_roto_raw_00000.png"


def test_original_folder_is_ignored_even_with_unmatched_png(project_factory):
    project = project_factory()
    original = project / "clip_01/original/private_9999.png"
    original.parent.mkdir()
    original.write_bytes(b"private data")

    frames = discover_frames(project / "clip_01")

    assert [frame.filename for frame in frames] == ["frame_0001.png", "frame_0002.png"]
    assert all("original" not in frame.paths for frame in frames)


@pytest.mark.parametrize(
    ("mutator", "code"),
    [
        (
            lambda clip: (clip / "manual").rename(clip / "manual_missing"),
            "missing_required_folder",
        ),
        (
            lambda clip: (clip / "roto_raw" / "frame_0002.png").unlink(),
            "png_filename_mismatch",
        ),
        (
            lambda clip: (clip / "manual" / "frame_0002.png").rename(
                clip / "manual" / "no_number.png"
            ),
            "missing_frame_number",
        ),
    ],
)
def test_structural_frame_errors_are_rejected(project_factory, mutator, code):
    project = project_factory()
    clip = project / "clip_01"
    mutator(clip)

    with pytest.raises(DiscoveryError) as raised:
        discover_frames(clip)

    assert raised.value.code == code


@pytest.mark.parametrize(
    ("frames", "code"),
    [
        (("frame.png", "frame_0002.png"), "missing_frame_number"),
        (("a_0001.png", "b_0001.png"), "duplicate_frame_number"),
        (("frame_0001.png", "frame_0003.png"), "frame_number_gap"),
        (("frame_0001.png",), "too_few_frames"),
    ],
)
def test_invalid_frame_numbering_is_rejected(project_factory, frames, code):
    project = project_factory(frames=frames)

    with pytest.raises(DiscoveryError) as raised:
        discover_frames(project / "clip_01")

    assert raised.value.code == code
