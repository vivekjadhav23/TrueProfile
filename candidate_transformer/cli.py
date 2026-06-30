import sys
import json
from pathlib import Path
import click
from jsonschema import validate as js_validate

@click.group()
@click.version_option(version="1.0.0", prog_name="candidate-transformer", message="%(prog)s %(version)s")
def main():
    """
    Candidate Transformer CLI tool.
    Extracts, normalizes, merges, and scores candidate profile details from raw sources.
    """
    pass

@main.command()
@click.option('--csv', type=click.Path(exists=True), help='Path to recruiter CSV')
@click.option('--ats', type=click.Path(exists=True), help='Path to ATS JSON file')
@click.option('--github', type=click.STRING, help='GitHub username or URL')
@click.option('--resume', type=click.Path(exists=True), help='Path to resume PDF/DOCX/TXT')
@click.option('--notes', type=click.Path(exists=True), help='Path to recruiter notes TXT')
@click.option('--config', type=click.Path(exists=True), help='Path to output config JSON (optional)')
@click.option('--output', type=click.Path(), help='Output file path (default: stdout)')
@click.option('--pretty', is_flag=True, help='Pretty-print JSON output')
def transform(csv, ats, github, resume, notes, config, output, pretty):
    """
    Transform candidate raw data from provided sources.
    """
    inputs = []
    if csv:
        inputs.append({"type": "csv", "path": str(Path(csv))})
    if ats:
        inputs.append({"type": "ats_json", "path": str(Path(ats))})
    if github:
        inputs.append({"type": "github", "url": github})
    if resume:
        inputs.append({"type": "resume", "path": str(Path(resume))})
    if notes:
        inputs.append({"type": "recruiter_notes", "path": str(Path(notes))})

    if not inputs:
        click.echo("Error: Please specify at least one candidate source parameter (e.g. --csv, --github, --resume, etc.)", err=True)
        sys.exit(1)

    try:
        from candidate_transformer.pipeline.extractor import Pipeline
        
        # 2. Instantiate Pipeline(config_path)
        pipeline = Pipeline(config_path=config)

        # 3. Call pipeline.run(inputs)
        result = pipeline.run(inputs)

        # 4. Print/write JSON output
        indent = 2 if pretty else None
        output_str = json.dumps(result, indent=indent, ensure_ascii=False)

        if output:
            output_path = Path(output)
            with output_path.open(mode='w', encoding='utf-8') as f:
                f.write(output_str)
        else:
            click.echo(output_str)

        # 5. Print summary to stderr
        unique_sources = getattr(pipeline, "unique_sources_count", 0)
        if not unique_sources and "provenance" in result:
            provenance = result.get("provenance", [])
            unique_sources = len({entry.get("source") for entry in provenance if entry.get("source")})
        overall_conf = result.get("overall_confidence", 0.0)
        click.echo(f"✓ Merged {unique_sources} sources | confidence: {overall_conf:.2f}", err=True)

        sys.exit(0)

    except Exception as e:
        click.echo(f"Fatal Error: {e}", err=True)
        sys.exit(1)

@main.command()
@click.option('--output', required=True, type=click.Path(exists=True), help='Path to candidate JSON file to validate')
def validate(output):
    """
    Validates a JSON file against the default output schema, prints pass/fail.
    """
    try:
        # Load output candidate JSON
        output_path = Path(output)
        with output_path.open(mode='r', encoding='utf-8') as f:
            data = json.load(f)

        # Resolve path to output_schema.json using pathlib.Path
        base_path = Path(__file__).resolve().parent
        schema_path = base_path / "schemas" / "output_schema.json"

        with schema_path.open(mode='r', encoding='utf-8') as sf:
            schema = json.load(sf)

        # Validate against schema
        js_validate(instance=data, schema=schema)
        click.echo("Validation status: PASS")
        sys.exit(0)
    except Exception as e:
        click.echo("Validation status: FAIL", err=True)
        click.echo(f"Details: {e}", err=True)
        sys.exit(1)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        click.echo(f"Fatal Error: An unexpected error occurred: {e}", err=True)
        sys.exit(1)
