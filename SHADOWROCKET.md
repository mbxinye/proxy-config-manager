# Shadowrocket 使用指南

本配置生成器专门针对 Shadowrocket 优化，采用**最严格的 TCP 连接测试**，确保每个节点都真实可用。

## 🎯 严格模式特点

- **TCP连接测试**: 不是简单的DNS解析，而是真实的端口连通性测试
- **高可用性**: 只有能建立TCP连接的节点才会被保留
- **精确延迟**: 测量真实的网络延迟，不是估算值
- **兼容性**: 生成的配置完全兼容 Shadowrocket iOS 应用

## 📱 支持的代理类型

Shadowrocket 原生支持以下所有代理类型：

| 协议 | 支持程度 | 说明 |
|------|---------|------|
| **SS** | ✅ 完全支持 | Shadowsocks，最常用 |
| **SSR** | ✅ 完全支持 | ShadowsocksR |
| **VMess** | ✅ 完全支持 | V2Ray VMess |
| **VLESS** | ✅ 完全支持 | Xray VLESS |
| **Trojan** | ✅ 完全支持 | Trojan-GFW |
| **Clash** | ✅ 完全支持 | 通过Clash配置导入 |

## 🚀 快速开始

### 方法一：使用 Clash 配置（推荐）

1. **运行测试**:
   ```bash
   ./test.sh        # 或使用 uv: ./test_uv.sh
   ```

2. **获取配置文件**:
   - 完整版: `output/clash_config.yml` (50个节点)
   - 精简版: `output/clash_mini.yml` (20个节点)

3. **导入 Shadowrocket**:
   - 打开 Shadowrocket
   - 点击右上角 "+"
   - 选择 "从剪贴板导入" 或 "从 URL 导入"
   - 复制 clash_config.yml 的内容到剪贴板，然后导入
   - 或者将文件上传到 iCloud/GitHub，获取 URL 直接订阅

### 方法二：使用节点 URI 列表

如果你更喜欢单独导入节点：

1. **获取 URI 列表**:
   - 完整版: `output/shadowrocket_nodes_full.txt`
   - 精简版: `output/shadowrocket_nodes_mini.txt`

2. **导入方式**:
   - 复制文件中的任意一行（一个 URI）
   - 打开 Shadowrocket
   - 点击右上角 "+"
   - 选择 "从剪贴板导入"
   - Shadowrocket 会自动识别并添加节点

### 方法三：GitHub Pages 订阅（最方便）

部署到 GitHub Pages 后，你可以直接订阅：

```
https://yourname.github.io/repo/clash.yml
```

在 Shadowrocket 中：
1. 首页 → 添加节点
2. 类型选择 "Subscribe"
3. URL 填入上面的地址
4. 保存并更新

## ⚙️ 配置说明

### 分流规则

生成的配置包含完整的分流规则：

- **全球直连**: 国内网站、局域网、本地连接
- **代理**: 国外网站、社交媒体、流媒体
- **自动选择**: URL 测试自动选择最快节点
- **负载均衡**: 智能分配流量

### 代理组

| 代理组 | 用途 | 建议 |
|--------|------|------|
| 🚀 节点选择 | 手动选择 | 日常使用 |
| ♻️ 自动选择 | 自动测速 | 推荐开启 |
| 📹 YouTube | 视频流媒体 | 选择延迟低的 |
| 🎥 Netflix | 奈飞解锁 | 需要支持奈飞的节点 |
| 🐟 漏网之鱼 | 其他流量 | 走代理 |

### DNS 设置

针对 Shadowrocket 优化的 DNS 配置：

- **默认DNS**: 223.5.5.5, 119.29.29.29 (国内)
- **Fallback**: 1.1.1.1, 8.8.8.8 (国外)
- **模式**: fake-ip (更好的性能和兼容性)

## 🔧 高级设置

### 开启 IPv6

如果你的网络支持 IPv6：

1. 打开 Shadowrocket
2. 设置 → IPv6 → 开启
3. 重新导入配置

### 排除特定应用

在 Shadowrocket 中：

1. 设置 → 分流 → 程序
2. 添加需要排除的应用
3. 选择 "DIRECT" 或 "REJECT"

### 自定义规则

