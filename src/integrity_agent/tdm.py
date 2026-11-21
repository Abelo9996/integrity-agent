"""Optional official publisher adapters. Server entitlements remain authoritative."""

import os
from urllib.parse import quote

from .acquisition import XML_PARSER
from .models import Coverage


def publisher_tdm(collector, work):
    if not work.doi:
        return
    candidates = [
        (
            "elsevier",
            "ELSEVIER_API_KEY",
            f"https://api.elsevier.com/content/article/doi/{quote(work.doi, safe='')}",
            "X-ELS-APIKey",
            {"Accept": "text/xml"},
            ".xml",
        ),
        (
            "wiley",
            "WILEY_TDM_TOKEN",
            f"https://api.wiley.com/onlinelibrary/tdm/v1/articles/{quote(work.doi, safe='')}",
            "Wiley-TDM-Client-Token",
            {},
            ".pdf",
        ),
    ]
    for source, env, url, header, extra, suffix in candidates:
        key = os.getenv(env)
        if not key:
            continue

        def collect(source=source, url=url, header=header, key=key, extra=extra, suffix=suffix):
            content = collector.http.get(url, headers={header: key, **extra})
            if suffix == ".pdf" and not content.startswith(b"%PDF"):
                raise ValueError("Publisher did not return a PDF")
            collector.save(
                work,
                content,
                source,
                url,
                work.doi,
                "Licensed TDM; no redistribution assumed",
                suffix,
            )

        collector.attempt(work, source, collect)
    key = os.getenv("SPRINGER_API_KEY")
    if key:

        def springer():
            from lxml import etree

            url = "https://api.springernature.com/openaccess/jats"
            content = collector.http.get(url, params={"q": f"doi:{work.doi}", "api_key": key})
            tree = etree.fromstring(content, XML_PARSER)
            for article in tree.xpath("//article"):
                identifiers = article.xpath('.//article-id[@pub-id-type="doi"]/text()')
                if work.doi in [i.lower() for i in identifiers]:
                    collector.save(
                        work,
                        etree.tostring(article),
                        "springer",
                        url,
                        work.doi,
                        "See article OA license",
                        ".xml",
                    )

        collector.attempt(work, "springer", springer)
    if not any(
        os.getenv(name) for name in ("ELSEVIER_API_KEY", "WILEY_TDM_TOKEN", "SPRINGER_API_KEY")
    ):
        collector.coverage.append(
            Coverage(
                work_id=work.id,
                source="publisher-tdm",
                status="skipped",
                detail="No publisher API credentials configured",
            )
        )
