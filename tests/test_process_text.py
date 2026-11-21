from integrity_agent.detectors import process, text


def test_registry_and_status():
    assert not process.registry("w", "a", "b", {}, {"enrollment": 10})
    assert (
        process.registry("w", "a", "b", {"enrollment": 12}, {"enrollment": 10})[0].kind
        == "registry-difference"
    )
    assert (
        process.status("w", "a", {"updated-by": [{"type": "retraction", "DOI": "10.test/notice"}]})[
            0
        ].tier
        == "info"
    )


def test_text_reuse_is_low_tier():
    content = " ".join(f"synthetic{i}" for i in range(80))
    sections = [
        {"work_id": w, "artifact_id": w, "section": "Results", "text": content} for w in ("a", "b")
    ]
    findings = text.detect(sections)
    assert findings[0].tier == "info"
    assert findings[0].measurements["context_weight"] == 2
