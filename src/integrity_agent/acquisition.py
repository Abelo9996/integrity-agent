"""Identifier-only author and artifact acquisition. Network failures are coverage, not findings."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import quote, urlsplit

import httpx
from lxml import etree

from .models import Artifact, Author, Coverage, Work, stable_id
from .transport import AccessError, Transport

XML_PARSER = etree.XMLParser(resolve_entities=False, no_network=True)


def doi(value):
    return re.sub(r"^https?://(?:dx\.)?doi.org/", "", value or "").lower().strip()


def openalex_headers():
    key = os.getenv("OPENALEX_API_KEY", "")
    return {"Authorization": f"Bearer {key}"} if key else {}


def resolve(http: Transport, *, name=None, orcid=None, openalex_id=None) -> list[Author]:
    base = "https://api.openalex.org/authors"
    if openalex_id:
        ident = openalex_id.rsplit("/", 1)[-1]
        if not re.fullmatch(r"A\d+", ident):
            raise ValueError("Invalid OpenAlex author ID")
        records = [http.json(f"{base}/{ident}", headers=openalex_headers())]
    elif orcid:
        if not re.fullmatch(r"\d{4}-\d{4}-\d{4}-[\dX]{4}", orcid):
            raise ValueError("Invalid ORCID format")
        records = [http.json(f"{base}/https://orcid.org/{orcid}", headers=openalex_headers())]
    elif name:
        records = http.json(
            base, params={"search": name, "per_page": 10}, headers=openalex_headers()
        )["results"]
    else:
        raise ValueError("Provide --orcid, --openalex-id, or --name")
    return [
        Author(
            id=r["id"],
            name=r["display_name"],
            orcid=r.get("orcid"),
            institutions=[i["display_name"] for i in (r.get("last_known_institutions") or [])],
            works_count=r.get("works_count", 0),
        )
        for r in records
    ]


def works(http: Transport, author: Author) -> list[Work]:
    cursor = "*"
    seen = set()
    result = []
    fetched = 0
    while cursor:
        if cursor in seen:
            raise AccessError("OpenAlex repeated its pagination cursor")
        seen.add(cursor)
        page = http.json(
            "https://api.openalex.org/works",
            params={
                "filter": f"authorships.author.id:{author.id}",
                "per_page": 100,
                "cursor": cursor,
            },
            headers=openalex_headers(),
        )
        for r in page["results"]:
            if not any(
                a.get("author", {}).get("id") == author.id for a in r.get("authorships", [])
            ):
                continue
            ids = r.get("ids") or {}
            locations = r.get("locations") or []
            arxiv = next(
                (
                    re.search(
                        r"arxiv\.org/(?:abs|pdf|html)/((?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?)",
                        loc.get("landing_page_url") or "",
                    )
                    for loc in locations
                    if re.search(
                        r"arxiv\.org/(?:abs|pdf|html)/((?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?)",
                        loc.get("landing_page_url") or "",
                    )
                ),
                None,
            )
            result.append(
                Work(
                    id=r["id"],
                    title=r.get("title") or "",
                    author_id=author.id,
                    year=r.get("publication_year"),
                    doi=doi(r.get("doi")) or None,
                    pmcid=(ids.get("pmcid") or "").rstrip("/").rsplit("/", 1)[-1] or None,
                    arxiv_id=arxiv.group(1) if arxiv else None,
                    venue=((r.get("primary_location") or {}).get("source") or {}).get(
                        "display_name", ""
                    ),
                    topic_id=(r.get("primary_topic") or {}).get("id"),
                    oa_urls=[
                        loc["pdf_url"]
                        for loc in locations
                        if loc.get("is_oa") and loc.get("pdf_url")
                    ],
                )
            )
        fetched += len(page["results"])
        cursor = page.get("meta", {}).get("next_cursor")
        total = page.get("meta", {}).get("count")
        if total is not None and fetched >= total:
            break
        if not page["results"]:
            break
        if cursor and not os.getenv("OPENALEX_API_KEY"):
            raise AccessError(
                "Full works pagination requires OPENALEX_API_KEY; partial lists are not accepted."
            )
    return list({w.id: w for w in result}.values())


class Collector:
    def __init__(self, http: Transport, root: Path):
        self.http = http
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.artifacts: list[Artifact] = []
        self.coverage: list[Coverage] = []

    def save(
        self,
        work: Work,
        content: bytes,
        source: str,
        url: str,
        link: str,
        license: str,
        suffix: str,
        *,
        parent: Artifact | None = None,
        relation="identifier",
    ):
        allowed = {work.id, work.doi, work.pmcid, work.arxiv_id}
        if link not in allowed and parent is None:
            raise ValueError("Artifact lacks a verified identifier or parent link")
        if parent and (
            parent.work_id != work.id
            or parent.artifact_id not in {a.artifact_id for a in self.artifacts}
        ):
            raise ValueError("Parent belongs to a different work")
        digest = hashlib.sha256(content).hexdigest()
        ident = stable_id("artifact", [work.id, url, digest])
        path = self.root / (ident + suffix)
        path.write_bytes(content)
        a = Artifact(
            work_id=work.id,
            artifact_id=ident,
            source=source,
            url=url,
            linking_identifier=link,
            sha256=digest,
            license=license,
            path=str(path),
            parent_artifact_id=parent.artifact_id if parent else None,
            relation=relation,
        )
        if a.artifact_id not in {x.artifact_id for x in self.artifacts}:
            self.artifacts.append(a)
            with (self.root / "manifest.jsonl").open("a") as f:
                f.write(a.model_dump_json() + "\n")
        return a

    def attempt(self, work, source, action):
        before = len(self.artifacts)
        try:
            action()
            count = len(self.artifacts) - before
            status, detail = (
                ("ok", f"{count} artifacts collected")
                if count
                else ("skipped", "No accessible identifier-linked artifacts")
            )
        except (
            AccessError,
            ValueError,
            KeyError,
            TypeError,
            httpx.HTTPError,
            etree.XMLSyntaxError,
        ) as exc:
            status, detail = (
                "failed",
                f"{type(exc).__name__}: {str(exc)[:200] if isinstance(exc, AccessError) else 'source response could not be validated'}",
            )
        self.coverage.append(Coverage(work_id=work.id, source=source, status=status, detail=detail))

    def pmc(self, w):
        if not w.pmcid:
            return
        base = "https://pmc-oa-opendata.s3.amazonaws.com/"
        token = None
        keys = []
        while True:
            params = {"list-type": "2", "prefix": f"metadata/{w.pmcid}."}
            if token:
                params["continuation-token"] = token
            tree = etree.fromstring(self.http.get(base, params=params), XML_PARSER)
            keys.extend(tree.xpath('//*[local-name()="Key"]/text()'))
            next_tokens = tree.xpath('//*[local-name()="NextContinuationToken"]/text()')
            if not next_tokens:
                break
            token = next_tokens[0]
        for key in keys:
            if not re.fullmatch(rf"metadata/{re.escape(w.pmcid)}\.\d+\.json", key):
                continue
            meta_url = base + key
            raw = self.http.get(meta_url)
            meta = json.loads(raw)
            if str(meta.get("pmcid")) != w.pmcid or not meta.get("is_pmc_openaccess"):
                continue
            if w.doi and meta.get("doi") and doi(meta["doi"]) != w.doi:
                raise ValueError("PMC DOI disagrees with resolved work")
            license = meta.get("license_code") or "unspecified"
            parent = self.save(w, raw, "pmc", meta_url, w.pmcid, license, ".json")
            urls = [meta.get("xml_url"), meta.get("text_url"), *meta.get("media_urls", [])]
            for url in filter(None, urls):
                if url.startswith("s3://pmc-oa-opendata/"):
                    url = base + url.removeprefix("s3://pmc-oa-opendata/")
                if urlsplit(url).hostname != "pmc-oa-opendata.s3.amazonaws.com":
                    raise ValueError("Unexpected PMC media host")
                suffix = Path(urlsplit(url).path).suffix.lower() or ".bin"
                self.save(
                    w,
                    self.http.get(url, ttl=30 * 86400),
                    "pmc",
                    url,
                    w.pmcid,
                    license,
                    suffix,
                    parent=parent,
                )

    def europe(self, w, *, identify=False):
        base = "https://www.ebi.ac.uk/europepmc/webservices/rest"
        if not w.pmcid and w.doi:
            page = self.http.json(
                base + "/search", params={"query": f'DOI:"{w.doi}"', "format": "json"}
            )
            matches = [
                r
                for r in page.get("resultList", {}).get("result", [])
                if doi(r.get("doi")) == w.doi
            ]
            if matches:
                self.save(
                    w,
                    json.dumps(page).encode(),
                    "europe-pmc-identifiers",
                    base + "/search",
                    w.doi,
                    "Europe PMC metadata",
                    ".json",
                )
                w.pmcid = matches[0].get("pmcid")
        if identify or not w.pmcid:
            return
        url = f"{base}/{w.pmcid}/fullTextXML"
        raw = self.http.get(url)
        tree = etree.fromstring(raw, XML_PARSER)
        text_dois = tree.xpath('//article-id[@pub-id-type="doi"]/text()')
        if w.doi and text_dois and w.doi not in {doi(d) for d in text_dois}:
            raise ValueError("Europe PMC DOI disagrees with resolved work")
        licenses = tree.xpath('//license//@*[local-name()="href"]')
        lic = licenses[0] if licenses else "PMC OA service; see article license"
        self.save(w, raw, "europe-pmc", url, w.pmcid, lic, ".xml")
        supplement = f"{base}/{w.pmcid}/supplementaryFiles"
        self.save(w, self.http.get(supplement), "europe-pmc", supplement, w.pmcid, lic, ".zip")

    def preprints(self, w):
        if not w.doi:
            return
        for server in ("biorxiv", "medrxiv"):
            preprint_dois = [w.doi] if w.doi.startswith("10.1101/") else []
            if not preprint_dois:
                pubs = self.http.json(f"https://api.biorxiv.org/pubs/{server}/{w.doi}/na/json")
                preprint_dois = [
                    p["biorxiv_doi"]
                    for p in pubs.get("collection", [])
                    if doi(p.get("published_doi")) == w.doi
                ]
            for pid in preprint_dois:
                url = f"https://api.biorxiv.org/details/{server}/{pid}/na/json"
                raw = self.http.get(url)
                records = json.loads(raw).get("collection", [])
                parent = self.save(w, raw, server, url, w.doi, "metadata", ".json")
                for record in records:
                    if doi(record.get("doi")) != pid:
                        continue
                    xml_url = record.get("jatsxml") or record.get("jats xml path")
                    if xml_url:
                        self.save(
                            w,
                            self.http.get(xml_url, download=True),
                            server,
                            xml_url,
                            pid,
                            record.get("license", "unspecified"),
                            ".xml",
                            parent=parent,
                            relation="published DOI to preprint DOI",
                        )

    def arxiv(self, w):
        if w.arxiv_id:
            url = f"https://arxiv.org/src/{w.arxiv_id}"
            self.save(
                w,
                self.http.get(url, download=True),
                "arxiv",
                url,
                w.arxiv_id,
                "arXiv individual article license; no redistribution assumed",
                ".tar.gz",
            )

    def unpaywall(self, w):
        if not w.doi or any(
            a.work_id == w.id and Path(a.path).suffix == ".xml" for a in self.artifacts
        ):
            return
        url = f"https://api.unpaywall.org/v2/{w.doi}"
        raw = self.http.get(url, params={"email": self.http.email})
        meta = json.loads(raw)
        if doi(meta.get("doi")) != w.doi:
            raise ValueError("Unpaywall identifier mismatch")
        parent = self.save(w, raw, "unpaywall", url, w.doi, "metadata", ".json")
        for loc in meta.get("oa_locations", []):
            pdf = loc.get("url_for_pdf")
            if pdf:
                raw_pdf = self.http.get(pdf, download=True)
                if not raw_pdf.startswith(b"%PDF"):
                    continue
                self.save(
                    w,
                    raw_pdf,
                    "unpaywall",
                    pdf,
                    w.doi,
                    loc.get("license") or "OA access; reuse license unspecified",
                    ".pdf",
                    parent=parent,
                )

    def crossref(self, w):
        if w.doi:
            url = f"https://api.crossref.org/works/{quote(w.doi, safe='')}"
            raw = self.http.get(url, params={"mailto": self.http.email})
            if doi(json.loads(raw)["message"]["DOI"]) != w.doi:
                raise ValueError("Crossref identifier mismatch")
            self.save(w, raw, "crossref", url, w.doi, "Crossref metadata", ".json")

    def collect(self, w):
        self.attempt(w, "identifier-enrichment", lambda: self.europe(w, identify=True))
        for source, fn in [
            ("pmc", self.pmc),
            ("europe-pmc", self.europe),
            ("preprints", self.preprints),
            ("arxiv", self.arxiv),
            ("unpaywall", self.unpaywall),
            ("crossref", self.crossref),
        ]:
            self.attempt(w, source, lambda fn=fn: fn(w))


def orcid_record(http: Transport, orcid_id: str):
    """Read public ORCID data for candidate context, never infer identity from names."""
    token = os.getenv("ORCID_ACCESS_TOKEN")
    headers = {"Accept": "application/vnd.orcid+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return http.json(f"https://pub.orcid.org/v3.0/{orcid_id}/record", headers=headers)


def field_baselines(collector, selected):
    """Random topic-associated author sample; context only, no career-matching claim."""
    from collections import Counter

    counts = Counter(w.year for w in selected if w.year)
    topic = Counter(w.topic_id for w in selected if w.topic_id)
    if not topic or not selected:
        return
    topic_id = topic.most_common(1)[0][0]
    url = "https://api.openalex.org/authors"
    params = {"filter": f"topics.id:{topic_id}", "sample": 100, "seed": 0, "per_page": 100}
    obj = collector.http.json(url, params=params, headers=openalex_headers())
    rows = [r for r in obj.get("results", []) if r["id"] != selected[0].author_id]
    reported_years = {c["year"] for r in rows for c in r.get("counts_by_year", [])}
    counts = {year: count for year, count in counts.items() if year in reported_years}
    # The artifact is a derived field reference attached through the work's OpenAlex topic.
    parent = collector.save(
        selected[0],
        json.dumps(
            {
                "topic_id": topic_id,
                "query": params,
                "years": {
                    str(year): [
                        next(
                            (
                                c["works_count"]
                                for c in r.get("counts_by_year", [])
                                if c["year"] == year
                            ),
                            0,
                        )
                        for r in rows
                    ]
                    for year in counts
                },
                "author_counts": dict(counts),
            }
        ).encode(),
        "openalex-baseline",
        url,
        selected[0].id,
        "CC0",
        ".json",
    )
    return parent
