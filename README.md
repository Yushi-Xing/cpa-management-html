# CPA management.html

为 CLIProxyAPI 提供单文件管理面板，保留官方界面，增加 Zed 认证回调提交、账单 Cookie 配置、额度刷新和进度条。

## 安装与自动更新

下载 [最新 Release](https://github.com/Yushi-Xing/cpa-management-html/releases/latest) 的 `management.html`，放入 CPA 实际读取的 `static` 目录。也可以让 CPA 自动获取：

```yaml
management:
  panel-github-repository: "https://github.com/Yushi-Xing/cpa-management-html"
  disable-auto-update-panel: false
```

合并到已有配置，保留管理密钥。旧 CPA 配置可能使用 `remote-management` 节点。此页面的 Zed 功能需要服务器已加载 Zed Linux 插件；登录、Cookie 和额度请求均通过 CPA 已鉴权的管理接口。

## Actions

推送主线或手动运行 `Build and publish CPA management panel` 构建当前已验证基线。每天检测官方面板更新；候选必须通过 Zed 回调、额度单元测试和 TypeScript 构建才发布，并更新 `panel-upstream.txt`。适配失败保留当前 Release 和基线。手动选择 `follow-upstream` 可立即测试最新官方面板。

此仓库仅包含前端适配、MIT 许可证和面板发布流程。Release 只有 `management.html`、`checksums.txt` 和公开的构建指纹。无需跨仓库访问令牌；本仓库使用自己的 Actions 默认令牌发布。

上游：[router-for-me/Cli-Proxy-API-Management-Center](https://github.com/router-for-me/Cli-Proxy-API-Management-Center)。构建的 HTML 内保留上游 MIT 许可证。
