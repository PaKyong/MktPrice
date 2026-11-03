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


def test_slow_emart_step_cannot_block_kamis_deploy():
    """참가격 단계는 자기 시간 제한이 있고, 그 제한이 작업 전체 제한보다 짧아야 한다.

    작업 전체가 시간 제한에 걸리면 continue-on-error로도 받지 못해 배포(그날 KAMIS 가격)까지 빠진다.
    """
    workflow = (ROOT / ".github" / "workflows" / "collect.yml").read_text(encoding="utf-8")
    job_limit = int(re.search(r"^  collect:\n(?:    .*\n)*?    timeout-minutes: (\d+)", workflow, re.M).group(1))
    step = re.search(r"^      - name: 이마트 값\(참가격\) 받기\n((?:        .*\n|\s*#.*\n)*)", workflow, re.M).group(1)
    assert "continue-on-error: true" in step
    step_limit = int(re.search(r"timeout-minutes: (\d+)", step).group(1))
    # KAMIS 몫(보통 몇 분)을 넉넉히 남긴다.
    assert job_limit - step_limit >= 20
