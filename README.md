# dev0's Blog

[devs0.com](https://devs0.com/) — 技术博客，基于 [Hugo](https://gohugo.io/) + [PaperMod](https://github.com/adityatelange/hugo-PaperMod) 主题。

## 项目结构

```
chainlinn.github.io/
├── archetypes/    # Hugo 模板
├── assets/        # 资源（SCSS 等）
├── content/
│   └── posts/     # 文章（Markdown）
├── layouts/       # 自定义布局覆盖
├── static/
│   ├── post/      # 文章配图
│   ├── css/       # 自定义样式
│   └── js/        # 自定义脚本
├── themes/
│   └── PaperMod/  # 主题（git submodule）
├── hugo.toml      # Hugo 配置
└── public/        # 构建输出（GitHub Pages 部署）
```

## 文章配图

文章配图放在 `static/post/` 下，命名规则：`{文章-slug}-{序号}.{扩展名}`。

例如 `115-cdn-302-redirect-play.md` 的配图：
- `static/post/115-cdn-302-redirect-play-1.png` — 302 直链理想数据流（时序图）
- `static/post/115-cdn-302-redirect-play-2.png` — 整体架构流程图
- `static/post/115-cdn-302-redirect-play-3.png` — RSA 加密流程
- `static/post/115-cdn-302-redirect-play-4.png` — RSA 解密流程
- `static/post/115-cdn-302-redirect-play-5.png` — XOR chunk-aligned 分段逻辑

文中引用方式：
```markdown
![图片描述](/post/115-cdn-302-redirect-play-1.png)
```

## 本地开发

```bash
# 克隆（含主题子模块）
git clone --recurse-submodules https://github.com/chainlinn/chainlinn.github.io.git
cd chainlinn.github.io

# 启动开发服务器
hugo server -D

# 构建
hugo
```

## 部署

推送到 `main` 分支，GitHub Actions 自动构建并部署到 GitHub Pages。
