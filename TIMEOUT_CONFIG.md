# 超时配置指南

本系统支持通过环境变量自定义所有超时设置，以适应不同的网络环境和需求。

## 默认超时配置

| 配置项 | 默认值 | 说明 | 适用场景 |
|--------|--------|------|----------|
| **PROXY_SUB_TIMEOUT** | 45秒 | 订阅获取超时 | 订阅文件通常较大，需要较长时间 |
| **PROXY_TCP_TIMEOUT** | 8秒 | TCP连接测试超时 | 代理节点响应通常较慢 |
| **PROXY_DNS_TIMEOUT** | 5秒 | DNS解析超时 | DNS解析应该很快 |
| **PROXY_HTTP_TIMEOUT** | 30秒 | HTTP请求超时 | 用于单链接测试等 |
| **PROXY_BATCH_SIZE** | 20 | 验证批次大小 | 每批同时测试的节点数 |
| **PROXY_BATCH_DELAY** | 0.5秒 | 批次间延迟 | 避免请求过快被封 |
| **PROXY_MAX_LATENCY** | 2000ms | 最大延迟阈值 | 超过此延迟会被过滤 |
| **PROXY_VALIDATION_MODE** | strict | 验证模式 | strict=严格(TCP测试), lenient=宽松(DNS测试) |

## 使用方式

### 1. 临时设置（单次运行）

```bash
# 设置订阅获取超时为60秒
PROXY_SUB_TIMEOUT=60 ./test.sh

# 设置TCP超时为10秒
PROXY_TCP_TIMEOUT=10 ./test.sh

# 同时设置多个参数
PROXY_SUB_TIMEOUT=60 PROXY_TCP_TIMEOUT=10 ./test.sh
```

### 2. 永久设置（添加到 shell 配置）

**bash/zsh:**
```bash
# 添加到 ~/.bashrc 或 ~/.zshrc
export PROXY_SUB_TIMEOUT=60
export PROXY_TCP_TIMEOUT=10
export PROXY_BATCH_SIZE=30
```

**fish:**
```fish
# 添加到 ~/.config/fish/config.fish
set -x PROXY_SUB_TIMEOUT 60
set -x PROXY_TCP_TIMEOUT 10
```

然后重新加载配置：
```bash
source ~/.bashrc  # 或 source ~/.zshrc
```

### 3. 创建 .env 文件

在项目根目录创建 `.env` 文件：

```bash
# .env 文件内容
PROXY_SUB_TIMEOUT=60
PROXY_TCP_TIMEOUT=10
PROXY_BATCH_SIZE=30
PROXY_BATCH_DELAY=1.0
```

然后运行测试脚本时会自动读取（如果安装了 python-dotenv）。

## 推荐配置

### 快速测试（网络较好）

```bash
PROXY_SUB_TIMEOUT=30 \
PROXY_TCP_TIMEOUT=5 \
PROXY_BATCH_SIZE=50 \
./test.sh
```

- 订阅获取：30秒
- TCP测试：5秒
- 批次大小：50个节点（更快完成）

### 慢速网络/严格测试

```bash
PROXY_SUB_TIMEOUT=60 \
PROXY_TCP_TIMEOUT=10 \
PROXY_BATCH_SIZE=15 \
PROXY_BATCH_DELAY=1.0 \
./test.sh
```

- 订阅获取：60秒（给更多时间下载）
- TCP测试：10秒（等待慢速节点）
- 批次大小：15个节点（减少并发避免被封）
- 批次延迟：1秒（更慢的请求频率）

### 大批量节点测试

```bash
PROXY_BATCH_SIZE=50 \
PROXY_BATCH_DELAY=0.3 \
./test.sh
```

- 批次大小：50个节点（更快完成）
- 批次延迟：0.3秒（减少等待时间）

## 调整建议

### 如果订阅获取经常超时

**症状**: 显示 "获取失败: timed out"

**解决方案**:
```bash
PROXY_SUB_TIMEOUT=60 ./test.sh  # 增加到60秒
```

### 如果很多节点显示连接超时

**症状**: 有效率极低，大量 "TCP连接超时"

**可能原因**:
1. 节点确实不可用
2. 本地网络限制
3. 超时时间太短

**解决方案**:
```bash
PROXY_TCP_TIMEOUT=10 ./test.sh  # 增加到10秒
```

### 如果测试速度太慢

**症状**: 验证几百个节点需要很长时间

**解决方案**:
```bash
PROXY_BATCH_SIZE=50 \
PROXY_BATCH_DELAY=0.3 \
PROXY_TCP_TIMEOUT=5 \
./test.sh
```

### 如果被封IP

**症状**: 突然所有节点都超时

**解决方案**:
```bash
PROXY_BATCH_SIZE=10 \
PROXY_BATCH_DELAY=2.0 \
./test.sh
```
- 减少并发数
- 增加延迟

## 验证配置

运行脚本时会显示当前配置：

```
🔒 严格模式节点验证
⏱️  超时设置: 8秒
📏 延迟阈值: 2000ms
📦 批次大小: 20个节点
⏳ 批次延迟: 0.5秒
```

## 环境变量参考

```bash
# 完整的可用环境变量列表
export PROXY_SUB_TIMEOUT=45      # 订阅获取超时（秒）
export PROXY_TCP_TIMEOUT=8       # TCP连接超时（秒）
export PROXY_DNS_TIMEOUT=5       # DNS解析超时（秒）
export PROXY_HTTP_TIMEOUT=30     # HTTP请求超时（秒）
export PROXY_BATCH_SIZE=20       # 验证批次大小（个）
export PROXY_BATCH_DELAY=0.5     # 批次间延迟（秒）
export PROXY_MAX_LATENCY=2000    # 最大延迟阈值（毫秒）
export PROXY_VALIDATION_MODE=strict  # 验证模式（strict/lenient）
```

## 注意事项

1. **TCP超时不宜过长**: 超过15秒的节点即使可用，体验也会很差
2. **批次大小**: 超过50可能会被封IP或导致测试不准确
3. **订阅超时**: 如果订阅文件很大（包含数千节点），需要增加时间
4. **网络环境**: 不同网络环境需要不同的配置，根据实际情况调整