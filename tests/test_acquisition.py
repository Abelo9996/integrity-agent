import json
from unittest.mock import Mock

import httpx
import pytest

from integrity_agent.acquisition import Collector, pmcid, resolve, works
from integrity_agent.models import Author, Work
from integrity_agent.transport import AccessError, Transport


def test_cache_and_cross_host_secret_stripping(tmp_path, monkeypatch):
    seen = []

    def handler(req):
        seen.append(req)
        if req.url.host == "example.org":
            return httpx.Response(302, headers={"Location": "https://example.net/file"})
        return httpx.Response(200, content=b"synthetic")

    monkeypatch.setattr(Transport, "validate_url", lambda self, url: None)
    t = Transport(
        tmp_path,
        "reviewer@synthetic.invalid",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        interval=0,
    )
    assert (
        t.get("https://example.org/file", headers={"Authorization": "Bearer test-only"})
        == b"synthetic"
    )
    assert "Authorization" not in seen[-1].headers
    t.get("https://example.org/file", headers={"Authorization": "Bearer test-only"})
    assert len(seen) == 2
    t.close()


def test_size_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(Transport, "validate_url", lambda self, url: None)
    t = Transport(
        tmp_path,
        "reviewer@synthetic.invalid",
        client=httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"1234"))
        ),
        interval=0,
    )
    with pytest.raises(AccessError):
        t.get("https://example.org", limit=2)
    t.close()


def test_shared_cache_coordinates_host_pacing(tmp_path, monkeypatch):
    import integrity_agent.transport as transport

    sleeps = []
    monkeypatch.setattr(transport.time, "time", lambda: 1000.0)
    monkeypatch.setattr(transport.time, "sleep", lambda delay: sleeps.append(delay))
    clients = [Transport(tmp_path, "reviewer@synthetic.invalid", interval=1) for _ in range(2)]
    try:
        clients[0]._pace("example.org")
        clients[1]._pace("example.org")
        clients[1]._pace("example.net")
        assert sleeps == [0, 1, 0]
        clients[0].interval = 5
        clients[0]._pace("example.org")
        clients[1]._pace("example.org")
        assert sleeps[-2:] == [6, 11]
    finally:
        for client in clients:
            client.close()


def test_robots_denial(tmp_path, monkeypatch):
    monkeypatch.setattr(Transport, "validate_url", lambda self, url: None)
    t = Transport(
        tmp_path,
        "reviewer@synthetic.invalid",
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(200, text="User-agent: *\nDisallow: /")
            )
        ),
        interval=0,
    )
    with pytest.raises(AccessError, match="disallows"):
        t.get("https://example.org/file", download=True)
    t.close()


def test_reject_private_urls():
    with pytest.raises(AccessError):
        Transport.validate_url("https://127.0.0.1/a")
    with pytest.raises(AccessError):
        Transport.validate_url("file:///etc/passwd")


def test_identifier_link_required(tmp_path):
    collector = Collector(Mock(), tmp_path)
    w = Work(id="W1", title="Synthetic", author_id="A1")
    with pytest.raises(ValueError):
        collector.save(w, b"x", "test", "https://example.org", "Same Name", "CC0", ".bin")
    a = collector.save(w, b"x", "test", "https://example.org", "W1", "CC0", ".bin")
    assert a.sha256
    assert json.loads((tmp_path / "manifest.jsonl").read_text())["linking_identifier"] == "W1"


def test_work_pagination_and_author_filter(monkeypatch):
    monkeypatch.setenv("OPENALEX_API_KEY", "test-only")
    h = Mock()
    item = {"id": "W1", "title": "Synthetic", "authorships": [{"author": {"id": "A1"}}]}
    h.json.side_effect = [
        {"results": [item], "meta": {"next_cursor": "next"}},
        {"results": [], "meta": {"next_cursor": None}},
    ]
    result = works(h, Author(id="A1", name="Synthetic"))
    assert len(result) == 1
    assert h.json.call_count == 2


def test_unconfirmed_name_never_resolves_works():
    h = Mock()
    h.json.return_value = {"results": [{"id": "A1", "display_name": "Synthetic"}]}
    assert resolve(h, name="Synthetic")[0].id == "A1"
    assert h.json.call_args.args[0].endswith("/authors")


@pytest.mark.parametrize(
    "value",
    [
        "PMC999999999",
        "999999999",
        "https://www.ncbi.nlm.nih.gov/pmc/articles/999999999",
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC999999999/",
    ],
)
def test_pmc_identifier_normalization(value):
    assert pmcid(value) == "PMC999999999"


