"""Test that sample job fixtures validate against the JSON schema.

Catches schema drift — if the schema or fixtures are updated independently,
this test fails rather than silently shipping an invalid contract.

Fork note: the fork's fixture is `sample_all_jobs_with_feasibility_tags.json`
and the fork's schema includes feasibility fields (feasible, feasibility,
feasibility_error). This test validates the fork's actual contract.
"""
import json
from pathlib import Path

import pytest

SCHEMA_PATH = Path(__file__).parent.parent / "schema" / "jobs.schema.json"
FIXTURES_DIR = Path(__file__).parent / "fixtures"
# Fork uses a feasibility-tagged fixture; the schema includes feasibility fields.
SAMPLE_FIXTURE = FIXTURES_DIR / "sample_all_jobs_with_feasibility_tags.json"


def _load_schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _try_jsonschema():
    try:
        import jsonschema
        return jsonschema
    except ImportError:
        return None


def test_schema_is_valid_json():
    """The schema file itself must be valid JSON."""
    schema = _load_schema()
    assert isinstance(schema, dict)
    assert "properties" in schema
    assert "required" in schema


def test_sample_all_jobs_validate():
    """Every job in the sample fixture must validate against the schema."""
    schema = _load_schema()
    sample = json.loads(SAMPLE_FIXTURE.read_text(encoding="utf-8"))
    jsonschema = _try_jsonschema()
    required = schema.get("required", [])

    for i, job in enumerate(sample["jobs"]):
        if jsonschema:
            jsonschema.validate(job, schema)
        else:
            # Fallback: check required fields exist
            for field in required:
                assert field in job, f"Job {i} missing required field: {field}"


def test_schema_required_fields_minimal():
    """Schema should require only the essential identity fields."""
    schema = _load_schema()
    required = schema["required"]
    # These are the minimum fields needed to identify a job
    assert "url" in required
    assert "title" in required
    assert "company" in required
    assert "ats" in required
    assert "first_seen" in required


def test_schema_includes_fork_feasibility_fields():
    """Fork-specific feasibility fields must remain in the schema.

    The fork has a feasibility checker that tags jobs with feasibility
    verdicts. The schema must continue to allow these fields so the
    fixture (and real output) validates. This guards against accidentally
    porting the upstream commit that removed feasibility fields.
    """
    schema = _load_schema()
    properties = schema["properties"]
    assert "feasible" in properties, "Schema must include 'feasible' (fork feature)"
    assert "feasibility" in properties, "Schema must include 'feasibility' (fork feature)"


def test_schema_keeps_job_schema_doc_reference():
    """The schema description must keep the docs/JOB_SCHEMA.md reference.

    The fork ships docs/JOB_SCHEMA.md as the canonical field contract.
    This guards against accidentally porting the upstream fix that
    removed the reference.
    """
    schema = _load_schema()
    assert "docs/JOB_SCHEMA.md" in schema.get("description", ""), (
        "Schema description must reference docs/JOB_SCHEMA.md (fork contract)"
    )
