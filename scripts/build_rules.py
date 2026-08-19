import json
import re
import subprocess
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]

POLICY = ROOT / "policy" / "services.json"

DIRECT_OUT = ROOT / "rules" / "direct-allow.yaml"
VETO_OUT = ROOT / "rules" / "service-veto.yaml"
ADS_OUT = ROOT / "rules" / "service-ads.yaml"

META_REPO = "https://github.com/MetaCubeX/meta-rules-dat.git"

RAW_BASE = (
    "https://raw.githubusercontent.com/"
    "MetaCubeX/meta-rules-dat"
)


# 获取本次构建时 MetaCubeX meta 分支的最新 commit。
# 只固定“本次构建快照”，下一次运行仍会重新获取最新版。
def latest_meta_commit():
    output = subprocess.check_output(
        [
            "git",
            "ls-remote",
            META_REPO,
            "refs/heads/meta",
        ],
        text=True,
    ).strip()

    sha = output.split()[0]

    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise RuntimeError(
            "Unable to resolve MetaCubeX meta HEAD"
        )

    return sha


# 读取你批准 DIRECT 的服务列表。
def read_services():
    data = json.loads(
        POLICY.read_text(encoding="utf-8")
    )

    if data.get("schema_version") != 1:
        raise RuntimeError(
            "Unsupported services.json schema"
        )

    services = data.get("services")

    if not isinstance(services, list):
        raise RuntimeError(
            "'services' must be a list"
        )

    result = []

    for service in services:
        if not isinstance(service, str):
            raise RuntimeError(
                f"Invalid service: {service}"
            )

        if not re.fullmatch(
            r"[a-z0-9][a-z0-9._-]*",
            service,
        ):
            raise RuntimeError(
                f"Invalid service name: {service}"
            )

        result.append(service)

    return sorted(set(result))


# 从 MetaCubeX 当前 commit 下载指定 service Rule Set。
# @!cn / @ads 不存在时视为空集合。
def fetch_list(commit, name, optional=False):
    encoded = quote(
        name,
        safe="@!._-",
    )

    url = (
        f"{RAW_BASE}/{commit}/"
        f"geo/geosite/{encoded}.list"
    )

    request = Request(
        url,
        headers={
            "User-Agent": "WEPC-rule-builder"
        },
    )

    try:
        with urlopen(
            request,
            timeout=30,
        ) as response:

            text = (
                response
                .read()
                .decode("utf-8")
            )

    except HTTPError as error:
        if optional and error.code == 404:
            return set()

        raise

    rules = set()

    for raw in text.splitlines():
        line = raw.strip()

        if not line:
            continue

        if line.startswith("#"):
            continue

        rules.add(line)

    return rules


# 输出 Mihomo / Stash 都能读取的 YAML Rule Set。
def write_yaml(path, rules, commit):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    lines = [
        "# Generated automatically by WEPC",
        f"# MetaCubeX commit: {commit}",
        "",
    ]

    if not rules:
        lines.append("payload: []")

    else:
        lines.append("payload:")

        for rule in sorted(rules):
            lines.append(
                "  - "
                + json.dumps(
                    rule,
                    ensure_ascii=False,
                )
            )

    lines.append("")

    path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main():
    commit = latest_meta_commit()
    services = read_services()

    direct = set()
    veto = set()
    ads = set()

    for service in services:

        # 整个批准服务
        full = fetch_list(
            commit,
            service,
        )

        # 服务中的非大陆子集
        non_cn = fetch_list(
            commit,
            f"{service}@!cn",
            optional=True,
        )

        # 服务自己的广告子集
        service_ads = fetch_list(
            commit,
            f"{service}@ads",
            optional=True,
        )

        # 不做 subtraction。
        # 最终由 Clash / Stash 的规则优先级决定：
        #
        # veto → WEPC
        # ads  → REJECT
        # full → DIRECT
        direct.update(full)
        veto.update(non_cn)
        ads.update(service_ads)

        print(
            f"{service}: "
            f"direct={len(full)}, "
            f"veto={len(non_cn)}, "
            f"ads={len(service_ads)}"
        )

    write_yaml(
        DIRECT_OUT,
        direct,
        commit,
    )

    write_yaml(
        VETO_OUT,
        veto,
        commit,
    )

    write_yaml(
        ADS_OUT,
        ads,
        commit,
    )

    print()
    print(f"MetaCubeX commit: {commit}")
    print(f"direct-allow: {len(direct)}")
    print(f"service-veto: {len(veto)}")
    print(f"service-ads: {len(ads)}")


if __name__ == "__main__":
    main()
