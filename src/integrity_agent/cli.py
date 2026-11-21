"""Local-only CLI. Author acquisition always requires explicit identity confirmation."""

from __future__ import annotations

import json
import os
from pathlib import Path

import typer
from dotenv import load_dotenv

from .acquisition import Collector, field_baselines, orcid_record, resolve, works
from .evaluation import evaluate, save_demo_images
from .models import Author, Coverage, Work, stable_id
from .pipeline import analyze
from .repositories import retraction_watch
from .transport import AccessError, Transport

app = typer.Typer(no_args_is_help=True)


@app.command()
def run(
    orcid: str | None = None,
    openalex_id: str | None = None,
    name: str | None = None,
    confirm_author: str | None = None,
    llm: bool = False,
    review_input: Path | None = None,
    max_works: int | None = None,
    with_retraction_watch: bool = True,
    with_field_baseline: bool = True,
):
    """Resolve an author, require confirmation, and write private local evidence reports."""
    load_dotenv()
    if max_works is not None and max_works <= 0:
        raise typer.BadParameter("--max-works must be positive")
    http = None
    try:
        http = Transport(Path("cache"), os.getenv("INTEGRITY_CONTACT_EMAIL", ""))
        candidates = resolve(http, name=name, orcid=orcid, openalex_id=openalex_id)
        if orcid:
            try:
                record = orcid_record(http, orcid)
                public_name = record.get("person", {}).get("name") or {}
                typer.echo(
                    "ORCID public record: "
                    + str(
                        public_name.get("credit-name")
                        or public_name.get("given-names")
                        or "name unavailable"
                    )
                )
            except (AccessError, ValueError):
                typer.echo("ORCID public record unavailable; review the candidate carefully.")
        if not candidates:
            raise ValueError("No candidate author profiles found")
        for a in candidates:
            typer.echo(
                f"{a.id} | {a.name} | ORCID: {a.orcid} | {a.works_count} works | {', '.join(a.institutions)}"
            )
        chosen_id = confirm_author or typer.prompt("Confirm by typing the exact OpenAlex author ID")
        chosen = next(
            (a for a in candidates if a.id.rsplit("/", 1)[-1] == chosen_id.rsplit("/", 1)[-1]), None
        )
        if chosen is None:
            raise ValueError("Confirmation must match a displayed candidate")
        typer.echo("Retrieving complete identifier-linked works list…")
        all_works = works(http, chosen)
        selected = all_works[:max_works] if max_works else all_works
        run_id = stable_id("run", [chosen.id])
        collector = Collector(http, Path("data") / run_id)
        output = Path("outputs") / run_id
        output.mkdir(parents=True, exist_ok=True)
        (output / "works.json").write_text(
            json.dumps([w.model_dump(mode="json") for w in all_works], indent=2)
        )
        if max_works and len(selected) < len(all_works):
            collector.coverage.append(
                Coverage(
                    work_id=chosen.id,
                    source="work limit",
                    status="skipped",
                    detail=f"Explicit limit: analyzed {len(selected)} of {len(all_works)} indexed works",
                )
            )
        for i, w in enumerate(selected, 1):
            typer.echo(f"Collecting work {i}/{len(selected)}: {w.id}")
            collector.collect(w)
            from .tdm import publisher_tdm

            publisher_tdm(collector, w)
        if with_retraction_watch and selected:
            collector.attempt(
                selected[0], "retraction-watch", lambda: retraction_watch(collector, selected)
            )
        if with_field_baseline and selected and not max_works:
            collector.attempt(
                selected[0], "field-baseline", lambda: field_baselines(collector, selected)
            )
        report = analyze(collector, chosen, selected, output, llm=llm, review_input=review_input)
        typer.echo(f"{output / 'report.html'}\n{output / 'report.json'}")
        typer.echo(
            f"Verifier accepted {report['verification']['accepted']} claims; removed {len(report['verification']['rejected'])}."
        )
    except (AccessError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    finally:
        if http:
            http.close()


@app.command()
def demo():
    """Run a completely offline synthetic two-paper example."""
    from unittest.mock import Mock

    root = Path("outputs/demo")
    paths = save_demo_images(Path("data/demo-input"))
    author = Author(id="synthetic-author", name="Synthetic Researcher")
    ws = [
        Work(
            id=f"synthetic-work-{i}",
            title=f"Synthetic microscopy example {i}",
            year=2020 + i,
            venue="Synthetic Journal",
            author_id=author.id,
        )
        for i in (1, 2)
    ]
    collector = Collector(Mock(), Path("data/demo"))
    for w, path in zip(ws, paths, strict=True):
        collector.save(
            w,
            path.read_bytes(),
            "synthetic",
            f"synthetic:{path.name}",
            w.id,
            "Apache-2.0 generated fixture",
            ".png",
        )
    report = analyze(collector, author, ws, root, network=False)
    typer.echo(
        f"{root / 'report.html'}\n{root / 'report.json'}\n{report['verification']['accepted']} verified claims"
    )


@app.command()
def evaluate_images(seeds: int = 12):
    """Measure procedural manipulation recall and unrelated-image false positives."""
    if seeds < 1:
        raise typer.BadParameter("seeds must be positive")
    typer.echo(json.dumps(evaluate(Path("outputs/evaluation"), seeds=seeds), indent=2))


if __name__ == "__main__":
    app()
