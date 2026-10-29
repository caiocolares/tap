"""Regressões para conflitos de merge e definições duplicadas nos manifests."""

import ast
import re
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_project_has_no_merge_markers_or_invalid_source():
    extensions = {".py", ".toml", ".lock", ".yml", ".yaml", ".md"}
    files = [
        path
        for path in ROOT.iterdir()
        if path.is_file()
        and (path.suffix in extensions or path.name.startswith("Dockerfile") or path.name == ".env.example")
    ]
    for path in files:
        text = path.read_text()
        assert not re.search(r"(?m)^(?:<{7}|={7}|>{7})(?: |$)", text), str(path)
        if path.suffix == ".py":
            ast.parse(text, filename=str(path))
    tomllib.loads((ROOT / "pyproject.toml").read_text())
    tomllib.loads((ROOT / "uv.lock").read_text())


class UniqueKeyLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        seen = set()
        for key, _ in node.value:
            if key.tag == "tag:yaml.org,2002:merge":
                continue
            assert key.value not in seen, f"Chave YAML duplicada: {key.value}"
            seen.add(key.value)
        return super().construct_mapping(node, deep=deep)


def test_deployment_and_ci_yaml_have_no_duplicate_keys():
    files = [
        ROOT / "docker-compose.yml",
        ROOT / "knative-service.yaml",
        *ROOT.glob("deploy/*.yaml"),
        *ROOT.glob(".github/workflows/*.yml"),
    ]
    for path in files:
        list(yaml.load_all(path.read_text(), Loader=UniqueKeyLoader))
