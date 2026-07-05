---
title: "Changelog · v1.0：dev0 体验增强"
date: 2026-07-05T00:00:00+08:00
draft: false
tags: ["changelog"]
series: ["博客优化"]
summary: "声音引用 shortcode、外链卡片、JetBrains Mono 代码字体、Zpix 像素字体、Giscus 评论系统......"
---

这是 dev0 博客的第一次体验增强更新，聚焦阅读体验和视觉风格。

## 声音引用

像推文一样引用别人的发言，头像、名字、时间一目了然。

**基础用法：**

```tpl
{{</* voice name="santu" handle="@santuchuan" date="2026-07-04" */>}}
写了个音乐播放器，音频存在网盘，让浏览器直接播 FLAC。
{{</* /voice */>}}
```

{{< voice name="santu" handle="@santuchuan" date="2026-07-04" >}}
写了个音乐播放器，音频存在网盘，让浏览器直接播 FLAC。
{{< /voice >}}

**参数说明：**

| 参数 | 必填 | 说明 | 默认值 |
|------|------|------|--------|
| `name` | 是 | 发言人名字 | — |
| `handle` | 否 | 社交媒体 handle | 不显示 |
| `date` | 否 | 发言日期 | 不显示 |
| `avatar` | 否 | 自定义头像 URL | 作者头像 |

**简写模式（只写名字）：**

```tpl
{{</* voice name="路人甲" */>}}
这项目思路不错，学到了。
{{</* /voice */>}}
```

{{< voice name="路人甲" >}}
这项目思路不错，学到了。
{{< /voice >}}

**内嵌代码块也支持：**

```tpl
{{</* voice name="dev0" handle="@chainlinn" date="2026-06-28" */>}}
''kotlin
fun rsaDecrypt(data: ByteArray): ByteArray { ... }
''
{{</* /voice */>}}
```

{{< voice name="dev0" handle="@chainlinn" date="2026-06-28" >}}
```kotlin
fun rsaDecrypt(data: ByteArray): ByteArray {
    val decrypted = BigInteger(1, chunk).modPow(RSA_E, RSA_N)
    val decBytes = decrypted.toByteArray()
    val idx = decBytes.indexOf(0)
    return if (idx >= 0) decBytes.copyOfRange(idx + 1, decBytes.size) else decBytes
}
```
{{< /voice >}}

## 外链卡片

构建时自动抓取目标站点的 OGP 标题和描述，省去手动填写。

**自动抓取模式：**

```tpl
{{</* card "https://javabetter.cn/" */>}}
```

{{< card "https://javabetter.cn/" >}}

**手动指定模式：**

```tpl
{{</* card url="https://builder.elegantresume.pro/" title="ElegantResume Builder" desc="在线简历生成器" */>}}
```

## 代码字体

代码块全部换为 JetBrains Mono，自托管 woff2（400 + 700），零外部依赖。

```kotlin
fun build(): String {
    val result = StringBuilder()
    repeat(10) { result.append("JetBrains Mono") }
    return result.toString()
}
```

## 评论系统

由 Utterances 迁移至 Giscus，后端从 GitHub Issues 改为 Discussions，支持 `noborder_light` / `noborder_dark` 主题自动切换。

## 像素字体

Zpix 自托管像素字体（866KB woff2），覆盖非正文区域。

<div class="zpix-demo">
  <div class="zpix-row">
    <span class="zpix-label">导航菜单</span>
    <span class="zpix-sample">dev0&nbsp;&nbsp;文章&nbsp;&nbsp;时间线&nbsp;&nbsp;系列&nbsp;&nbsp;标签&nbsp;&nbsp;收录&nbsp;&nbsp;搜索</span>
  </div>
  <div class="zpix-row">
    <span class="zpix-label">首页标题</span>
    <span class="zpix-sample">我试图留下些什么，欢迎来到 dev0 的博客</span>
  </div>
  <div class="zpix-row">
    <span class="zpix-label">热力图</span>
    <span class="zpix-sample zpix-mono">Mon · Wed · Fri · 这一年留下了 42 次痕迹 · Less ■■■ More</span>
  </div>
  <div class="zpix-row">
    <span class="zpix-label">页脚</span>
    <span class="zpix-sample">© 2026 dev0 · Powered by Hugo & PaperMod</span>
  </div>
</div>

<style>
.zpix-demo {
  background: var(--code-bg);
  border-radius: 12px;
  padding: 16px 20px;
  margin: 1em 0 0;
  border: 1px solid var(--border);
}
.zpix-row {
  margin-bottom: 10px;
}
.zpix-row:last-child { margin-bottom: 0; }
.zpix-label {
  display: block;
  font-size: 12px;
  color: var(--secondary);
  margin-bottom: 2px;
}
.zpix-sample {
  font-family: "Zpix", sans-serif;
  font-size: 14px;
  color: var(--primary);
  line-height: 1.8;
}
.zpix-mono { font-size: 12px; }
</style>

## 热力图

首页底部贡献热力图（Cal-Heatmap），展示发文活跃度，支持年份切换、星期标签、深浅色统计图例。

## Excalidraw 图表

文章中的流程图全部改用 Excalidraw 手绘风格 SVG，暗色模式下自动反色。

![整体架构流程图](/post/115-cdn-302-redirect-play-2.svg)

## 作者药丸

文章 meta 行增加极简冷淡风作者药丸。在文章 front matter 中启用 AI 共创者：

```yaml
---
author: "santu"
aiCoAuthor: true   # 设为 true 显示 AI 共创药丸
---
```

效果：日期、阅读时间、字数之后展示作者和 AI 共创者的药丸标签，支持亮色/暗色/自动三种模式自动适配。

---

更多细节见 [GitHub](https://github.com/chainlinn/chainlinn.github.io)。
