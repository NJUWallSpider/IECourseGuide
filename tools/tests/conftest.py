import shutil
import sys
import tempfile
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

REPO_ROOT = TOOLS_DIR.parent


def pytest_unconfigure(config):  # noqa: ARG001
    """清理测试在仓库里留下的临时产物。

    本机环境的 TEMP 目录不可写，``tempfile`` 会回退到当前目录，pytest 的
    ``tmp_path`` 因此会落在仓库根目录（``pytest-of-*/``）；CI/Linux 下不受影响。
    顺手清掉 ``.pytest_cache`` 与 ``__pycache__``，避免被 ``git add -A`` 误收。
    """

    try:
        if Path(tempfile.gettempdir()).resolve() == REPO_ROOT.resolve():
            for path in REPO_ROOT.glob("pytest-of-*"):
                shutil.rmtree(path, ignore_errors=True)
    except OSError:
        pass
    shutil.rmtree(REPO_ROOT / ".pytest_cache", ignore_errors=True)
    for directory in (TOOLS_DIR, TOOLS_DIR / "tests"):
        shutil.rmtree(directory / "__pycache__", ignore_errors=True)
