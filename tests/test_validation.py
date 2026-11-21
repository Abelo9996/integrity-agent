import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from integrity_agent.validation import build_packet, predict_packet, score_packet


def corpus(tmp_path):
    rows = []
    for i in range(2):
        path = tmp_path / f"synthetic-{i}.png"
        Image.fromarray(
            np.random.default_rng(i).integers(0, 255, (128, 128, 3), dtype=np.uint8)
        ).save(path)
        rows.append(
            {
                "id": f"synthetic-{i}",
                "path": str(path),
                "pmcid": f"synthetic-article-{i}",
                "source": f"https://example.org/{i}.png",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "license": "CC BY",
                "citation": "Synthetic test fixture",
            }
        )
    p = tmp_path / "corpus.json"
    p.write_text(json.dumps({"figures": rows}))
    return p


def test_pending_review_is_not_a_negative_label(tmp_path):
    root = tmp_path / "packet"
    manifest = build_packet(corpus(tmp_path), root)
    assert len(manifest["cases"]) == 8
    assert "horizontal-flip" not in (root / "reviewer/index.html").read_text()
    predict_packet(root)
    score = score_packet(root)
    assert score["human_labels"]["pending"] == 8
    assert score["adjudicated_negative_signal_rate"] is None
    assert score["adjudicated_negative_count"] == 0
    assert score["generated_manipulations"]["horizontal-flip"]["total"] == 2
    labels_path = root / "reviewer/labels.json"
    labels = json.loads(labels_path.read_text())
    labels[0].update(label="distinct")
    labels_path.write_text(json.dumps(labels))
    with pytest.raises(ValueError, match="reviewer ID"):
        score_packet(root)
    labels[0].update(reviewer_id="synthetic-test", rationale="Synthetic test label only")
    labels_path.write_text(json.dumps(labels))
    score = score_packet(root)
    assert score["adjudicated_negative_count"] == 1
    assert score["human_labels"]["pending"] == 7
    with pytest.raises(ValueError, match="already exists"):
        build_packet(corpus(tmp_path), root)


def test_packet_rejects_changed_source_and_prediction_manifest(tmp_path):
    source = corpus(tmp_path)
    rows = json.loads(source.read_text())
    Path(rows["figures"][0]["path"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="digest"):
        build_packet(source, tmp_path / "bad")
    source = corpus(tmp_path)
    root = tmp_path / "good"
    build_packet(source, root)
    predict_packet(root)
    manifest = root / "coordinator/manifest.json"
    manifest.write_text(manifest.read_text() + " ")
    with pytest.raises(ValueError, match="different manifest"):
        score_packet(root)
