# SWU 查寝打卡脚本

西南大学钉钉查寝自动打卡独立脚本. 适用于需要在本地或云函数中运行自动打卡的场景.

## 功能特性

- 自动获取当日打卡任务
- 支持统一身份认证登录
- OCR 自动识别验证码
- 自动填写宿舍信息和位置
- 支持请假状态检测
- 防重复打卡
- 详细状态码返回
- GitHub Actions 定时任务与 Cloudflare Workers 定时调度支持
- 瞬时失败自动重试 (多次失败才算失败)
- 失败邮件通知

## 环境要求

- Python 3.13+
- 依赖库: requests, beautifulsoup4, Pillow, ddddocr

## 快速开始

### 方式一: GitHub Actions 自动签到

**重要提示: GitHub Actions 存在排队延迟问题**
- 定时任务可能延迟数分钟、数十分钟, 甚至数小时才执行
- 免费账户优先级低, 高峰期延迟更严重
- 无法保证准时签到, 可能因延迟错过签到时间窗口
- 如对签到时间有严格要求, 建议使用云服务器、本地部署或配合外部定时触发器 (如 Cloudflare Workers)

基本配置:
1. Fork 本仓库到你的账号
2. 在仓库 **Settings** -> **Secrets and variables** -> **Actions** 中配置账号密码
3. 设置每天北京时间 21:15、21:45 自动签到 (实际执行时间不可控)

**详细配置教程**: [GITHUB_ACTIONS.md](GITHUB_ACTIONS.md)

### 方式二: 本地运行

#### 1. 安装依赖

```bash
# 使用 pip
pip install -e .

# 或使用 uv (推荐)
uv sync
```

#### 2. 运行脚本

安装后可直接使用命令行工具:

```bash
# 设置环境变量后运行
export SWU_USERNAME="你的学号"
export SWU_PASSWORD="你的密码"
swu-checkin
```

若未预先设置环境变量, 直接运行 `swu-checkin` 会以安全交互方式提示输入账号和密码:

```bash
swu-checkin
# 提示: 校园网账号: 
# 提示: 校园网密码: 
```

作为 Python 模块调用:

```python
from swu_checkin import check_in

# 方式 A: 从环境变量 (SWU_USERNAME / SWU_PASSWORD) 读取账号密码
result = check_in()

# 方式 B: 直接传入账号和密码
result = check_in("你的学号", "你的密码")
```

##### Windows PowerShell

```powershell
$env:SWU_USERNAME="你的学号"
$env:SWU_PASSWORD="你的密码"
swu-checkin
```

##### Linux / macOS

```bash
export SWU_USERNAME="你的学号"
export SWU_PASSWORD="你的密码"
swu-checkin
```

## 返回状态码

| 状态码 | 含义 |
|---|---|
| 0 | 今日暂无签到任务 |
| 1 | 签到成功 |
| 2 | 今日已签到, 无需重复操作 |
| 3 | 账号或密码验证失败 |
| 4 | 连接错误或请求超时 |
| 5 | 请假中, 跳过打卡 |

## 项目结构

```
.
├── .github/
│   └── workflows/
│       └── checkin.yml       # GitHub Actions 工作流
├── src/
│   └── swu_checkin/
│       ├── __init__.py       # 模块导出定义
│       ├── cache.py          # 运行时上下文与会话管理
│       ├── check_in.py       # 主打卡脚本与 CLI 入口
│       ├── des.py            # DES 加密工具
│       ├── get_info.py       # 信息获取与统一认证登录
│       └── identity.py       # 身份选择处理
├── tests/
│   └── test_security.py      # 安全性与脱敏测试
├── CONTRIBUTING.md           # 贡献指南
├── GITHUB_ACTIONS.md         # Actions 配置指南
├── pyproject.toml            # 项目配置和依赖
└── README.md
```

## 工作流程

1. 使用校园网账号密码登录统一身份认证
2. 通过 OCR 识别验证码自动登录
3. 获取 token 和打卡任务信息
4. 检测请假状态
5. 自动填写宿舍位置信息并提交打卡

## 环境变量配置

### 必需配置 (二选一或作为默认凭据)
- `SWU_USERNAME`: 校园网账号 (学号, 兼容旧变量名 `SWUDK_USERNAME`)
- `SWU_PASSWORD`: 校园网密码 (兼容旧变量名 `SWUDK_PASSWORD`)

### 可选配置
- `SWU_MAX_ATTEMPTS`: 签到失败重试次数 (默认 3 次, 兼容 `SWUDK_MAX_ATTEMPTS`)
- `SWU_RETRY_DELAY`: 首次重试等待秒数, 后续指数退避 (默认 8 秒, 兼容 `SWUDK_RETRY_DELAY`)
- `SWU_DEBUG_CREDENTIALS`: 调试模式, 输出敏感信息 (`1` 启用, 默认关闭, 兼容 `SWUDK_DEBUG_CREDENTIALS`)

## 注意事项

### 安全性
- 脚本仅从环境变量或交互式输入读取账号密码, 切勿硬编码或提交到仓库
- GitHub Actions 使用 Secrets 存储敏感信息, 不会泄露到日志
- 正常模式下不会输出 token、ticket 等敏感信息
- 调试模式 (`SWU_DEBUG_CREDENTIALS=1`) 会输出敏感信息, 仅用于本地开发, 切勿在 GitHub Actions 中启用

### 功能特性
- 验证码识别失败自动重试 (每次登录尝试最多识别 3 次验证码)
- 登录失败自动重试 (验证码错误时自动重新登录, 最多 3 次)
- 网络异常、今日任务暂未生成时自动重试 3 次, 打满才算失败
- 一次签到流程中复用 session、token、学号、宿舍信息等, 避免重复请求
- 建议在正式使用前先手动测试一次

## 相关项目

- **[swu-login](https://github.com/Sorynthia/swu-login)** - 西南大学统一身份认证独立登录模块
- **[swudk-dingtalk](https://github.com/Sorynthia/swudk-dingtalk)** - 钉钉扫码打卡前端工具

## 贡献指南

欢迎提交 Issue 和 Pull Request! 请查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解详细信息.

## 引用与归属

如果你在项目中使用或参考了本代码, 建议按以下方式标注:

```
基于 Sorynthia/swu-checkin 开发
GitHub: https://github.com/Sorynthia/swu-checkin
```

本项目采用 MIT 许可证, 欢迎使用和修改, 但请保留原作者信息.

## 许可证

MIT License
