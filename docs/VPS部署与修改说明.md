# Oracle AMD VPS：CloudFlyer 修复与部署

本分支整理 2026-10-13 配合 [wipoman/ns-sign](https://github.com/wipoman/ns-sign) 排障时的修复。运行环境为 Oracle AMD64 / Ubuntu、Docker；以下为 root 命令。

## 修改内容与验证范围

| 项目 | 修改 |
| --- | --- |
| `cloudflyer/bypasser.py` | 在 `locate_cf_button()` 的快捷查找中捕获 `AttributeError`，置 `button=None`，使缺失 shadow root 时仍能进入原有递归查找。其他异常保留原处理方式。 |
| `Dockerfile.vps` | 新增基于本次实测原镜像 digest 的构建配方；先安装 Google 官方签名公钥，再升级 Chrome stable；复制本仓库的按钮查找补丁。 |
| `Dockerfile.vps` | 直接用 `/app/venv/bin/python -u -m cloudflyer` 启动，跳过原 Kasm/VNC 完整桌面入口；使用 `-L` 启动虚拟显示。 |
| 文档 | 整理单实例、共享内存、本地端口、升级与回滚、日志检查方法。 |
| `tests/` | 覆盖快捷查找成功、缺失 shadow root 后递归回退、浏览器断开异常传播。 |

本次 VPS 实测：Chrome 从 `126.0.6478.126` 升到 `155.0.8059.39`，DrissionPage 保留 `4.0.5.6`；修复后 NodeSeek Turnstile 返回有效令牌。这里的 Dockerfile 在构建时安装 Google 仓库当时提供的 stable，未来版本不一定是 155。基础镜像固定 digest，但 Chrome 软件源不是版本快照。

原 `Dockerfile`、桌面启动脚本及上游 Docker Hub/PyPI 发布工作流保留原样；本分支的 VPS 使用方法明确选择 `Dockerfile.vps`。没有给 `jackzzs/cloudflyer` 发布新镜像，也没有新增自动镜像发布。此次整理环境没有 Docker，新增构建配方未实际构建；它固化的是用户 VPS 上已执行成功的更新和启动方式。

## 1. 构建带补丁的镜像

```bash
git clone https://github.com/wipoman/cloudflyer-oss.git /opt/cloudflyer-src
cd /opt/cloudflyer-src
docker build --pull -f Dockerfile.vps -t cloudflyer-local:vps .
```

此配方针对 AMD64；不是 ARM64 构建方案。升级已有源码用 `git pull --ff-only`；需要重新取得最新 Chrome 时用 `docker build --pull --no-cache -f Dockerfile.vps -t cloudflyer-local:vps .`。

## 2. 启动

确认没有其他容器占用名字 `cloudflyer` 或本机 3000 端口；已有部署先看下一节迁移步骤。

```bash
read -r -p 'CloudFlyer 客户端密钥（明文显示）：' CLOUDFLYER_CLIENT_KEY
docker run -d \
  --name cloudflyer \
  --restart unless-stopped \
  --shm-size=256m \
  -p 127.0.0.1:3000:3000 \
  cloudflyer-local:vps \
  -K "$CLOUDFLYER_CLIENT_KEY" -H 0.0.0.0 -P 3000 -M 1 -L
unset CLOUDFLYER_CLIENT_KEY
```

- 输入密钥时不额外加引号；命令里的 `"$CLOUDFLYER_CLIENT_KEY"` 必须保留引号，以保持密钥中的特殊字符。
- `-L` 在这版代码里通过 Xvfb 创建虚拟显示，不等于 Chrome 原生无头模式。
- `-M 1` 限制单实例并发，适合本次小内存 VPS。
- 容器内监听 `0.0.0.0`，宿主机只映射 `127.0.0.1`。同机 ns-sign 使用 `--network host` 访问 API。
- **上游目前要求传入 `clientKey` 字段，但没有对其值做实际鉴权；本分支没有修改该行为。务必保持上述本地端口绑定，不把它当成具备密钥保护的公网服务。**

## 3. 已有 cloudflyer 容器迁移

更新仓库不会自动修改 VPS，也不会改变正在运行的容器。先构建新镜像，保留已验证的旧容器与镜像，再切换；不要直接删除旧容器。

```bash
docker commit cloudflyer cloudflyer-local:before-repo-update
docker stop cloudflyer
docker rename cloudflyer cloudflyer-before-repo-update
```

然后执行第 2 节的启动命令。若备份名字已存在，先换一个未占用的备份名；不要覆盖唯一的可用备份。

如需回滚新容器：

```bash
docker stop cloudflyer
docker rename cloudflyer cloudflyer-new-failed
docker rename cloudflyer-before-repo-update cloudflyer
docker start cloudflyer
```

`docker restart` 会保留容器内修改；删除后从原 `jackzzs/cloudflyer` 重建则不保留。所以本分支把修复固化到构建配方，而不是只依赖容器手工更新。

## 4. 检查

```bash
docker ps --filter name=cloudflyer
docker logs --tail 80 cloudflyer
docker exec cloudflyer google-chrome --version
docker exec cloudflyer /app/venv/bin/python -c 'from importlib.metadata import version; print(version("DrissionPage"))'
curl -i --max-time 10 http://127.0.0.1:3000/
```

根路径 `/` 返回 `404 Not Found` 是因为没有定义根路由，只能说明 HTTP 服务已响应，不能据此证明浏览器或验证码任务成功。真正的功能验证请运行 ns-sign 文档里的 `login-test`；其会创建任务、轮询结果并校验 NodeSeek 新会话。

CloudFlyer 的 `Turnstile` 任务返回验证令牌，不会替用户完成 NodeSeek 的账号登录、邮箱验证或持久保存 NodeSeek Cookie。后者由 ns-sign 本地入口处理。无需为了签到开放 5901/6901 等桌面端口。

## 5. 本地回归测试

```bash
python3 -m unittest discover -s tests -v
```

测试使用模拟 DOM，不启动真实 Chrome，不保证每次真实验证码都能通过。浏览器升级、网站变化、IP 或账号风控仍可能影响结果；若返回超时，应结合完整任务错误与容器日志排查。