def test_pmc_location_resolves_missing_external_identifier():
    h = Mock()
    h.json.return_value = {
        "results": [
            {
                "id": "W1",
                "title": "Synthetic",
                "authorships": [{"author": {"id": "A1"}}],
                "locations": [
                    {"landing_page_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC999999999/"}
                ],
            }
        ],
        "meta": {"count": 1},
    }
    assert works(h, Author(id="A1", name="Synthetic"))[0].pmcid == "PMC999999999"


def test_truncated_byline_is_expanded_before_author_verification():
    h = Mock()
    h.json.side_effect = [
        {
            "results": [{"id": "W1", "is_authors_truncated": True, "authorships": []}],
            "meta": {"count": 1},
        },
        {"id": "W1", "title": "Synthetic consortium", "authorships": [{"author": {"id": "A1"}}]},
    ]
    assert [w.id for w in works(h, Author(id="A1", name="Synthetic"))] == ["W1"]
    assert h.json.call_args.args[0] == "https://api.openalex.org/works/W1"


def test_unverified_filtered_work_aborts_instead_of_silent_omission():
    h = Mock()
    h.json.return_value = {"results": [{"id": "W1", "authorships": []}], "meta": {"count": 1}}
    with pytest.raises(AccessError, match="confirmed author link"):
        works(h, Author(id="A1", name="Synthetic"))


def test_author_inventory_includes_hidden_records_on_every_page(monkeypatch):
    monkeypatch.setenv("OPENALEX_API_KEY", "test-only")
    h = Mock()

    def page(url, *, params, headers):
        assert params["include_pulled"] == "true"
        assert params["include_parts"] == "true"
        assert params["corpus"] == "all"
        first = params["cursor"] == "*"
        return {
            "results": [
                {
                    "id": "W1" if first else "W2",
                    "title": "Synthetic withdrawn work" if first else "Synthetic linked dataset",
                    "is_pulled": first,
                    "is_xpac": not first,
                    "authorships": [{"author": {"id": "A1"}}],
                }
            ],
            "meta": {"count": 2, "next_cursor": "next" if first else None},
        }

    h.json.side_effect = page
    assert [w.id for w in works(h, Author(id="A1", name="Synthetic"))] == ["W1", "W2"]
    assert h.json.call_count == 2


def test_pmc_current_bucket_schema_and_exact_identifier(tmp_path):
    http = Mock()
    base = "https://pmc-oa-opendata.s3.amazonaws.com/"
    listing = b"<ListBucketResult><Contents><Key>metadata/PMC999999999.1.json</Key></Contents></ListBucketResult>"
    meta = {
        "pmcid": "PMC999999999",
        "doi": "10.synthetic/paper",
        "is_pmc_openaccess": True,
        "license_code": "CC BY",
        "xml_url": base + "PMC999999999.1/PMC999999999.1.xml",
        "media_urls": [base + "PMC999999999.1/figure.jpg"],
    }
    http.get.side_effect = [
        listing,
        json.dumps(meta).encode(),
        b"<article/>",
        b"synthetic-image-bytes",
    ]
    c = Collector(http, tmp_path)
    w = Work(
        id="W1", title="Synthetic", author_id="A1", doi="10.synthetic/paper", pmcid="PMC999999999"
    )
    c.pmc(w)
    assert len(c.artifacts) == 3
    assert all(a.linking_identifier == w.pmcid for a in c.artifacts)
    assert c.artifacts[-1].parent_artifact_id == c.artifacts[0].artifact_id


def test_cache_corruption_redownloaded(tmp_path, monkeypatch):
    monkeypatch.setattr(Transport, "validate_url", lambda self, url: None)
    count = []

    def handler(r):
        count.append(1)
        return httpx.Response(200, content=b"original")

    t = Transport(
        tmp_path,
        "reviewer@synthetic.invalid",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        interval=0,
    )
    t.get("https://example.org/file")
    next(tmp_path.glob("*.blob")).write_bytes(b"changed")
    assert t.get("https://example.org/file") == b"original"
    assert len(count) == 2
    t.close()


def test_pmc_explicit_tdm_manuscript_and_pdf_are_retained(tmp_path):
    http = Mock()
    base = "https://pmc-oa-opendata.s3.amazonaws.com/"
    meta = {
        "pmcid": "PMC999999999",
        "is_pmc_openaccess": False,
        "is_manuscript": True,
        "license_code": "TDM",
        "xml_url": base + "PMC999999999.1/paper.xml",
        "pdf_url": base + "PMC999999999.1/paper.pdf",
    }
    http.get.side_effect = [
        b"<ListBucketResult><Contents><Key>metadata/PMC999999999.1.json</Key></Contents></ListBucketResult>",
        json.dumps(meta).encode(),
        b"<article/>",
        b"%PDF-synthetic",
    ]
    c = Collector(http, tmp_path)
    c.pmc(Work(id="W1", title="Synthetic", author_id="A1", pmcid="PMC999999999"))
    assert len(c.artifacts) == 3
    assert all(a.license == "TDM" for a in c.artifacts)
    assert c.artifacts[-1].path.endswith(".pdf")


