"""The layering is enforced, not just documented.

Every source file's imports are read and checked against the table below: a module may import only
the first-party modules listed for it. Third-party rules: ``requests`` belongs to the generic
client only, ``duckdb`` to the local store only.
"""

import ast
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
P = "collibra_toolkit"

# module (or package) -> first-party prefixes it may import. The longest matching key wins.
ALLOWED = {
    P: [f"{P}._lazy", f"{P}.client"],
    f"{P}._lazy": [],
    f"{P}.client": [f"{P}.client"],
    f"{P}.client.retry": [],
    f"{P}.client.errors": [f"{P}.client.retry"],
    f"{P}.client.auth": [f"{P}.client.errors"],
    f"{P}.client.pagination": [],
    f"{P}.client.core": [f"{P}.client.{m}" for m in ("auth", "errors", "pagination", "retry")],
    f"{P}.client.health": [f"{P}.client.core"],
    f"{P}.cli": [f"{P}.client", f"{P}.cli"],                      # never an initiative
    f"{P}.insights": [f"{P}._lazy", f"{P}.insights"],
    f"{P}.insights.tables": [],
    f"{P}.insights.api": [f"{P}.client", f"{P}.insights.tables", f"{P}.insights.api"],
    f"{P}.insights.store": [f"{P}.insights.tables", f"{P}.insights.store"],
    f"{P}.insights.model": [f"{P}.insights.store", f"{P}.insights.model"],
    f"{P}.insights.lakehouse": [f"{P}.insights.store", f"{P}.insights.model", f"{P}.insights.tables", f"{P}.insights.lakehouse"],
    f"{P}.insights.diagnostics": [f"{P}._lazy", f"{P}.insights.diagnostics"],
    f"{P}.insights.diagnostics.offline": [f"{P}.insights.store"],
    f"{P}.insights.diagnostics.live": [f"{P}.client", f"{P}.insights.store", f"{P}.insights.diagnostics.offline"],
    f"{P}.insights.cli": [P + "."],                                # the composition root may use anything
}
THIRD_PARTY_OWNER = {"requests": f"{P}.client", "duckdb": f"{P}.insights.store"}


def _module_name(path: Path) -> str:
    parts = list(path.relative_to(SRC).with_suffix("").parts)
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _imports(path: Path, module: str) -> set[str]:
    package = module if path.name == "__init__.py" else module.rsplit(".", 1)[0]
    found = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            found |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = ".".join(package.split(".")[: len(package.split(".")) - (node.level - 1)])
                if node.module:
                    found.add(f"{base}.{node.module}")
                else:
                    found |= {f"{base}.{a.name}" for a in node.names}
            elif node.module:
                found.add(node.module)
    return found


def _rule(module: str) -> list[str]:
    key = max((k for k in ALLOWED if module == k or module.startswith(k + ".")), key=len)
    return ALLOWED[key]


def test_every_module_imports_only_what_its_layer_allows():
    problems = []
    files = sorted(SRC.rglob("*.py"))
    assert len(files) > 20
    for path in files:
        module = _module_name(path)
        allowed = _rule(module)
        for target in sorted(_imports(path, module)):
            root = target.split(".")[0]
            if root == P:
                if not any(target == a or target.startswith(a if a.endswith(".") else a + ".") or target == a.rstrip(".") for a in allowed):
                    problems.append(f"{module} must not import {target}")
            elif root in THIRD_PARTY_OWNER and not module.startswith(THIRD_PARTY_OWNER[root]):
                problems.append(f"{module} must not import {root} (reserved for {THIRD_PARTY_OWNER[root]})")
    assert not problems, "\n".join(problems)


def _runs(code: str) -> str:
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def test_downloading_works_without_duckdb():
    assert _runs(
        "import sys; sys.modules['duckdb'] = None\n"
        "from collibra_toolkit.insights import InsightsClient\n"
        "from collibra_toolkit import CollibraClient\n"
        "print('ok')"
    ) == "ok"


def test_local_analysis_works_without_requests():
    assert _runs(
        "import sys; sys.modules['requests'] = None\n"
        "from collibra_toolkit.insights.store import Snapshot\n"
        "from collibra_toolkit.insights.model import build_model, check_model\n"
        "from collibra_toolkit.insights.diagnostics import snapshot_report\n"
        "print('ok')"
    ) == "ok"


def test_the_generic_client_does_not_need_any_initiative():
    assert _runs(
        "import sys\n"
        "from collibra_toolkit import CollibraClient\n"
        "assert not any(m.startswith('collibra_toolkit.insights') for m in sys.modules)\n"
        "print('ok')"
    ) == "ok"
