# 贡献流程

## 分支模型

| 分支 | 说明 |
|---|---|
| `main` | **受保护**。只接受 Pull Request 合入，禁止直接 push / 强推 / 删除。 |
| `feature/*` | 日常开发分支。直接 push，CI 会在每次 push 上运行。 |

日常改动流程：

```bash
git switch -c feature/your-change         # 从最新的 main 开分支
# ... 改代码，本地跑测试 ...
git commit -m "fix: ..."
git push -u origin feature/your-change
gh pr create --fill                       # 或网页上开 PR
# 等 CI 变绿 → Squash / Merge
```

`main` 上的分支保护要求（见文末「分支保护」）：

- 必须通过 PR 合入，**不允许**直接 push；
- 必须通过必需状态检查 `test`；
- 分支必须与 `main` 同步（strict）；
- 禁止强推与删除；
- 规则对管理员同样生效（`enforce_admins`）。

> 该规则要求 PR 评审数为 0，因此维护者可以自行合并自己的 PR —— 保护的是
> "必须走 PR + 必须过 CI"，不是"必须有第二个人批准"。需要额外评审时，在
> GitHub 上把 required approving review count 调大即可。

## CI 做什么

[`.github/workflows/ci.yml`](.github/workflows/ci.yml)，单 job `test`：

1. **安装 Qt / OpenGL 运行时库**：`libegl1 libgl1 libxkbcommon0 libdbus-1-3
   libfontconfig1 libglib2.0-0`。缺少 `libEGL.so.1` 时
   `from PySide6.QtWidgets import QApplication` 会在**导入期**失败，所有 UI 测试
   模块都会变成 import error（`QT_QPA_PLATFORM=offscreen` 并不能绕过动态库缺失）。
2. **安装 `glslang-tools`**：让 GLSL 校验用例真正执行。
   **不安装 G'MIC**：它是可选后端，应用在缺失时会降级；且其首次调用要构建约
   15s 的命令缓存，不适合作为必需的状态检查。相关用例在缺失时跳过。
3. `ruff check .`（配置见 `pyproject.toml`，当前 gate 为 `E9`）。
4. **两遍测试**：
   - `TOOLBOX_NO_NUMBA=1` 跑**全量**：这是没装 numba 时的默认路径（numba 是
     可选依赖），而且**两条路径并不等价** —— numba 的 `math.pow` 溢出时返回
     `inf`，CPython 会抛 `OverflowError`。`fractal_newton` / `fractal_nova` 的
     崩溃就是只在这条路径上出现的。
   - 装 numba 后再跑 `tests.test_fractal tests.test_filter_robustness tests.test_core`，
     覆盖加速路径。

## 本地复现 CI

```bash
# 与 CI 第一遍完全一致（纯 Python 回退路径 + 全量）
QT_QPA_PLATFORM=offscreen TOOLBOX_NO_NUMBA=1 \
  .venv/bin/python -m unittest discover -s tests -v

# 与 CI 第二遍一致（加速路径）
QT_QPA_PLATFORM=offscreen \
  .venv/bin/python -m unittest tests.test_fractal tests.test_filter_robustness tests.test_core -v

# Lint（需要 dev extra）
ruff check .

# UI smoke（应用/撤销/重置）
QT_QPA_PLATFORM=offscreen .venv/bin/python _smoke_test.py
```

### 环境变量

| 变量 | 作用 |
|---|---|
| `QT_QPA_PLATFORM=offscreen` | 无显示环境下运行 Qt（CI 与本地无头验证都需要） |
| `TOOLBOX_NO_NUMBA=1` | 强制走纯 Python 路径，即使本机装了 numba；用于复现 CI / 排查回退路径缺陷 |

### 可选外部工具与测试跳过策略

这些工具**不是**运行测试的前提，缺失时相关用例 `skip` 而非 `fail`：

| 工具 | 影响的用例 | 缺失时 |
|---|---|---|
| `gmic` | `tests/test_gmic_backend.py` 中 4 个用例 | skip（`test_four_textures` / 降级路径用例仍会运行） |
| `glslangValidator`（`glslang-tools`） | `test_builtin_glsl_validation` | skip；另有用例断言缺失时返回明确的「未安装」而非「GLSL 非法」 |

## 分支保护

当前生效的设置（public 仓库的经典 branch protection rule，分支 `main`）：

```json
{
  "required_pull_request_reviews": { "required_approving_review_count": 0,
                                     "dismiss_stale_reviews": true },
  "required_status_checks": { "strict": true, "contexts": ["test"] },
  "enforce_admins": true,
  "allow_force_pushes": false,
  "allow_deletions": false
}
```

查看 / 修改：

```bash
# 查看
gh api repos/emoeem/toolbox/branches/main/protection

# 临时放开（例如需要紧急直推 main）
gh api -X DELETE repos/emoeem/toolbox/branches/main/protection

# 恢复
gh api -X PUT repos/emoeem/toolbox/branches/main/protection \
  -H "Accept: application/vnd.github+json" \
  -F 'required_status_checks[strict]=true' \
  -F 'required_status_checks[contexts][]=test' \
  -F 'enforce_admins=true' \
  -F 'required_pull_request_reviews[required_approving_review_count]=0' \
  -F 'restrictions=' -F 'allow_force_pushes=false' -F 'allow_deletions=false'
```

> 需要的 token 权限：`repo`（classic PAT）。`enforce_admins=true` 意味着管理员
> 也必须走 PR；如果被 CI 卡住且需要紧急修复，先按上面的方式临时删除规则。
