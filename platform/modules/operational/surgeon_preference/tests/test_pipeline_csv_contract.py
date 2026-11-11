import pytest

from orchestration.minio_medallion_pipeline import MinIOMedallionPipeline


def pipeline():
    return MinIOMedallionPipeline.__new__(MinIOMedallionPipeline)


def test_csv_source_requires_surgeon_and_procedure_identity_columns(tmp_path):
    source = tmp_path / "renamed_schema.csv"
    source.write_text("operator,operation\nA. Surgeon,Hip replacement\n", encoding="utf-8")

    with pytest.raises(ValueError, match="surgeon_name or surgeon"):
        pipeline()._extract_records(source)


def test_csv_source_normalises_headers_and_supports_known_identity_aliases(tmp_path):
    source = tmp_path / "preference.csv"
    source.write_text(
        " Surgeon Name ,Procedure\nA. Surgeon,Hip replacement\n",
        encoding="utf-8",
    )

    assert pipeline()._extract_records(source) == [
        {"surgeon_name": "A. Surgeon", "procedure": "Hip replacement"}
    ]


def test_csv_source_rejects_duplicate_normalised_headers(tmp_path):
    source = tmp_path / "duplicate_headers.csv"
    source.write_text(
        "surgeon_name,Surgeon Name,procedure_name\nA,B,Hip replacement\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate column names"):
        pipeline()._extract_records(source)


def test_csv_source_rejects_rows_with_extra_values(tmp_path):
    source = tmp_path / "extra_values.csv"
    source.write_text(
        "surgeon_name,procedure_name\nA. Surgeon,Hip replacement,unexpected\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="row 2 has more values"):
        pipeline()._extract_records(source)
