"""Follow only links extracted from an article's own data availability statement."""

from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit

from .acquisition import doi


def linked_repository(collector, work, parent, link):
    http = collector.http
    host = urlsplit(link).hostname
    path = urlsplit(link).path
    if host in ("doi.org", "dx.doi.org"):
        zenodo = re.fullmatch(r"/10\.5281/zenodo\.(\d+)", path)
        figshare = re.fullmatch(r"/10\.6084/m9\.figshare\.(\d+)(?:\.v(\d+))?", path)
        if zenodo:
            host, path = "zenodo.org", "/records/" + zenodo.group(1)
        elif figshare:
            host, path = (
                "figshare.com",
                "/articles/"
                + figshare.group(1)
                + ("/" + figshare.group(2) if figshare.group(2) else ""),
            )
    raw = None
    files = []
    license = "See repository record; no redistribution assumed"
    endpoint = link
    source = ""
    if host == "zenodo.org" and re.fullmatch(r"/records?/\d+/?", path):
        source = "zenodo"
        ident = path.strip("/").split("/")[-1]
        endpoint = f"https://zenodo.org/api/records/{ident}"
        raw = http.get(endpoint)
        obj = json.loads(raw)
        license = str(obj.get("metadata", {}).get("license", license))
        files = [(f["links"]["self"], f["key"]) for f in obj.get("files", [])]
    elif host in ("figshare.com", "www.figshare.com") and re.search(r"/\d+(?:/\d+)?/?$", path):
        source = "figshare"
        match = re.search(r"/([0-9]+)(?:/([0-9]+))?/?$", path)
        ident = match.group(1)
        endpoint = f"https://api.figshare.com/v2/articles/{ident}"
        if match.group(2):
            endpoint += "/versions/" + match.group(2)
        raw = http.get(endpoint)
        obj = json.loads(raw)
        license = str(obj.get("license", license))
        files = [(f["download_url"], f["name"]) for f in obj.get("files", [])]
    elif (
        host in ("doi.org", "dx.doi.org") and path.startswith("/10.5061/")
    ) or host == "datadryad.org":
        source = "dryad"
        identifier = (
            path.lstrip("/") if host in ("doi.org", "dx.doi.org") else path.split("doi:")[-1]
        )
        if not identifier.startswith("10.5061/"):
            return
        endpoint = "https://datadryad.org/api/v2/datasets/" + quote("doi:" + identifier, safe="")
        raw = http.get(endpoint)
        obj = json.loads(raw)
        version = urljoin(endpoint, obj["_links"]["stash:version"]["href"])
        page_url = version + "/files"
        while page_url:
            page = http.json(page_url)
            for item in page.get("_embedded", {}).get("stash:files", []):
                files.append(
                    (urljoin(endpoint, item["_links"]["stash:download"]["href"]), item["path"])
                )
            next_link = page.get("_links", {}).get("next", {}).get("href")
            page_url = urljoin(endpoint, next_link) if next_link else None
        license = "CC0 (Dryad data); see dataset terms"
    elif host == "osf.io" and re.fullmatch(r"/[a-z0-9]{5,}/?", path):
        source = "osf"
        ident = path.strip("/")
        endpoint = f"https://api.osf.io/v2/nodes/{ident}/"
        raw = http.get(endpoint)
        node = json.loads(raw)
        if not node.get("data", {}).get("attributes", {}).get("public"):
            return
        queue = [f"{endpoint}files/osfstorage/"]
        visited = set()
        while queue:
            page_url = queue.pop()
            if page_url in visited:
                continue
            visited.add(page_url)
            if len(visited) > 1000:
                raise ValueError("OSF folder traversal limit exceeded")
            page = http.json(page_url)
            if page.get("links", {}).get("next"):
                queue.append(page["links"]["next"])
            for item in page.get("data", []):
                if item["attributes"]["kind"] == "folder":
                    queue.append(item["relationships"]["files"]["links"]["related"]["href"])
                elif item.get("links", {}).get("download"):
                    files.append((item["links"]["download"], item["attributes"]["name"]))
    elif host in ("www.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov") and (
        m := re.search(r"\bGSE\d+\b", link)
    ):
        source = "geo"
        ident = m.group()
        prefix = ident[:-3] + "nnn"
        endpoint = f"https://ftp.ncbi.nlm.nih.gov/geo/series/{prefix}/{ident}/suppl/"
        # An official directory, reached through an explicit GEO accession link.
        listing = http.get(endpoint, download=True)
        from lxml import html

        tree = html.fromstring(listing)
        files = [
            (urljoin(endpoint, h), h)
            for h in tree.xpath("//a/@href")
            if not h.endswith("/") and not h.startswith(("?", "/", "http")) and ".." not in h
        ]
        raw = json.dumps({"accession": ident, "directory": endpoint}).encode()
    if raw is None:
        return
    record = collector.save(
        work,
        raw,
        source,
        endpoint,
        link,
        license,
        ".json",
        parent=parent,
        relation="paper data availability statement",
    )
    for url, filename in files:
        suffix = "".join(Path(filename).suffixes[-2:]) or ".bin"
        collector.save(
            work,
            http.get(url, download=True),
            source,
            url,
            link,
            license,
            suffix,
            parent=record,
            relation="repository record file link",
        )


def trials(collector, work, parent, text):
    for nct in sorted(set(re.findall(r"\bNCT\d{8}\b", text))):
        url = f"https://clinicaltrials.gov/api/v2/studies/{nct}"
        raw = collector.http.get(url)
        obj = json.loads(raw)
        if obj["protocolSection"]["identificationModule"]["nctId"] != nct:
            raise ValueError("Registry identifier mismatch")
        collector.save(
            work,
            raw,
            "clinicaltrials",
            url,
            nct,
            "ClinicalTrials.gov public data",
            ".json",
            parent=parent,
            relation="registry identifier in paper",
        )


def retraction_watch(collector, works):
    url = "https://gitlab.com/crossref/retraction-watch-data/-/raw/main/retraction_watch.csv"
    raw = collector.http.get(url, download=True)
    by_doi = {w.doi: w for w in works if w.doi}
    for record in csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))):
        for identifier in re.split(r"[;\s]+", record.get("OriginalPaperDOI", "")):
            w = by_doi.get(doi(identifier))
            if w:
                collector.save(
                    w,
                    json.dumps(record).encode(),
                    "retraction-watch",
                    url,
                    w.doi,
                    "Crossref Retraction Watch data; cite source",
                    ".json",
                )


def jats_assets(collector, work, parent):
    """Follow literal article graphics/supplement links; never guess asset filenames."""
    from lxml import etree

    from .acquisition import XML_PARSER

    tree = etree.fromstring(Path(parent.path).read_bytes(), XML_PARSER)
    hrefs = tree.xpath(
        '//graphic//@*[local-name()="href"] | //supplementary-material//@*[local-name()="href"] | //media//@*[local-name()="href"]'
    )
    known = {a.url for a in collector.artifacts if a.work_id == work.id}
    for href in hrefs:
        url = urljoin(parent.url, href)
        suffix = Path(urlsplit(url).path).suffix.lower()
        if url in known or suffix not in {
            ".png",
            ".jpg",
            ".jpeg",
            ".tiff",
            ".tif",
            ".pdf",
            ".xlsx",
            ".csv",
            ".tsv",
            ".zip",
        }:
            continue
        collector.save(
            work,
            collector.http.get(url, download=True),
            parent.source,
            url,
            parent.linking_identifier,
            parent.license,
            suffix,
            parent=parent,
            relation="literal JATS asset link",
        )
