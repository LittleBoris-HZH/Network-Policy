# Network-Policy-Default-Proxy

WEPC 的历史网络分流策略库，适用于 **Mihomo / Clash Verge Rev / Stash** 的**默认代理（Default Proxy）**架构。

> **状态：保留供回退及历史兼容。** 日常使用的新版策略已迁移至 [Network-Policy-Default-Direct](https://github.com/LittleBoris-HZH/Network-Policy-Default-Direct)。两套策略的默认路由行为相反，不应混用其自动生成的服务规则。

## 核心策略

- 对未被明确放行的公网流量，客户端使用 `MATCH,WEPC` 作为最终兜底。
- **DIRECT 是显式放行结果**：由客户端本地基础设施规则、本仓库的人工例外以及已批准服务清单决定。
- 服务归属来自 [MetaCubeX/meta-rules-dat](https://github.com/MetaCubeX/meta-rules-dat) 的 geosite 列表；是否直连由本仓库 `policy/services.json` 维护。
- 对已批准服务的 `@!cn` 子集，通过 `service-veto` 重新指定 WEPC，避免整个服务域名集合被误直连。
- 广告及跟踪域名的阻断由客户端订阅的 [Loyalsoldier/clash-rules](https://github.com/Loyalsoldier/clash-rules) `reject.txt` 负责，与本仓库的服务放行策略相互独立。
- 本仓库只托管规则数据与构建代码；TUN、DNS、代理节点及最终 `MATCH` 行为由各客户端本地 YAML 决定。

## 文件结构

| 路径 | 职责 | 典型动作 |
| --- | --- | --- |
| [`policy/services.json`](policy/services.json) | 已获准直连的服务标识列表 | 构建输入 |
| [`scripts/build_rules.py`](scripts/build_rules.py) | 拉取 MetaCubeX 规则并生成服务策略 | 构建脚本 |
| [`rules/direct-allow.yaml`](rules/direct-allow.yaml) | 已批准服务的域名集合 | `DIRECT` |
| [`rules/service-veto.yaml`](rules/service-veto.yaml) | 已批准服务中的 `@!cn` 域名子集 | `WEPC` |
| [`rules/custom-reject.yaml`](rules/custom-reject.yaml) | 人工指定阻断域名 | `REJECT` |
| [`rules/custom-proxy.yaml`](rules/custom-proxy.yaml) | 人工强制代理的域名 | `WEPC` |
| [`rules/custom-direct.yaml`](rules/custom-direct.yaml) | 人工强制直连的域名 | `DIRECT` |
| [`.github/workflows/build-rules.yml`](.github/workflows/build-rules.yml) | 自动更新生成规则 | GitHub Actions |

这些 `rules/*.yaml` 均按 Mihomo / Stash 域名规则集的 `payload` 格式维护。具体的 `rule-providers` 订阅 URL、规则次序及节点名称以客户端配置为准。

## 客户端规则优先级

旧架构的推荐逻辑如下（由客户端执行，本仓库不会自动注入此顺序）：

1. 本地基础设施及受保护网段 → `DIRECT`
2. `custom-reject` → `REJECT`
3. `custom-proxy` → `WEPC`
4. `custom-direct` → `DIRECT`
5. Loyalsoldier `reject.txt` → `REJECT`
6. `service-veto` → `WEPC`
7. `direct-allow` → `DIRECT`
8. `MATCH,WEPC`

规则遵循首次匹配即停止的原则；人工修正规则排在自动构建规则之前。

## 自动更新与维护

当前保留原有 GitHub Actions 工作流：

- 修改 `policy/services.json`、构建脚本或工作流时触发重建。
- 每日 **03:17 UTC** 定时检查一次 MetaCubeX 规则。
- 可在 GitHub Actions 页面手动触发 `workflow_dispatch`。
- 构建仅在生成内容发生变化时提交 `direct-allow.yaml` 和 `service-veto.yaml`。
- 客户端的 `rule-providers` 仍需按自身设置定时拉取新文件；GitHub 构建完成不代表客户端立即应用。

历史构建任务目前仍予保留，以便旧版配置回退或仍有设备引用时继续使用。

## 与新版策略的区别

| | 本仓库：Default Proxy | [新仓库：Default Direct](https://github.com/LittleBoris-HZH/Network-Policy-Default-Direct) |
| --- | --- | --- |
| 未命中规则 | `MATCH,WEPC` | `MATCH,DIRECT` |
| 分流思路 | 逐步授权 DIRECT | 仅对选定域名使用 WEPC |
| 主要自动规则来源 | MetaCubeX 已批准服务列表 | Loyalsoldier `gfw.txt` |
| 自建定时构建 | 有 | 无 |
| 规则文件职责 | 含 `direct-allow`、`service-veto` | 仅保留三类 `custom-*` 人工例外 |

**迁移提醒：** 更换仓库订阅地址时，应同时检查客户端规则排序和最后的 `MATCH` 动作。仅把 `MATCH,WEPC` 改为 `MATCH,DIRECT`，却继续引用旧版服务放行规则，并不等同于完整迁移。

## 安全边界

仓库为公开规则仓库。请勿提交 WireGuard 私钥、VLESS UUID、REALITY 认证材料、VPS 登录凭据，或任何包含真实认证信息的完整客户端配置文件。
