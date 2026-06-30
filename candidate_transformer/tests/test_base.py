import pytest
from candidate_transformer.sources import BaseSource, CSVSource

def test_base_source_cannot_be_instantiated():
    """Verify that BaseSource is abstract and cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BaseSource()

def test_incomplete_subclass_raises_error():
    """Verify that a subclass without 'extract' implementation raises TypeError on instantiation."""
    class IncompleteSource(BaseSource):
        pass

    with pytest.raises(TypeError):
        IncompleteSource()

def test_csv_source_extract_returns_source_name(tmp_path):
    """Verify that CSVSource can be instantiated and returns source_name."""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("name,email\nAlice,alice@example.com\n", encoding="utf-8")
    source = CSVSource()
    res = source.extract(str(csv_file))
    assert isinstance(res, dict)
    assert res.get("source_name") == "recruiter_csv"
