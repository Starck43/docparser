import tempfile
from pathlib import Path

from app.services import utils


def test_txt_parser():
    with tempfile.NamedTemporaryFile("w+", suffix=".txt", delete=False) as f:
        f.write("hello world")
        f.flush()
        text = utils.parse_file(Path(f.name))
        assert "hello world" in text
