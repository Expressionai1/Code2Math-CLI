## Python / Backend
- Python虚拟环境地址：.venv
- 使用 uv pip 来进行包的安装
- Python 3.12；遵循 PEP 8，使用 Ruff 进行格式化与检查（行长 88）。

## Git 提交要求

- **Git 提交格式**：必须使用 `type: message` 格式，其中 type 必须是以下之一：feat/fix/chore/docs/test/refactor/build/ci/revert。message 可用中文，总长度控制在 180 个字符内。示例：`feat: 添加滑动操作重试机制`、`fix: 修复中文输入截断问题`。
- 注意：只需生成 git message，不需要帮用户做 git 管理，用户会根据提示自行操作。