在生成的配置文件中，你可以添加自定义规则：

```yaml
rules:
  - DOMAIN-SUFFIX,my-company.com,DIRECT
  - DOMAIN-KEYWORD,ad,REJECT
```

## 📊 严格模式说明

### 为什么有效率这么低？

严格模式下，有效率通常在 **5-30%** 是正常的，这是因为：

1. **防火墙屏蔽**: 很多免费节点的端口会被防火墙检测并屏蔽
2. **TCP探测**: 真实建立TCP连接，不像DNS解析那样容易通过
3. **延迟阈值**: 超过2秒的连接会被认为不稳定
4. **节点质量**: 免费节点本身就存在大量无效或低速节点

### 如何提高效率？

1. **添加更多订阅源**:
   ```bash
   vim subscriptions.txt
   # 添加更多链接
   ```

2. **定期更新**:
   - 免费节点经常失效，建议每天运行一次测试

3. **使用付费节点**:
   - 付费订阅的有效率通常在 60-90%

## 🐛 故障排查

### 配置导入失败

1. **检查 YAML 格式**:
   ```bash
   python3 -c "import yaml; yaml.safe_load(open('output/clash_config.yml'))"
   ```

2. **检查节点数量**:
   - 确保至少有几个有效节点

3. **手动测试节点**:
   ```bash
   python3 diagnose.py test <服务器> <端口>
   ```

### 连接失败

1. **检查网络**:
   - 确保 Shadowrocket 的 VPN 开关已打开
   - 检查是否有其他 VPN 冲突

2. **测试节点**:
   - 在节点列表中点击节点进行连通性测试
   - 如果显示超时，说明节点已失效

3. **更换节点**:
   - 选择其他延迟较低的节点
   - 或更新配置获取新节点

### 某些应用不走代理

1. **检查规则**:
   - 确认应用流量是否被 DIRECT 规则匹配

2. **添加自定义规则**:
   - 在 Shadowrocket 中添加应用级别的规则

## 💡 最佳实践

### 日常使用

1. **使用自动选择模式**:
   - Shadowrocket 会自动选择延迟最低的节点

2. **定期更新配置**:
   - 免费节点寿命短，建议每天更新

3. **备份配置**:
   - 在 Shadowrocket 中导出配置备份

### 网络优化

1. **开启 TCP Fast Open**:
   - 设置 → TCP Fast Open → 开启

2. **调整 MTU**:
   - 如果遇到连接问题，尝试调整 MTU 值

3. **使用 Fake IP**:
   - 已默认开启，提供更好的性能

## 📝 文件说明

```
output/
├── clash_config.yml           # Clash 完整配置 (50节点)
├── clash_mini.yml             # Clash 精简配置 (20节点)
├── shadowrocket_nodes_full.txt    # Shadowrocket URI 列表 (50节点)
├── shadowrocket_nodes_mini.txt    # Shadowrocket URI 列表 (20节点)
└── valid_nodes.json           # 节点原始数据
```

提示
- 当无有效节点时，生成器会输出占位的 clash_config.yml/clash_mini.yml 与空的 URI 列表，便于工作流发布流程继续执行。

## 🔗 相关链接

- [Shadowrocket 官网](https://shadowrocket.app/)
- [Clash 文档](https://github.com/Dreamacro/clash/wiki)
- [节点诊断工具](../diagnose.py)

## ❓ 常见问题

**Q: 为什么严格模式下有效率这么低？**
A: 严格模式会进行真实的 TCP 连接测试，而大多数免费节点的端口会被防火墙屏蔽。这是正常的，建议添加更多订阅源。

**Q: Shadowrocket 支持 VLESS 吗？**
A: 支持。我们的配置生成器会正确生成 VLESS 配置。

**Q: 可以直接导入 URI 吗？**
A: 可以。我们生成了 `shadowrocket_nodes_full.txt` 文件，每行是一个节点 URI，可以直接复制导入。

**Q: 多久更新一次配置？**
A: 免费节点建议每天更新。如果是付费订阅，可以每周更新一次。

**Q: 为什么有些节点延迟很低但无法连接？**
A: 延迟只代表网络连通性，不代表代理服务可用。严格模式会测试代理端口是否真正开放。
