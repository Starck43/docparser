import tempfile
from pathlib import Path

from app.services import parser


def test_txt_parser():
    with tempfile.NamedTemporaryFile("w+", suffix=".txt", delete=False) as f:
        f.write("hello world")
        f.flush()
        text = parser.parse_file(Path(f.name))
        assert "hello world" in text
