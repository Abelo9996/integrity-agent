"""D4: raw row sequences and explicitly scoped distribution/workbook signals."""

from __future__ import annotations

import io
import re
import zipfile
from collections import Counter

import numpy as np
import pandas as pd
from lxml import etree
from scipy.stats import chisquare, skew

from ..models import finding


def rows(frame: pd.DataFrame, work_id: str, artifact_id: str, *, sequence_length=3):
    if sequence_length < 2:
        raise ValueError("Sequence length must be >=2")
    records = [
        tuple(None if pd.isna(x) else str(x) for x in row)
        for row in frame.itertuples(index=False, name=None)
    ]
    seen = {}
    duplicates = []
    for start in range(len(records) - sequence_length + 1):
        seq = tuple(records[start : start + sequence_length])
        if len(set(seq)) < 2:
            continue
        if seq in seen and start - seen[seq] >= sequence_length:
            duplicates.append([seen[seq] + 1, start + 1])
        else:
            seen.setdefault(seq, start)
    if not duplicates:
        return []
    return [
        finding(
            "D4",
            "repeated-row-sequence",
            "review",
            [work_id],
            [artifact_id],
            "Nonconstant row sequences repeat in the raw data; warrants review.",
            parameters={"sequence_length": sequence_length},
            measurements={"row_pairs_one_based": duplicates},
            limitations=[
                "Repeated measurements, sorting, merges and duplicated exports can explain repetition."
            ],
        )
    ]


def distribution(
    values,
    work_id,
    artifact_id,
    *,
    column,
    expected_skew=False,
    terminal_digits=False,
    hard_cap=None,
    digit_resolution=1,
):
    a = np.asarray(values, float)
    a = a[np.isfinite(a)]
    if len(a) < 100:
        return []
    signals = []
    if expected_skew and abs(float(skew(a))) < 0.1:
        signals.append(("low-skew", {"skew": float(skew(a))}))
    if hard_cap is not None and np.mean(a == hard_cap) > 0.1:
        signals.append(
            ("mass-at-cap", {"cap": hard_cap, "fraction": float(np.mean(a == hard_cap))})
        )
    if terminal_digits:
        if digit_resolution <= 0:
            raise ValueError("digit_resolution must be positive")
        counts = np.bincount(np.abs(np.rint(a / digit_resolution).astype(int)) % 10, minlength=10)
        p = float(chisquare(counts).pvalue)
        if p < 0.001:
            signals.append(("terminal-digits", {"p": p, "counts": counts.tolist()}))
    return [
        finding(
            "D4",
            kind,
            "info",
            [work_id],
            [artifact_id],
            f"Column {column} has a {kind} distribution signal under the supplied assumptions.",
            parameters={
                "expected_skew": expected_skew,
                "digit_resolution": digit_resolution,
                "terminal_digits": terminal_digits,
                "hard_cap": hard_cap,
            },
            measurements=metric,
            limitations=[
                "Measurement precision, rounding, censoring and domain mechanisms require human assessment.",
                "Exploratory checks are not calibrated across arbitrary columns.",
            ],
        )
        for kind, metric in signals
    ]


def workbook(content: bytes, work_id: str, artifact_id: str):
    import openpyxl

    result = []
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        if sum(i.file_size for i in archive.infolist()) > 100_000_000:
            raise ValueError("Workbook expansion limit exceeded")
        if "xl/calcChain.xml" in archive.namelist():
            root = etree.fromstring(
                archive.read("xl/calcChain.xml"),
                etree.XMLParser(resolve_entities=False, no_network=True),
            )
            refs = root.xpath('//*[local-name()="c"]/@r')
            row_ids = [int(re.search(r"\d+", r).group()) for r in refs if re.search(r"\d+", r)]
            if row_ids != sorted(row_ids):
                result.append(
                    finding(
                        "D4",
                        "calculation-order",
                        "info",
                        [work_id],
                        [artifact_id],
                        "Workbook calculation-chain order differs from worksheet row order.",
                        measurements={"references": refs[:100]},
                        limitations=[
                            "Calculation dependencies routinely reorder cells; not evidence of editing chronology."
                        ],
                    )
                )
    wb = openpyxl.load_workbook(
        io.BytesIO(content), read_only=False, data_only=False, keep_links=False
    )
    for sheet in wb:
        for column in sheet.iter_cols():
            styles = Counter(cell.style_id for cell in column[1:] if cell.value is not None)
            fonts = {str(cell.font) for cell in column[1:] if cell.value is not None}
            if len(fonts) > 1:
                result.append(
                    finding(
                        "D4",
                        "mixed-fonts",
                        "info",
                        [work_id],
                        [artifact_id],
                        f"Worksheet {sheet.title}, column {column[0].column_letter} contains mixed fonts.",
                        measurements={"style_counts": dict(styles)},
                        limitations=[
                            "Formatting, pasted values and templates commonly cause this."
                        ],
                    )
                )
    metadata = {
        k: str(getattr(wb.properties, k))
        for k in ("creator", "lastModifiedBy", "created", "modified")
    }
    result.append(
        finding(
            "D4",
            "workbook-metadata",
            "info",
            [work_id],
            [artifact_id],
            "Workbook metadata was extracted for provenance review.",
            measurements=metadata,
            limitations=["Metadata is editable and does not establish who created the data."],
        )
    )
    wb.close()
    return result
