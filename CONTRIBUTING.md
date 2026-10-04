# 贡献指南

感谢你考虑为本项目做出贡献!

## 如何贡献

### 报告问题

- 使用 GitHub Issues 报告 bug 或提出功能请求
- 提供清晰的标题和详细的描述
- 包含复现步骤、环境信息和预期行为

### 提交代码

1. Fork 本仓库
2. 创建你的功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交你的修改 (`git commit -m 'feat: add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

### 代码规范

- Python 代码遵循 PEP 8
- 提交信息遵循 Conventional Commits 规范 (例如: feat: ..., fix: ..., docs: ...)
- 添加必要的注释和文档

### Pull Request 要求

- 确保代码通过现有测试和 Ruff 静态检查
- 对于新功能, 添加相应的测试用例
- 更新相关文档
- 保持提交历史清晰

## 开发环境

推荐使用 uv 管理依赖:

```bash
uv sync
```

或使用 pip:

```bash
pip install -e .
```

### 运行检查与测试

```bash
# 代码静态检查
ruff check src tests

# 安全性与脱敏测试
python tests/test_security.py
```

## 行为准则

- 尊重所有贡献者
- 保持友好和专业的交流
- 接受建设性的批评
- 关注项目目标和用户需求

## 许可证

提交代码即表示你同意你的贡献使用项目的 MIT 许可证.
