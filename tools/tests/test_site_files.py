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


def test_failed_emart_commit_cannot_block_kamis_deploy():
    """이마트 커밋 단계가 실패해도(받아 오기·푸시 거절 등) 작업이 실패로 끝나 배포가 빠지면 안 된다.

    그 단계도 continue-on-error로 두고, 실패했으면 맨 끝 emart-check가 실행을 실패로 끝낸다(메일).
    """
    workflow = (ROOT / ".github" / "workflows" / "collect.yml").read_text(encoding="utf-8")
    step = re.search(r"^      - name: 이마트 파일 바뀌었으면 커밋·푸시\n((?:        .*\n|\s*#.*\n)*)", workflow, re.M).group(1)
    assert "continue-on-error: true" in step
    step_id = re.search(r"id: (\S+)", step).group(1)
    output = re.search(rf"^      (\S+): \$\{{\{{ steps\.{step_id}\.outcome \}}\}}", workflow, re.M).group(1)
    check = re.search(r"^  emart-check:\n((?:    .*\n)*)", workflow, re.M).group(1)
    assert f"needs.collect.outputs.{output} == 'failure'" in check


def test_failed_deploy_is_tried_once_more():
    """배포 단계가 실패하면 같은 실행 안에서 한 번 더 배포한다.

    2026-11-10 새벽 실행은 방금 올린 사이트 묶음을 GitHub이 찾지 못해 배포가 실패했고, 다시 시도하지
    않아 사이트가 다음 실행까지 옛 값에 멈춰 있었다. 첫 시도가 작업을 실패로 끝내면 다시 시도할 수
    없으므로 continue-on-error로 두고, 두 번째 시도는 첫 시도가 실패했을 때만 돈다. 두 번째도
    실패하면 작업이 실패로 끝나야 메일이 온다.
    """
    workflow = (ROOT / ".github" / "workflows" / "collect.yml").read_text(encoding="utf-8")
    job = re.search(r"^  deploy:\n((?:    .*\n|\n)*)", workflow, re.M).group(1)
    tries = [step for step in re.split(r"^      - ", job, flags=re.M) if "uses: actions/deploy-pages@" in step]
    assert len(tries) == 2
    first, second = tries
    assert "continue-on-error: true" in first
    first_id = re.search(r"id: (\S+)", first).group(1)
    assert f"if: steps.{first_id}.outcome == 'failure'" in second
    assert "continue-on-error" not in second
    # 두 시도가 같은 사이트 묶음을 배포한다.
    names = [re.search(r"artifact_name: (.+)", step).group(1) for step in tries]
    assert names[0] == names[1]


def test_every_job_starts_from_the_newest_commit():
    """수집과 배포 모두 main의 가장 새 커밋을 받아 온다.

    받아 오기는 그냥 두면 실행을 만든 때의 커밋을 받는다. 앞 실행이 끝나기를 기다린 수집 실행이 그 실행의
    커밋을 못 본 채 같은 날 값을 또 받고, 한 줄짜리 가격 파일에서 커밋 충돌이 나 실패한다.
    """
    workflow = (ROOT / ".github" / "workflows" / "collect.yml").read_text(encoding="utf-8")
    checkouts = [step for step in re.split(r"^      - ", workflow, flags=re.M) if step.startswith("uses: actions/checkout@")]
    assert len(checkouts) == 2
    assert all("ref: main" in step for step in checkouts)


def test_keys_are_given_only_to_steps_that_run_our_code():
    """키는 작업 전체가 아니라 우리 코드를 돌리는 단계에만 넘긴다(남이 만든 도구 단계에는 보이지 않게)."""
    workflow = (ROOT / ".github" / "workflows" / "collect.yml").read_text(encoding="utf-8")
    steps = re.split(r"^      - ", workflow, flags=re.M)
    assert "secrets." not in steps[0]
    assert sum("secrets." in step for step in steps) >= 1
    assert all("uses:" not in step for step in steps[1:] if "secrets." in step)
