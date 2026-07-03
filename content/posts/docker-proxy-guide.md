---
title: "转载｜如何优雅的给 Docker 配置网络代理"
date: 2026-07-03T22:00:00+08:00
draft: false
tags: ["Docker", "网络", "代理"]
categories: ["技术"]
series: ["Docker 实践"]
summary: "转载一篇关于 Docker 三种场景下代理配置的详细教程：Dockerd 代理、Container 代理、Docker Build 代理。"
canonicalURL: "https://www.cnblogs.com/Chary/p/18096678"
---

> 本文转载自 [博客园 charygao1990](https://www.cnblogs.com/Chary/p/18096678)，仅作学习备忘之用。

---

有时因为网络原因，比如公司 NAT，或其它啥的，需要使用代理。Docker 的代理配置，略显复杂，因为有三种场景。但基本原理都是一致的，都是利用 Linux 的 `http_proxy` 等环境变量。

## Dockerd 代理

在执行 `docker pull` 时，是由守护进程 dockerd 来执行。因此，代理需要配在 dockerd 的环境中。而这个环境，则是受 systemd 所管控，因此实际是 systemd 的配置。

```bash
sudo mkdir -p /etc/systemd/system/docker.service.d
sudo touch /etc/systemd/system/docker.service.d/proxy.conf
```

在这个 `proxy.conf` 文件（可以是任意 `*.conf` 的形式）中，添加以下内容：

```ini
[Service]
Environment="HTTP_PROXY=http://proxy.example.com:8080/"
Environment="HTTPS_PROXY=http://proxy.example.com:8080/"
Environment="NO_PROXY=localhost,127.0.0.1,.example.com"
```

其中 `http://proxy.example.com:8080` 要换成可用的免密代理。通常使用 cntlm 在本机自建免密代理，去对接公司的代理。

重启生效：

```bash
sudo systemctl daemon-reload
sudo systemctl restart docker
```

检查是否生效：

```bash
sudo systemctl show --property=Environment docker
docker info | grep Proxy
```

> **注意：** 通过 `daemon.json` 方式配置的优先级会高于通过 systemd 配置（Docker Engine 23.0+ 支持）。

---

## Container 代理

在容器运行阶段，如果需要代理上网，则需要配置 `~/.docker/config.json`。以下配置只在 Docker 17.07 及以上版本生效。

```json
{
  "proxies": {
    "default": {
      "httpProxy": "http://proxy.example.com:8080",
      "httpsProxy": "http://proxy.example.com:8080",
      "noProxy": "localhost,127.0.0.1,.example.com"
    }
  }
}
```

这个是用户级的配置，修改后立即生效，但只针对以后启动的 Container，对已经启动的 Container 无效。

此外，容器的网络代理，也可以直接在其运行时通过 `-e` 注入：

```bash
docker run --env HTTP_PROXY="http://proxy.example.com:8080" <some-image>
```

**两种方法分别适合不同场景：**
- `config.json` 非常方便，适合个人开发环境
- `-e` 注入更显式，适合 CI/CD 自动构建环境或上线环境

> **警告：** 无论是 `docker run` 还是 `docker build`，默认是网络隔绝的。如果代理使用的是 `localhost:3128` 这类，会无效。仅限本地的代理必须加上 `--network host` 才能正常使用。

---

## Docker Build 代理

虽然 `docker build` 的本质也是启动一个容器，但是环境会略有不同，用户级 `config.json` 配置无效。在构建时，需要通过 `--build-arg` 注入：

```bash
docker build . \
  --build-arg "HTTP_PROXY=http://proxy.example.com:8080/" \
  --build-arg "HTTPS_PROXY=http://proxy.example.com:8080/" \
  --build-arg "NO_PROXY=localhost,127.0.0.1,.example.com" \
  -t your/image:tag
```

> **重要：** 不要在 Dockerfile 中使用 `ENV` 指令配置代理！这会把代理服务器打包进镜像，可能造成安全隐患，也可能导致通过此镜像创建的容器访问不到私有代理服务器。

---

## 总结

| 场景 | 配置方式 | 生效时机 |
|------|---------|---------|
| `docker pull` | systemd 或 `daemon.json` | 重载 systemd + 重启 dockerd |
| `docker run` | `~/.docker/config.json` 或 `-e` 注入 | 下次启动容器生效 |
| `docker build` | `--build-arg` 注入 | 执行时立即生效 |

关键是理解每种场景的代理作用范围——是从 systemd 层面、用户配置层面，还是运行参数层面。
