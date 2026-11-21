import io

import openpyxl
import pandas as pd

from integrity_agent.detectors import raw


def test_repeated_sequences():
    frame = pd.DataFrame({"a": [1, 2, 3, 4, 1, 2, 3, 5]})
    assert raw.rows(frame, "w", "a")[0].measurements["row_pairs_one_based"] == [[1, 5]]
    assert not raw.rows(pd.DataFrame({"a": [0] * 20}), "w", "a")


def test_workbook_signals_are_info():
    wb = openpyxl.Workbook()
    ws = wb.active
    for x in ["value", 1, 2, 3]:
        ws.append([x])
    ws["A3"].font = openpyxl.styles.Font(name="Courier New")
    buf = io.BytesIO()
    wb.save(buf)
    findings = raw.workbook(buf.getvalue(), "w", "a")
    assert {f.kind for f in findings} == {"mixed-fonts", "workbook-metadata"}
    assert all(f.tier == "info" for f in findings)
