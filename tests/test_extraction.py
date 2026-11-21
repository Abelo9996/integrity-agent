import io
import tarfile
import zipfile

import pytest

from integrity_agent.extraction import archive_members, jats, numbers_verified
from integrity_agent.models import Stat


def test_jats_links_captions_tables_and_no_external_entities():
    raw = b"""<article><body><sec><title>Data availability</title><p><ext-link xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="https://example.org/data">data</ext-link></p></sec><fig><caption><p>Synthetic caption</p></caption><graphic xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="figure1.jpg"/></fig><table-wrap><table><tr><th>n</th></tr><tr><td>12</td></tr></table></table-wrap></body></article>"""
    parsed = jats(raw)
    assert parsed["captions"]["figure1"] == "Synthetic caption"
    assert parsed["tables"][0]["rows"] == [["n"], ["12"]]
    assert parsed["data_links"] == ["https://example.org/data"]


def test_unsafe_archives_rejected():
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("../escape.txt", "bad")
    with pytest.raises(ValueError):
        archive_members(out.getvalue())
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w") as t:
        item = tarfile.TarInfo("link")
        item.type = tarfile.SYMTYPE
        item.linkname = "/etc/passwd"
        t.addfile(item)
    with pytest.raises(ValueError):
        archive_members(out.getvalue())


def test_archive_limit_and_regular_files():
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("figure.txt", "synthetic")
    assert archive_members(out.getvalue()) == [("figure.txt", b"synthetic")]
    with pytest.raises(ValueError):
        archive_members(out.getvalue(), max_bytes=2)


def test_numeric_hallucinations_are_dropped():
    s = Stat(work_id="w", artifact_id="a", group="g", variable="x", mean="1.25", sd="0.50", n=12)
    assert numbers_verified(s, "n=12; mean=1.25; SD=0.50")
    assert not numbers_verified(s, "n=312; mean=1.25; SD=0.50")
    assert not numbers_verified(s, "n=12; mean=1.26; SD=0.50")


def test_jats_stats_are_typed_but_integer_assumptions_not_inferred():
    from integrity_agent.extraction import table_stats

    tables = [
        {
            "id": "t1",
            "caption": "Synthetic measure",
            "rows": [["group", "n", "mean", "SD"], ["A", "12", "1.25", "0.50"]],
        }
    ]
    rows = table_stats(tables, "w", "a")
    assert len(rows) == 1
    assert rows[0].mean == "1.25"
    assert rows[0].integer_scale_confirmed is False


def test_pdf_extraction_requires_source_quote_and_exact_numbers():
    from integrity_agent.extraction import validate_pdf_stats

    source = "Treatment age n=12 mean=1.25 SD=0.50"
    s = Stat(
        work_id="w",
        artifact_id="a",
        group="Treatment",
        variable="age",
        mean="1.25",
        sd="0.50",
        n=12,
        source_text=source,
        integer_scale_confirmed=True,
    )
    accepted, rejected = validate_pdf_stats([s], source, "w", "a")
    assert len(accepted) == 1 and not rejected
    assert not accepted[0].integer_scale_confirmed
    changed = s.model_copy(update={"n": 312})
    assert not validate_pdf_stats([changed], source, "w", "a")[0]
