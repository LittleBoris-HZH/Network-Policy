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

META_REPO = "https://github.com/MetaCubeX/meta-rules-dat.git"

RAW_BASE = (
    "https://raw.githubusercontent.com/"
    "MetaCubeX/meta-rules-dat"
)


# 获取本次构建时 meta 分支最新 commit。
def latest_meta_commit():
    result = subprocess.run(
        [
            "git",
            "ls-remote",
            "--exit-code",
            META_REPO,
            "refs/heads/meta",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )

    parts = result.stdout.split()

    if not parts:
        raise RuntimeError(
            "Unable to resolve MetaCubeX meta HEAD"
        )

    sha = parts[0]

    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise RuntimeError(
            f"Invalid MetaCubeX commit: {sha}"
        )

    return sha


# 读取允许 DIRECT 的服务。
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


# 下载 MetaCubeX service list。
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

        # @!cn 不一定存在。
        if optional and error.code == 404:
            return set()

        raise

    rules = set()

    for line_no, raw in enumerate(
        text.splitlines(),
        1,
    ):

        line = raw.strip()

        if not line or line.startswith("#"):
            continue

        # 确保输出仍然是 domain Rule Set，
        # 不把其他规则类型误塞进去。
        if (
            any(ch.isspace() for ch in line)
            or "," in line
            or ":" in line
            or "/" in line
            or "#" in line
        ):
            raise RuntimeError(
                f"{name}.list:{line_no}: "
                f"unexpected domain syntax: {line}"
            )

        rules.add(line)

    return rules


# 输出 Mihomo / Stash YAML Rule Set。
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

    for service in services:

        # 整个服务 → DIRECT
        full = fetch_list(
            commit,
            service,
        )

        # 服务中的 @!cn → WEPC
        non_cn = fetch_list(
            commit,
            f"{service}@!cn",
            optional=True,
        )

        direct.update(full)
        veto.update(non_cn)

        print(
            f"{service}: "
            f"direct={len(full)}, "
            f"veto={len(non_cn)}"
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

    print()
    print(f"MetaCubeX commit: {commit}")
    print(f"direct-allow: {len(direct)}")
    print(f"service-veto: {len(veto)}")


if __name__ == "__main__":
    main()
