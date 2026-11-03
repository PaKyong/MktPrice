"""배포가 서비스 워커의 저장 목록에 있는 파일을 모두 싣는지 본다.

목록의 파일이 하나라도 사이트에 없으면 새 서비스 워커 설치가 통째로 실패해 오프라인으로 열리지 않는다.
"""

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent


def test_deploy_copies_every_offline_file():
    sw = (ROOT / "sw.js").read_text(encoding="utf-8")
    shell = re.search(r"const SHELL = \[(.*?)\];", sw, re.S).group(1)
    prices = re.search(r'const PRICES = "([^"]+)"', sw).group(1)
    # 이마트 파일은 설치 목록에는 없지만(없는 날이 있다) 받으면 오프라인용으로 저장하므로 배포에 실려야 한다.
    emart = re.search(r'const EMART = "([^"]+)"', sw).group(1)
    paths = [p for p in re.findall(r'"([^"]+)"', shell) if p != "./"] + [prices, emart]

    workflow = (ROOT / ".github" / "workflows" / "collect.yml").read_text(encoding="utf-8")
    copy_line = next(line for line in workflow.splitlines() if "cp -r" in line and "_site/" in line)
    copied = copy_line.split()[2:-1]

    for path in paths:
        assert path.split("/")[0] in copied, path
