"""Conservative publication-type cues for review and routing."""

import re


def notice_title(title: str) -> bool:
    """A title cue only, never proof of a document's type or retraction status."""
    return bool(
        re.match(
            r"^\s*(?:retraction|correction|erratum|corrigendum|withdrawal)"
            r"(?:\s+note)?\s*(?::|\bto\b|\bof\b|$)",
            title,
            re.IGNORECASE,
        )
    )
