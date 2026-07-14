from pathlib import Path
import tomllib

import llmwiki


def test_public_package_identity_and_version():
    project = tomllib.loads(Path("pyproject.toml").read_text("utf-8"))["project"]
    assert project["name"] == "my-second-brain-by-yfw"
    assert project["version"] == "1.0.0"
    assert llmwiki.__version__ == "1.0.0"