def test_missing_pmc_asset_does_not_hide_later_media(tmp_path):
    http = Mock()
    base = "https://pmc-oa-opendata.s3.amazonaws.com/"
    meta = {
        "pmcid": "PMC999999999",
        "is_pmc_openaccess": True,
        "license_code": "CC BY",
        "xml_url": base + "PMC999999999.1/paper.xml",
        "media_urls": [base + "PMC999999999.1/missing.jpg", base + "PMC999999999.1/available.jpg"],
    }
    http.get.side_effect = [
        b"<ListBucketResult><Contents><Key>metadata/PMC999999999.1.json</Key></Contents></ListBucketResult>",
        json.dumps(meta).encode(),
        AccessError("missing XML"),
        AccessError("missing image"),
        b"synthetic-image",
    ]
    c = Collector(http, tmp_path)
    c.pmc(Work(id="W1", title="Synthetic", author_id="A1", pmcid="PMC999999999"))
    assert len(c.artifacts) == 2
    assert c.artifacts[-1].url.endswith("available.jpg")
    assert [row.status for row in c.coverage] == ["failed", "failed", "ok"]


def test_supplement_zip_does_not_suppress_pdf_fallback(tmp_path):
    http = Mock()
    http.get.side_effect = [
        json.dumps(
            {
                "doi": "10.synthetic/paper",
                "oa_locations": [{"url_for_pdf": "https://example.org/paper.pdf"}],
            }
        ).encode(),
        b"%PDF-synthetic",
    ]
    c = Collector(http, tmp_path)
    w = Work(id="W1", title="Synthetic", author_id="A1", doi="10.synthetic/paper")
    c.save(w, b"supplement", "europe-pmc", "https://example.org/supplement", w.id, "CC0", ".zip")
    c.unpaywall(w)
    assert c.artifacts[-1].path.endswith(".pdf")


def test_openalex_pdf_requires_oa_and_records_exact_parent(tmp_path):
    http = Mock()
    metadata = {
        "id": "https://openalex.org/W1",
        "authorships": [{"author": None}, {"author": {"id": "https://openalex.org/A1"}}],
        "locations": [
            {"is_oa": False, "pdf_url": "https://example.org/paywall.pdf"},
            {"is_oa": True, "pdf_url": "https://example.org/blocked.pdf"},
            {"is_oa": True, "pdf_url": "http://example.org/open.pdf", "license": "cc-by"},
        ],
    }
    http.get.side_effect = [
        json.dumps(metadata).encode(),
        AccessError("robots denies access"),
        b"%PDF-synthetic",
    ]
    c = Collector(http, tmp_path)
    c.openalex_pdf(Work(id="W1", title="Synthetic", author_id="A1"))
    assert len(c.artifacts) == 2
    artifact = c.artifacts[-1]
    assert artifact.url == "https://example.org/open.pdf"
    assert artifact.parent_artifact_id == c.artifacts[0].artifact_id
    assert artifact.linking_identifier == "W1"
    assert artifact.license == "cc-by"
    assert http.get.call_args.kwargs == {"download": True}
    assert not any("paywall.pdf" in call.args[0] for call in http.get.call_args_list)
    assert [row.status for row in c.coverage] == ["failed", "ok"]


@pytest.mark.parametrize(
    "record",
    [
        {"id": "W2", "authorships": [{"author": {"id": "A1"}}]},
        {"id": "W1", "authorships": [{"author": {"id": "A2"}}]},
        {"id": "W1", "doi": "10.synthetic/wrong", "authorships": [{"author": {"id": "A1"}}]},
    ],
)
def test_openalex_pdf_rejects_mismatched_links(tmp_path, record):
    http = Mock()
    http.get.return_value = json.dumps(record).encode()
    c = Collector(http, tmp_path)
    with pytest.raises(ValueError):
        c.openalex_pdf(Work(id="W1", title="Synthetic", author_id="A1", doi="10.synthetic/paper"))
    assert not c.artifacts
    assert http.get.call_count == 1


