---
title: "刻度尺演示"
date: 2026-07-04T00:30:00+08:00
draft: false
tags: ["Hugo"]
categories: ["技术"]
---

# 第一章

它是最强的静态网站生成器之一。

# 第二章

用 Markdown 写内容，自动转 HTML。

## 安装

```bash
brew install hugo
```

## 创建站点

```bash
hugo new site my-blog
```

### 目录结构

`content/` 放文章，`themes/` 放主题，`hugo.toml` 是配置。

### 新建文章

`hugo new content posts/hello.md`，改 front matter 里的 `draft: false` 就能发布。

## 本地预览

`hugo server -D`，浏览器打开 `localhost:1313`。

### 热重载

改文章保存后页面自动刷新。

### 包含草稿

`-D` 参数让草稿文章也可见。

# 第三章

主题市场上有几百个免费主题。

## PaperMod

简洁、快、SEO 好。

### 安装

```bash
git submodule add https://github.com/adityatelange/hugo-PaperMod themes/PaperMod
```

### 配置

在 `hugo.toml` 里设 `theme = 'PaperMod'`。

### 首页模式

支持列表模式、HomeInfo 模式、Profile 模式三种。

## Blowfish

功能丰富，自带搜索和暗色模式。

### 特色

短代码多，适合技术博客。

### 暗色模式

根据系统设置自动切换，也可以手动切换。

## Stack

卡片风格，适合图片多的博客。

# 第四章

写完文章直接推 GitHub，CI 自动建好。

## 目录改造

顶部目录体验差，改成了右侧刻度尺。

### 模板层

`single.html` 里加容器。

### 样式层

CSS 固定定位加三级宽度。

### 脚本层

JS 动态生成刻度加 ScrollSpy。

# 第五章

一个文件加几行代码，效果立竿见影。
