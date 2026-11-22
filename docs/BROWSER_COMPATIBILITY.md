# 2026-11-22 浏览器兼容性修复

配套恢复工具位于 [wipoman/ns-sign](https://github.com/wipoman/ns-sign/blob/main/docs/BROWSER_RECOVERY.md)。本次把 VPS 容器内验证过的修改固化到源码和 `Dockerfile.vps`，不会自动更新现有容器。

## 修改内容

| 文件 | 修改及依据 |
| --- | --- |
| `cloudflyer/instance.py` | 删除 CONNECT 和普通请求中对 `challenges.cloudflare.com` 的第三方 DNS/IP 改写，保留官方主机名，使用正常解析路径。实机曾出现第三方解析 `socket.gaierror: -2`，而官方验证域名解析正常。 |
| `cloudflyer/instance.py` | 允许 CSS、图片、字体响应；仍保留音视频及超过 30 MB 的响应过滤。实机原页面样式错乱，修改后登录页样式表正常加载。 |
| `cloudflyer/instance.py` | 移除对整个 Turnstile `/turnstile/v0/` 前缀响应的缓存和重放代码。该前缀不能一律视为可跨任务复用的静态文件。VPS 上原先通过禁止写缓存并重启清空内存实现相同效果，仓库删除了不再使用的缓存路径。 |
| `Dockerfile.vps` | 在原 Chrome 更新配方上复制 `bypasser.py` 和 `instance.py`，显式安装 `xdotool` / `x11-utils`，供受控桌面操作与检查使用。 |
| 文档与测试 | 增加故障原因、验证范围、恢复入口和离线回归测试。 |

十月已提交的按钮 shadow root 查找回退、Google 软件源公钥更新、Chrome stable 升级、单实例虚拟显示启动方式继续保留。没有修改 Docker 引擎，也没有新增 Docker Hub 或 PyPI 自动发布。

## 构建和使用

已有克隆目录：

```bash
git -C /opt/cloudflyer-src pull --ff-only
docker build --pull -f /opt/cloudflyer-src/Dockerfile.vps \
  -t cloudflyer-local:vps /opt/cloudflyer-src
```

首次部署与保留旧容器的迁移/回滚步骤见 [VPS 部署说明](VPS部署与修改说明.md)。要刷新 Chrome 安装层需显式加 `--no-cache`；本次实机为 Chrome `155.0.8059.39` 和 DrissionPage `4.0.5.6`，构建时 Chrome stable 版本随官方软件源变化。

**已成功恢复的 VPS 不必立即重建。** `docker restart` 保留容器内代码修改，但正在使用的浏览器验证/登录状态不应视为一定能保留。删除容器后从旧 `jackzzs/cloudflyer` 重建，不会带上本分支补丁；需使用新构建镜像。旧容器/commit 镜像可能包含会话数据，仅在本机私有保存。

实际 Chrome 的 DISPLAY 可能为 `:0`，而容器默认 DISPLAY 是 `:1`。不要全局写死 `:0`，也不要根据一次截图永久硬编码点击位置。ns-sign 的恢复脚本会读取实际 Chrome 进程环境并检查窗口几何信息。

API 继续只映射到宿主机 `127.0.0.1:3000`，不开放浏览器调试或桌面端口。现有 API 的 clientKey 未做值鉴权，沿用原文档的本地访问部署。

## 结果与限制

- 修复后实机可加载正常 NodeSeek 登录页，取得整页验证信息；完成登录页验证后，浏览器账号校验和签到均返回 200。
- 新会话保存后，原 ns-sign HTTP 入口及 systemd 服务成功识别“今日已签到”，无需更换定时入口。
- 取得 `cf_clearance` 不等于账号已登录，也不保证把它复制给另一 HTTP 客户端就能通过。CloudFlyer 任务 success 不等于 NodeSeek 签到成功。
- 官方检测页成功不能保证 NodeSeek 的验证也成功。本次仍需要人工补点；首次点击未成功的原因未被严格隔离。
- CSP/CORS 控制台记录不一定是阻断原因；本轮没有删除 CSP、关闭浏览器安全机制或重写站点鉴权逻辑。
- 旧的挑战 HTML 模板替换、任务结束返回内部首页等行为保持不变。恢复工具按此行为处理，未将 CloudFlyer 改造为永久登录浏览器服务。
- 本轮只对相关逻辑进行离线测试，未在整理环境重新构建 Docker 镜像；真实验证结果来自现有 VPS 操作日志，不承诺未来无人值守续登录成功。

## 回归测试

```bash
python3 -m unittest discover -s tests -v
```

覆盖请求主机名保持、验证响应不缓存、页面资源通过、音视频/大文件限制及原按钮查找回退。无需真实账号或访问验证码站点。