def test_zenodo_doi_link_retains_paper_provenance(tmp_path):
    from integrity_agent.repositories import linked_repository

    http = Mock()
    http.get.side_effect = [
        json.dumps(
            {
                "metadata": {"license": {"id": "cc-by-4.0"}},
                "files": [
                    {
                        "key": "synthetic.csv",
                        "links": {
                            "self": "https://zenodo.org/api/records/999999999/files/synthetic.csv/content"
                        },
                    }
                ],
            }
        ).encode(),
        b"x\n1\n",
    ]
    c = Collector(http, tmp_path)
    w = Work(id="W1", title="Synthetic", author_id="A1")
    parent = c.save(
        w, b"<article/>", "synthetic", "https://example.org/paper.xml", "W1", "CC0", ".xml"
    )
    linked_repository(c, w, parent, "https://doi.org/10.5281/zenodo.999999999")
    assert len(c.artifacts) == 3
    assert c.artifacts[-1].linking_identifier == "https://doi.org/10.5281/zenodo.999999999"
    assert c.artifacts[-1].parent_artifact_id == c.artifacts[1].artifact_id
    assert http.get.call_args_list[0].args[0] == "https://zenodo.org/api/records/999999999"


def test_complete_first_page_works_without_key(monkeypatch):
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    h = Mock()
    h.json.return_value = {
        "results": [{"id": "W1", "title": "Synthetic", "authorships": [{"author": {"id": "A1"}}]}],
        "meta": {"count": 1, "next_cursor": "unused"},
    }
    assert len(works(h, Author(id="A1", name="Synthetic"))) == 1
    assert h.json.call_count == 1


def test_xml_without_images_keeps_pdf_fallback_and_tries_other_copies(tmp_path):
    h = Mock()
    h.get.side_effect = [
        json.dumps(
            {
                "doi": "10.synthetic/paper",
                "oa_locations": [
                    {"url_for_pdf": "https://example.org/denied.pdf"},
                    {"url_for_pdf": "http://example.net/available.pdf", "license": "cc-by"},
                ],
            }
        ).encode(),
        AccessError("HTTP 403 from example.org"),
        b"%PDF-synthetic",
    ]
    c = Collector(h, tmp_path)
    w = Work(id="W1", title="Synthetic", author_id="A1", doi="10.synthetic/paper")
    c.save(w, b"<article/>", "pmc", "https://example.org/paper.xml", w.id, "TDM", ".xml")
    c.unpaywall(w)
    assert c.artifacts[-1].path.endswith(".pdf")
    assert c.artifacts[-1].url == "https://example.net/available.pdf"
    assert [item.status for item in c.coverage] == ["failed", "ok"]


def test_partial_first_page_requires_key(monkeypatch):
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    h = Mock()
    h.json.return_value = {
        "results": [{"id": "W1", "title": "Synthetic", "authorships": [{"author": {"id": "A1"}}]}],
        "meta": {"count": 2, "next_cursor": "next"},
    }
    with pytest.raises(AccessError, match="partial lists"):
        works(h, Author(id="A1", name="Synthetic"))


@pytest.mark.parametrize("prepaid, successful", [(0, True), (1, False)])
def test_openalex_archive_is_exact_and_free(tmp_path, monkeypatch, prepaid, successful):
    monkeypatch.setenv("OPENALEX_API_KEY", "synthetic-key")
    http = Mock()
    url = "https://content.openalex.org/works/W1.pdf"
    metadata = {
        "id": "https://openalex.org/W1",
        "authorships": [{"author": {"id": "https://openalex.org/A1"}}],
        "open_access": {"is_oa": True},
        "content_urls": {"pdf": url},
        "best_oa_location": {"license": "cc-by"},
    }
    http.json.return_value = {
        "rate_limit": {
            "prepaid_remaining_usd": prepaid,
            "daily_remaining_usd": 0.01,
            "endpoint_costs_usd": {"content": 0.01},
        }
    }
    http.get.side_effect = [json.dumps(metadata).encode(), b"%PDF-synthetic\n%%EOF"]
    c = Collector(http, tmp_path)
    work = Work(id="W1", title="Synthetic", author_id="A1")
    c.openalex_pdf(work)
    calls = [call for call in http.get.call_args_list if call.args == (url,)]
    assert bool(calls) is successful
    if successful:
        assert calls[0].kwargs == {
            "headers": {"Authorization": "Bearer synthetic-key"},
            "download": True,
        }
        assert c.artifacts[-1].source == "openalex-archive"
        assert c.artifacts[-1].parent_artifact_id == c.artifacts[0].artifact_id
        assert c.artifacts[-1].url == url
        assert c.artifacts[-1].license == "cc-by"
        assert c.openalex_pdf_allowance == 0
    else:
        assert c.coverage[-1].status == "failed"
