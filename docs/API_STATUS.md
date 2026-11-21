# API audit — 2026-11-21

Official documentation was checked before implementation. Endpoints can change; individual
failures are recorded in each report's coverage log. Authentication failure is never treated
as an empty research record. Contact email is required for network runs.

| Source | Current contract and reference |
| --- | --- |
| OpenAlex | [API/authentication](https://help.openalex.org/api/authentication/): per_page maximum 100; cursor paging after first page requires a key; 10 requests/s keyless, 30/s free key. Bearer authentication keeps keys out of URLs. |
| ORCID | [Read API v3](https://info.orcid.org/documentation/api-tutorials/api-tutorial-read-data-on-a-record/): public record/works, optional configured read-public token; no writes. |
| PMC | [AWS documentation](https://pmc.ncbi.nlm.nih.gov/tools/pmcaws), [bucket README](https://pmc-oa-opendata.s3.amazonaws.com/README.txt): legacy FTP removed August 2026. List metadata/PMCID.version.json; follow xml_url/media_urls with per-version license. Anonymous HTTPS is equivalent to no-sign-request S3 access. |
| Europe PMC | [REST](https://europepmc.org/RestfulWebService): DOI search, PMCID/fullTextXML, PMCID/supplementaryFiles. Docs page returned 403 during audit; official service guide confirms XML and supplementary methods. |
| bioRxiv / medRxiv | [API](https://api.biorxiv.org/): details/{server}/{DOI}/na/json returns versions and JATS URL; pubs links published DOI to preprint DOI. |
| arXiv | [API manual](https://info.arxiv.org/help/api/user-manual.html), [bulk access](https://info.arxiv.org/help/bulk_data_s3.html): identifier-based source download; at least 3 seconds between requests. Individual license is not inferred from availability. |
| Unpaywall | [v2 API](https://unpaywall.org/products/api): DOI lookup with email, returned OA location/license; PDF fallback only. Main documentation is JavaScript rendered. |
| Elsevier | [Article API](https://dev.elsevier.com/documentation/ArticleRetrievalAPI.wadl): DOI endpoint, verified entitlement required; API key alone is insufficient. Optional adapter, only enabled with configured credentials; not live validated. |
| Springer Nature | [Developer portal](https://dev.springernature.com/): separate OA and licensed TDM APIs; optional adapter; not live validated. |
| Wiley | [TDM](https://onlinelibrary.wiley.com/library-info/resources/text-and-datamining): token, licensed PDF only, 60 requests per 10 minutes. Optional extension. |
| Dryad | [Official source documentation](https://github.com/datadryad/dryad-app/blob/main/documentation/apis/README.md): API v2 /datasets/{encoded DOI}, versions/files, paginated HAL links. |
| Zenodo | [API](https://developers.zenodo.org/): public records/{id}, files from returned links, record license; private deposits excluded. |
| figshare | [v2](https://docs.figshare.com/v2/): public articles/{id}, files/download_url, license. |
| OSF | [API v2](https://developer.osf.io/): public nodes/{id}/files, paginated file links; docs are JavaScript rendered. |
| GEO | [Downloads](https://www.ncbi.nlm.nih.gov/geo/info/download.html): accession-linked HTTPS FTP mirror; audit page returned a CAPTCHA. No CAPTCHA bypass or name search. |
| ClinicalTrials.gov | [API v2](https://clinicaltrials.gov/data-api/api): /api/v2/studies/{NCT}; registry current record does not prove historical outcome switching. |
| Crossref | [REST](https://www.crossref.org/documentation/retrieve-metadata/rest-api/), [updates](https://www.crossref.org/blog/retraction-watch-retractions-now-in-the-crossref-api/): updated-by, update-to; update-type:retraction identifies notices, not original works. |
| Retraction Watch | [Crossref data](https://www.crossref.org/documentation/retrieve-metadata/retraction-watch/), [CSV](https://gitlab.com/crossref/retraction-watch-data/-/blob/main/retraction_watch.csv): exact OriginalPaperDOI join; no name matching. |
| Anthropic | [Messages](https://platform.claude.com/docs/en/api/messages): POST /v1/messages, API version and model configurable. Only selected IDs and controlled review questions are accepted from the model. |

Transport uses conservative per-host pacing, robots checks for downloaded web resources,
bounded downloads, retry/backoff, and no authentication forwarding across redirects.
No claim of exhaustive collection is possible: unavailable, blocked, unlicensed and oversized
artifacts remain visible as coverage gaps.

OpenAlex inventory follow-up: the [default works view](https://help.openalex.org/data/works/pulled/)
excludes retracted, withdrawn and removed works starting November 19, 2026. Author inventory
queries explicitly use `include_pulled=true`, `include_parts=true` and `corpus=all` on every
page to retain pulled records, [linked component records and the expansion corpus](https://help.openalex.org/data/works/corpus/).
These additions are essential for coverage; publication status is still reported only through
identifier-linked detector results, not inferred from an author's publication count.
List responses also truncate bylines and locations. When truncation is reported, inventory
retrieves the single-work record before validating author membership or collecting location
links; an unconfirmed author relationship aborts rather than silently shortening the list.
See [authorship limits](https://help.openalex.org/data/authorships/).

PMC identifiers are normalized from both legacy numeric NCBI URLs and current `PMC`-prefixed
URLs. The S3 adapter accepts the OA subset and explicitly marked `TDM` author manuscripts,
preserves the source license, and retrieves any listed PDF after XML and media. It does not
infer permission to redistribute manuscripts. Text-only XML does not suppress PDF fallback;
Unpaywall copies are tried independently so a failed location cannot hide another legal copy.
