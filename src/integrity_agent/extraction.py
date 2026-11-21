"""Non-generative JATS extraction, whitespace segmentation and safe archive expansion."""

from __future__ import annotations

import io
import re
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

import numpy as np
from lxml import etree

from .acquisition import XML_PARSER
from .models import Stat


def jats(content: bytes):
    root = etree.fromstring(content, XML_PARSER)
    captions = {}
    for fig in root.xpath("//fig"):
        caption = " ".join(fig.xpath(".//caption//text()"))
        for href in fig.xpath('.//graphic//@*[local-name()="href"]'):
            captions[Path(href).stem] = caption
    sections = []
    for sec in root.xpath("//sec[not(sec)]"):
        title = " ".join(sec.xpath("./title//text()"))
        sections.append((title, " ".join(sec.itertext())))
    sections.extend(
        ("figure legend", " ".join(f.xpath(".//caption//text()"))) for f in root.xpath("//fig")
    )
    tables = []
    for table in root.xpath("//table-wrap"):
        rows = [
            [" ".join(c.itertext()).strip() for c in row.xpath("./td|./th")]
            for row in table.xpath(".//tr")
        ]
        tables.append(
            {
                "id": table.get("id", ""),
                "caption": " ".join(table.xpath("./caption//text()")),
                "rows": rows,
            }
        )
    # Repository crawling is restricted to explicitly labelled data availability sections.
    links = []
    for sec in root.xpath("//sec"):
        title = " ".join(sec.xpath("./title//text()")).lower()
        if "data availab" in title or sec.get("sec-type") in (
            "data-availability",
            "data-availability-statement",
        ):
            links.extend(sec.xpath('.//ext-link//@*[local-name()="href"]'))
            links.extend(re.findall(r"https://[^\s<>]+", " ".join(sec.itertext())))
    return {
        "captions": captions,
        "sections": sections,
        "tables": tables,
        "data_links": sorted(set(links)),
        "text": " ".join(root.itertext()),
    }


def split_panels(pixels, *, min_size=64, depth=0, offset=(0, 0)):
    """Only split on broad white gutters; preserve original coordinates and unsplit figures."""
    a = np.asarray(pixels)
    if depth > 3:
        return [(offset[0], offset[1], a.shape[1], a.shape[0], a)]
    luminance = a.mean(axis=2) if a.ndim == 3 else a
    for axis in (0, 1):
        whitespace = (luminance > 245).mean(axis=1 if axis == 0 else 0) > 0.99
        starts = np.flatnonzero(np.diff(np.r_[False, whitespace, False].astype(int)) == 1)
        ends = np.flatnonzero(np.diff(np.r_[False, whitespace, False].astype(int)) == -1)
        for start, end in zip(starts, ends, strict=True):
            cut = int((start + end) // 2)
            if end - start < 4 or min(cut, a.shape[axis] - cut) < min_size:
                continue
            first, second = (a[:cut], a[cut:]) if axis == 0 else (a[:, :cut], a[:, cut:])
            delta = (0, cut) if axis == 0 else (cut, 0)
            return split_panels(
                first, min_size=min_size, depth=depth + 1, offset=offset
            ) + split_panels(
                second,
                min_size=min_size,
                depth=depth + 1,
                offset=(offset[0] + delta[0], offset[1] + delta[1]),
            )
    return [(offset[0], offset[1], a.shape[1], a.shape[0], a)]


def archive_members(content: bytes, *, max_bytes=200_000_000, max_members=2000):
    """Return bounded regular files; never extract paths or execute LaTeX/macros."""
    output = []
    size = 0

    def accept(name, count, reader):
        nonlocal size
        p = PurePosixPath(name)
        if p.is_absolute() or ".." in p.parts or "\\" in name:
            raise ValueError("Unsafe archive path")
        size += count
        if size > max_bytes or len(output) >= max_members:
            raise ValueError("Archive expansion limit exceeded")
        if count:
            output.append((name, reader()))

    if zipfile.is_zipfile(io.BytesIO(content)):
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            for item in archive.infolist():
                if item.is_dir():
                    continue
                if (item.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("Archive symlink rejected")
                accept(item.filename, item.file_size, lambda item=item: archive.read(item))
    else:
        with tarfile.open(fileobj=io.BytesIO(content), mode="r:*") as archive:
            for item in archive:
                if item.isdir():
                    continue
                if not item.isfile():
                    raise ValueError("Archive non-regular member rejected")
                accept(item.name, item.size, lambda item=item: archive.extractfile(item).read())
    return output


def pdf_images(content: bytes):
    import pymupdf

    result = []
    with pymupdf.open(stream=content, filetype="pdf") as doc:
        seen = set()
        for page in doc:
            for image in page.get_images(full=True):
                xref = image[0]
                if xref not in seen:
                    seen.add(xref)
                    item = doc.extract_image(xref)
                    result.append((f"embedded-{xref}.{item['ext']}", item["image"]))
        text = "\n".join(p.get_text() for p in doc)
    return result, text


def numbers_verified(stat: Stat, source: str) -> bool:
    """Token equality, not substring membership (12 is not present in 312)."""
    numbers = set(re.findall(r"(?<![\w.])[+-]?\d+(?:\.\d+)?(?![\w.])", source.replace("−", "-")))
    return all(x in numbers for x in [stat.mean, str(stat.n), *([stat.sd] if stat.sd else [])])


def table_stats(tables, work_id, artifact_id):
    """Only unambiguous separate mean/SD/n columns; never infer integer-scale assumptions."""
    extracted = []
    aliases = {
        "mean": "mean",
        "sd": "sd",
        "standard deviation": "sd",
        "n": "n",
        "sample size": "n",
        "group": "group",
        "variable": "variable",
        "measure": "variable",
    }
    for table in tables:
        rows = table["rows"]
        if not rows:
            continue
        header = {aliases.get(cell.lower().strip()): i for i, cell in enumerate(rows[0])}
        if not all(key in header for key in ("mean", "sd", "n")):
            continue
        for index, row in enumerate(rows[1:], 1):
            if len(row) != len(rows[0]):
                continue
            try:

                def cell(key, default="", row=row, header=header):
                    return row[header[key]] if key in header else default

                s = Stat(
                    work_id=work_id,
                    artifact_id=artifact_id,
                    group=cell("group", f"{table['id']} row {index}"),
                    variable=cell("variable", table["caption"]),
                    mean=cell("mean"),
                    sd=cell("sd"),
                    n=int(cell("n")),
                    source_text=" | ".join(row),
                    integer_scale_confirmed=False,
                )
                if numbers_verified(s, s.source_text):
                    extracted.append(s)
            except (ValueError, TypeError):
                continue
    return extracted


def validate_pdf_stats(rows, source_text, work_id, artifact_id):
    normalized = " ".join(source_text.split())
    accepted, rejected = [], []
    for row in rows:
        quote = " ".join(row.source_text.split())
        if (
            row.work_id != work_id
            or row.artifact_id != artifact_id
            or not quote
            or quote not in normalized
            or not numbers_verified(row, quote)
            or row.variable not in quote
            or row.group not in quote
        ):
            rejected.append(row.model_dump(mode="json"))
        else:
            accepted.append(row.model_copy(update={"integer_scale_confirmed": False}))
    return accepted, rejected
