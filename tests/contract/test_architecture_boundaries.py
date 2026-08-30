from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src/daily_dash"


def _daily_dash_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("daily_dash.")
        ):
            imports.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("daily_dash."):
                    imports.add(alias.name)
    return imports


def _assert_no_layer_imports(layer: str, forbidden: tuple[str, ...]) -> None:
    for path in sorted((SRC / layer).glob("*.py")):
        for imported in _daily_dash_imports(path):
            assert not imported.startswith(forbidden), f"{path}: forbidden dependency {imported}"


def test_presentation_is_a_pure_rendering_layer() -> None:
    _assert_no_layer_imports(
        "presentation",
        (
            "daily_dash.retrieval",
            "daily_dash.processing",
            "daily_dash.llm",
            "daily_dash.storage",
            "daily_dash.pipelines",
            "daily_dash.delivery",
        ),
    )


def test_processing_does_not_call_external_or_presentation_layers() -> None:
    _assert_no_layer_imports(
        "processing",
        (
            "daily_dash.retrieval",
            "daily_dash.llm",
            "daily_dash.presentation",
            "daily_dash.storage",
            "daily_dash.delivery",
        ),
    )


def test_llm_adapters_do_not_depend_on_processing_or_presentation() -> None:
    _assert_no_layer_imports(
        "llm",
        (
            "daily_dash.processing",
            "daily_dash.retrieval",
            "daily_dash.presentation",
            "daily_dash.storage",
            "daily_dash.pipelines",
            "daily_dash.delivery",
        ),
    )


def test_pipelines_orchestrate_but_never_render_or_deliver() -> None:
    _assert_no_layer_imports(
        "pipelines",
        (
            "daily_dash.presentation",
            "daily_dash.delivery",
        ),
    )


def test_retrieval_never_depends_on_processing_presentation_or_storage() -> None:
    _assert_no_layer_imports(
        "retrieval",
        (
            "daily_dash.processing",
            "daily_dash.presentation",
            "daily_dash.storage",
            "daily_dash.pipelines",
            "daily_dash.delivery",
        ),
    )


def test_pipelines_do_not_read_presentation_policy() -> None:
    for path in sorted((SRC / "pipelines").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert "profile.presentation" not in text, (
            f"{path}: pipeline processing must not depend on presentation configuration"
        )
