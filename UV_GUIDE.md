# UV 使用指南

## 什么是 UV？

[uv](https://github.com/astral-sh/uv) 是一个用 Rust 编写的极速 Python 包管理器，比 pip 快 10-100 倍。

## 安装 UV

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或使用 pip
pip install uv

# 或使用 Homebrew (macOS)
brew install uv
```

安装后重启终端或运行 `source ~/.bashrc` / `source ~/.zshrc`

## 快速开始

### 方式一：一键测试（推荐）

```bash
# 运行完整测试（自动创建环境、安装依赖、执行测试）
./test_uv.sh
```

### 方式二：分步操作

```bash
# 1. 创建虚拟环境
uv venv

# 2. 安装依赖
uv pip install requests pyyaml aiohttp asyncio python-socks async_timeout

# 3. 运行测试
source .venv/bin/activate
./test.sh

# 或直接使用 uv run（无需手动激活）
uv run test.sh
```

## 常用命令

### 虚拟环境管理

```bash
# 创建虚拟环境
uv venv

# 创建特定Python版本的虚拟环境
uv venv --python 3.11

# 查看虚拟环境信息
ls -la .venv/
```

### 包管理

```bash
# 安装包
uv pip install requests

# 安装多个包
uv pip install requests pyyaml aiohttp

# 从 requirements.txt 安装
uv pip install -r requirements.txt

# 查看已安装包
uv pip list

# 查看包树
uv pip tree
```

### 运行脚本

```bash
# 方式1：激活环境后运行
source .venv/bin/activate
python scripts/subscription_manager.py init

# 方式2：使用 uv run（推荐）
uv run python scripts/subscription_manager.py init

# 方式3：直接运行 Python 文件
uv run scripts/subscription_manager.py init
```

## 单链接测试

```bash
# 使用 uv run 测试单个订阅
uv run python test_single.py "https://example.com/sub"

# 详细模式
uv run python test_single.py "https://example.com/sub" -v
```

## 分步测试

```bash
# 初始化
uv run python scripts/subscription_manager.py init

# 选择订阅
uv run python scripts/subscription_manager.py select

# 获取订阅
uv run python scripts/subscription_manager.py fetch

# 验证节点
uv run python scripts/validator.py validate

# 更新评分
uv run python scripts/subscription_manager.py update-scores

# 生成报告
uv run python scripts/subscription_manager.py report

# 生成配置
uv run python scripts/clash_generator.py generate
```

## 检查状态

```bash
# 查看当前状态
uv run python check_status.py
```

## 高级用法

### 使用特定 Python 版本

```bash
# 如果安装了多个 Python 版本
uv venv --python python3.11
uv venv --python python3.10

# 查看可用版本
uv python list
```

### 锁定依赖版本

```bash
# 生成锁定文件（类似于 requirements.lock）
uv pip freeze > requirements.lock

# 从锁定文件安装
uv pip install -r requirements.lock
```

### 清理环境

```bash
# 删除虚拟环境
rm -rf .venv

# 删除输出文件
rm -rf output/*

# 重新创建
uv venv
uv pip install requests pyyaml aiohttp asyncio python-socks async_timeout
```

## 性能对比

```bash
# 使用 pip（慢）
time pip install requests pyyaml aiohttp asyncio python-socks async_timeout
# 约 10-30 秒

# 使用 uv（快）
time uv pip install requests pyyaml aiohttp asyncio python-socks async_timeout
# 约 1-3 秒
```

## 故障排除

### UV 命令未找到

```bash
# 检查安装
echo $PATH
which uv

# 如果未找到，添加到你的 shell 配置
# ~/.bashrc 或 ~/.zshrc
export PATH="$HOME/.cargo/bin:$PATH"
```

### 虚拟环境创建失败

```bash
# 检查 Python 版本
python3 --version  # 需要 3.8+

# 指定 Python 路径
uv venv --python $(which python3)
```

### 包安装失败

```bash
# 清除缓存
uv cache clean

# 重试安装
uv pip install --reinstall requests
```

## 与 pip 的对比

| 功能 | pip | uv |
|------|-----|-----|
| 安装速度 | 慢 | **快 10-100 倍** |
| 虚拟环境 | 需手动创建 | 内置 `uv venv` |
| 运行脚本 | 需激活环境 | `uv run` 一键运行 |
| 依赖解析 | 慢 | **极快** |
| 兼容性 | 标准 | 与 pip 完全兼容 |

## 最佳实践

1. **首次使用**: 运行 `./test_uv.sh` 一键完成所有设置
2. **日常使用**: 使用 `uv run` 直接运行脚本，无需手动激活环境
3. **团队协作**: 提交 `requirements.lock` 文件确保环境一致
4. **CI/CD**: uv 在 GitHub Actions 中同样可用，可加速构建

## 完整工作流示例

```bash
# 1. 安装 uv
# curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 进入项目目录
cd proxy-config-manager

# 3. 配置订阅
vim subscriptions.txt

# 4. 运行测试（首次会自动创建环境）
./test_uv.sh

# 5. 查看结果
cat output/test_report.md
uv run python check_status.py

# 6. 后续测试（使用已创建的环境）
uv run test.sh
```