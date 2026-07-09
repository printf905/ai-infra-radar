from pathlib import Path

from radar.config import load_config


def test_load_config_from_yaml(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        """
database_path: data/test.sqlite
arxiv:
  queries:
    - cat:cs.LG
github:
  enabled: false
tagging:
  keywords:
    inference:
      - serving
""",
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.database_path == Path("data/test.sqlite")
    assert config.arxiv.queries == ["cat:cs.LG"]
    assert config.github.enabled is False
    assert config.tagging.keywords["inference"] == ["serving"]
