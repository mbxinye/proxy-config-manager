# 本地测试指南

## 🚀 快速开始（使用 UV - 推荐）

[uv](https://github.com/astral-sh/uv) 是一个极速 Python 包管理器，比 pip 快 10-100 倍。

### 1. 安装 uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. 一键测试

```bash
# 自动创建虚拟环境、安装依赖、运行测试
./test_uv.sh
```

### 3. 查看结果

```bash
# 检查状态
uv run python check_status.py
```

详细 uv 用法见 **[UV_GUIDE.md](./UV_GUIDE.md)**

---

## 传统方式（使用 pip）

如果你不想使用 uv，也可以使用传统 pip 方式。

### 1. 安装依赖

```bash
# 安装Python依赖
pip3 install -r requirements.txt

# 或使用 pip
pip install -r requirements.txt
```

### 2. 配置订阅链接

编辑 `subscriptions.txt` 文件，添加你的订阅链接：

```text
# 示例
https://example.com/subscription1
https://example.com/subscription2
```

## 测试方式

### 验证模式说明

本系统提供两种节点验证模式：

**宽松模式（默认，推荐）**
- 仅测试DNS解析是否成功
- 适用于大多数免费代理节点
- 有效率通常较高（30-70%）
- 命令：`./test.sh` 或 `./test_uv.sh`

**严格模式**
- 进行实际的TCP连接测试
- 能更准确地筛选可用节点
- 有效率通常较低（5-30%），因为很多节点防火墙会屏蔽探测
- 命令：`./test.sh --strict`

**💡 建议**: 先使用宽松模式测试，如果有效率过低（<10%），再检查订阅链接或尝试严格模式。

### 方式一：完整流程测试（pip 方式）

运行完整的测试脚本，模拟GitHub Actions的工作流程：

```bash
./test.sh
```

### 方式二：完整流程测试（uv 方式）

使用 uv 自动管理虚拟环境：

```bash
./test_uv.sh
```

### 方式三：单链接测试

快速测试单个订阅链接：

**使用 pip：**
```bash
python3 test_single.py "https://example.com/subscription"
python3 test_single.py "https://example.com/subscription" -v  # 详细模式
```

**使用 uv：**
```bash
uv run python test_single.py "https://example.com/subscription"
uv run python test_single.py "https://example.com/subscription" -v
```

### 方式四：分步测试

如果你只想测试某个特定步骤：

**使用 pip：**
```bash
# 1. 初始化订阅数据库
python3 scripts/subscription_manager.py init

# 2. 查看会处理哪些订阅
python3 scripts/subscription_manager.py select

# 3. 获取订阅内容
python3 scripts/subscription_manager.py fetch

# 4. 验证节点
python3 scripts/validator.py validate

# 5. 更新评分
python3 scripts/subscription_manager.py update-scores

# 6. 查看报告
python3 scripts/subscription_manager.py report

# 7. 生成Clash配置
python3 scripts/clash_generator.py generate
```

**使用 uv：**
```bash
# 所有命令都可以用 uv run 前缀
uv run python scripts/subscription_manager.py init
uv run python scripts/subscription_manager.py select
# ... 其他命令同理
```

## 查看结果

### 验证统计

```bash
cat output/validation_stats.json | python3 -m json.tool

# 或使用 uv
uv run python -c "import json; print(json.dumps(json.load(open('output/validation_stats.json')), indent=2))"
```

输出示例：
```json
{
  "timestamp": 1700000000,
  "total_nodes": 150,
  "valid_nodes": 85,
  "success_rate": 0.567,
  "subscription_stats": {
    "https://example1.com": {
      "total": 30,
      "valid": 20,
      "avg_latency": 180.5
    }
  }
}
```

### 订阅评分

```bash
cat data/subscriptions.json | python3 -m json.tool

# 查看特定订阅的评分
python3 -c "
import json
with open('data/subscriptions.json') as f:
    data = json.load(f)
    for sub in data['subscriptions']:
        print(f\"{sub['name']}: {sub['score']}分 ({sub['frequency']}) - {sub['success_rate']*100:.1f}% 成功率\")
"
```

### 查看有效节点

```bash
# 查看节点数量
python3 -c "
import json
with open('output/valid_nodes.json') as f:
    nodes = json.load(f)
    print(f'共 {len(nodes)} 个有效节点')
    for node in nodes[:5]:
        print(f\"  - {node['name']} ({node['type']}): {node.get('latency', 'N/A')}ms\")
"
```

## 常见问题

### 1. 权限错误

如果遇到权限错误：
```bash
chmod +x test.sh test_uv.sh test_single.py setup_uv.sh check_status.py
```

### 2. Python模块未找到

**使用 pip：**
```bash
# 检查Python版本
python3 --version  # 需要3.8+

# 安装依赖
python3 -m pip install -r requirements.txt
```

**使用 uv：**
```bash
# 创建环境并安装
uv venv
uv pip install -r requirements.txt
```

### 3. SSL证书错误

在测试脚本中已禁用SSL验证，如果仍有问题：
```bash
# 更新证书
pip install --upgrade certifi
# 或
uv pip install --upgrade certifi
```

### 4. 节点验证太慢

可以在 `scripts/validator.py` 中修改超时时间：
```python
self.timeout = 5  # 从10秒改为5秒
```

### 5. 网络限制

如果在受限网络环境，可能需要代理：

```bash
# 设置代理环境变量
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890

# 然后运行测试
./test.sh
# 或
./test_uv.sh
```

## 调试模式

### 启用详细日志

在Python脚本中添加调试输出：
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 查看中间文件

测试过程中会生成以下中间文件：
- `subscriptions/sub_001.txt` - 原始订阅内容
- `output/fetched_data.json` - 获取的订阅数据
- `output/selected_subscriptions.json` - 选中的订阅
- `output/urls_to_fetch.txt` - 要获取的URL列表

### 手动检查节点

```bash
# 查看解析的节点
python3 -c "
import json
with open('output/fetched_data.json') as f:
    data = json.load(f)
    for sub in data[:1]:  # 查看第一个订阅
        print(f'订阅: {sub[\"url\"][:50]}...')
        print(f'内容长度: {len(sub.get(\"content\", \"\"))}')
        print(f'内容前200字符:')
        print(sub.get('content', '')[:200])
"
```

## 生成Clash配置

本地测试通过后，可以生成Clash配置文件：

**使用 pip：**
```bash
python3 scripts/clash_generator.py generate
```

**使用 uv：**
```bash
uv run python scripts/clash_generator.py generate
```

查看生成的配置：
```bash
ls -lh output/clash_*.yml

# 验证YAML格式
python3 -c "import yaml; yaml.safe_load(open('output/clash_config.yml'))" && echo "✅ YAML格式正确"
```

## 与GitHub Actions的差异

本地测试与GitHub Actions的主要区别：

| 功能 | 本地 | GitHub Actions |
|------|------|----------------|
| 评分持久化 | ✓ | ✓ |
| 定时运行 | ✗ | ✓ |
| 自动提交 | ✗ | ✓ |
| GitHub Pages | ✗ | ✓ |
| 并行处理 | ✗（较少） | ✓（更多） |

## 性能优化

### 加快测试速度

1. **减少节点验证数量**
   - 编辑 `scripts/validator.py`
   - 修改 `batch_size = 50` 为更小的值

2. **跳过验证**
   - 开发时可临时跳过验证步骤
   - 直接生成配置进行格式检查

3. **只测试特定订阅**
   - 临时编辑 `subscriptions.txt` 只保留一个链接
   - 测试完成后再恢复

## 下一步

本地测试通过后：

1. **提交到GitHub**
   ```bash
   git add .
   git commit -m "Add proxy subscriptions"
   git push
   ```

2. **启用Actions和Pages**（参考README）

3. **触发运行**
   - 手动触发或等待自动运行

4. **使用配置**
   - 订阅链接：`https://yourname.github.io/repo/clash.yml`