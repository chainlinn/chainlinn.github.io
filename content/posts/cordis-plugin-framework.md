---
title: "一切皆插件：Cordis 插件框架拆解"
date: 2026-08-24T00:00:00+08:00
draft: false
tags: ["LLM", "Agent", "Cordis", "插件架构", "SDK"]
series: ["Agent"]
summary: "构建 agent 运行时 SDK 时，我选了 Cordis 作为内核。它把'一切皆插件'做成了可运行的机制：ctx 是主板，apply 是插拔，effect 是可逆注册，waterfall 是管线。这篇文章拆解这些机制，以及它们如何撑起一个 agent 运行时的解耦。"
---

在构建 agent 运行时 SDK 时，我面临一个选择：自研插件机制，还是站在已有的框架上。

最后选了 Cordis——koishi 生态里打磨多年的插件框架，也是 DeepSeek Harness 的内核。理由很直接：**"一切皆插件"不该是口号，它需要一套可运行的机制**——而 Cordis 把这套机制做完了。

这篇文章拆解它：ctx、apply、effect、事件分发、inject、配置。每个机制都配真实代码——来自我落地 agent 运行时时的实践。

如果你是从前端过来的（Vue/React/Redux），这篇文章的暗线是：**Cordis 的抽象不是新东西，是前端已有抽象在插件框架里的重组**。每个机制我都会给出前端的参照系——你会发现，学会 Cordis 的过程，其实是把熟悉的东西换个环境重新认一遍。

## 1. ctx 是主板，插件是部件

Cordis 的核心抽象是一个 `Context`。忘掉"上下文"这个翻译——**ctx 是主板**：所有插件共享的注册表、事件总线、生命周期容器。

前端参照：它像 **EventBus + 全局 store + provide/inject 的合体**——所有插件共享同一个"环境"，往上面注册东西、从上面取东西。

插件就是插到主板上的部件。最朴素的插件是一个函数：

```ts
// 插件 = 一个函数，接收 ctx，往主板上注册东西
export function apply(ctx: Context) {
  ctx.on('message', (text) => {
    console.log(`收到消息: ${text}`)
  })
}
```

Cordis 加载插件时调用 `apply(ctx)`——这就是插拔动作：插件描述它贡献什么，主板负责组装。

插件有三种形态，按需选择：

```ts
// 1. 函数（最常用）：named export 的 apply
export function apply(ctx: Context) {}

// 2. 对象：带 apply 方法的对象
export const objectPlugin = {
  name: 'object-plugin',
  apply(ctx: Context) {},
}

// 3. 类：Service 子类——要暴露服务给别的插件时
export class MyService extends Service {
  constructor(ctx: Context) {
    super(ctx, 'myService')   // 注册为 ctx.myService
  }
}
```

第三种形态很关键：**类插件在 ctx 上注册一个服务**——别的插件可以通过 `ctx.myService` 使用它。这是插件间通信的主通道。

前端参照：类插件 ≈ Vue 的 **provide**——把服务"提供"到公共环境，谁需要谁注入。

## 2. effect：可逆注册

插件会注册很多东西：事件监听、定时器、服务、资源。注册了就该能注销——Cordis 用 `ctx.effect()` 统一解决：

```ts
export function apply(ctx: Context) {
  // effect 注册"卸载时要执行的回调"
  ctx.effect(() => {
    const timer = setInterval(() => {}, 1000)
    return () => clearInterval(timer)   // 卸载时自动清理
  })
}
```

每个插件的生命周期是明确的（PENDING → LOADING → ACTIVE → UNLOADING → DISPOSED），卸载时**所有 effect 的回调逆序执行**——注册的监听、资源、服务全部自动撤销。

前端参照：`effect()` 就是一个 **mini 版 Vue 生命周期 hook**——`onMounted` 里注册、`onUnmounted` 里清理，被压缩成一个函数：注册即声明清理，卸载由框架统一触发。Vue 组合式 API 的用户会对这个心智模型感到非常熟悉。

这意味着插件开发者的心智负担大幅降低：**注册时声明清理逻辑，卸载的事框架管**。我们的工具注册就是这么写的：

```ts
register(definition: ToolDefinition): () => void {
  registry.set(definition.name, definition)
  return ctx.effect(() => () => {
    registry.delete(definition.name)   // 插件卸载 = 工具自动注销
  })
}
```

"注册返回注销"成了一个贯穿全库的模式。

## 3. 事件分发：五个模型

Cordis 的事件系统不是简单的发布订阅——它提供**五种分发模型**，每种解决一类问题：

| 模型 | 语义 | 适合 |
|---|---|---|
| `emit` | 广播，全部监听者执行 | 通知（"工具执行完了"） |
| `parallel` | 并行执行 | 无依赖的观察者 |
| `serial` | 串行执行 | 有顺序的观察者 |
| `bail` | 短路——第一个有返回值的胜出 | 查找/裁决（"谁能处理这个"） |
| `waterfall` | **瀑布——每个监听者可以改写结果或拦截** | 管线/中间件（审批、鉴权、变换） |

对 agent 运行时，`waterfall` 是最重要的一个。它是中间件语义：监听者收到参数，可以选择直接返回（短路）或调用 `next()` 委托给下一个：

前端参照：这不是新概念——**Koa 中间件、Express 的 next()、axios 拦截器、webpack loader** 全是这个模式。前端写过后端中间件的人，看到 `next()` 的那一刻就懂了 waterfall 的全部语义：每个监听者是一层洋葱，`next()` 是剥到下一层。

```ts
ctx.on('tools/pre-execute', async (exec, next) => {
  // 审批：敏感工具调用需要人工确认
  if (!isSensitive(exec.name)) return next()   // 放行
  const approved = await askUser(exec)
  if (!approved) return { reject: true }        // 拦截
  return next()
})
```

这就是 agent 运行时"防线插件"的挂载面：审批、幂等、限流、重试，全部挂在瀑布上，互不侵入。**内核提供管线，策略由插件决定**——这是"一切皆插件"落地的关键。

## 4. inject：依赖通道（一个真实的坑）

插件依赖别的插件提供的服务时，用 `inject` 声明：

```ts
class LlmAdapter extends Service {
  // 声明依赖：需要 ctx.llm（由别的插件提供）
  static inject = ['llm']
  constructor(ctx: Context) {
    super(ctx, 'llmAdapter')
    ctx.llm.registerAdapter(...)   // ← 这里会炸
  }
}
```

直接 `ctx.plugin(LlmAdapter)` 会得到这个错误：

```
cannot get property "llm" without inject
```

**声明了 inject 的插件，必须通过 `ctx.inject()` 通道激活**——它拿到的是一个"注入过依赖"的上下文：

```ts
await ctx.plugin(LlmRuntime)   // 先装提供 llm 服务的插件
await ctx.inject(['llm'], async (injectCtx) => {
  await injectCtx.plugin(LlmAdapter)   // 在注入通道里激活
})
```

这个坑的真实教训是：**inject 不是声明"我想要"，是声明"我必须在这个通道里拿"**——它把依赖关系变成了显式的激活约束，而不是运行时碰运气。声明式配置（cordis.yml）会自动处理这条通道，编程式装配必须显式走 `ctx.inject`。

前端参照：`inject` 这个名字就是 **Vue 的 provide/inject**——但它比 Vue 严格：Vue 的 inject 没找到依赖时只是警告，Cordis 的 inject 没走对通道直接报错。**依赖关系从"约定"升级成了"约束"**——这正是插件框架需要的严谨度。

## 5. 配置：Schema 校验，错配 fail loud

每个插件可以声明自己的配置 schema，装配时统一校验：

```ts
export class LlmService extends Service {
  static Config = Schema.object({
    baseUrl: Schema.string().default('https://api.deepseek.com'),
    model: Schema.string().default('deepseek-v4-flash'),
  })
}
```

配置写错，**启动时直接报错**，而不是运行到一半炸：

```
invalid config: providers.deepseek.models[0].id must be a string
```

这看起来是小事，但对 SDK 至关重要——业务侧接入时最常见的坑就是配置错，fail loud 让错误发生在"装配时"而不是"线上运行时"。

## 6. 实战：seam 三角色

"一切皆插件"最漂亮的实践，是能力缝（capability seam）的三角色分工：**Service Definition / Service Provider / Consumer**。

以我们的模型层为例：

```
dsh-llm（Service Definition）       dsh-llm-pi-ai（Provider）
  ├─ 注册 ctx.llm 服务（插座）        ├─ 把 deepseek 路由插进插座
  ├─ 定义调用协议                      └─ 内置模型目录/凭证/协议
  └─ 管理适配器注册表
         ↑
    loop（Consumer）
  ├─ 只依赖 ctx.llm（插座）
  └─ 感知不到任何 Provider
```

`dsh-llm` 是插座——定义 `ctx.llm` 服务、调用协议、适配器注册表。`dsh-llm-pi-ai` 是插上去的适配器——注册 deepseek 路由。`loop`（循环）是消费者——只依赖插座，不知道底下是哪个 Provider。

**换模型供应商 = 换一个 Provider 插件**，seam 和 loop 一行不用改。这就是插件架构给 agent 运行时的承诺：能力可替换，解耦到协议层。

## 前端的迁移地图

把全文的参照系收拢成一张表：

| 前端已有抽象 | Cordis 的对应 | 差异点 |
|---|---|---|
| Vue `onMounted`/`onUnmounted` | `effect()` | 注册与清理压缩成一个函数，卸载统一触发 |
| Koa 中间件 / axios 拦截器 / webpack loader | `waterfall` 事件 | 语义完全一致：`next()` 委托、短路即返回 |
| Vue provide/inject | `inject` 通道 | 更严格：依赖缺失从"警告"升级为"报错" |
| EventBus + 全局 store | `ctx` | 加上了服务注册表与生命周期容器 |
| Vue provide（服务） | 类插件（Service） | 服务注册进公共环境，谁需要谁注入 |
| Redux action log + reducer | 事件溯源（会话日志 + 投影） | 见上篇《Agent 记忆的正确形态》 |

迁移思想的核心一句话：**Cordis 没有发明新抽象，它把前端已经熟悉的心智模型（生命周期、中间件、依赖注入、事件总线）重组进了"一切皆插件"的框架里**——学它不需要空杯，只需要认出来。

## 结论

Cordis 用一套小而完整的机制兑现了"一切皆插件"：

- **ctx**：主板——插件共享的注册表与事件总线
- **apply**：插拔动作——插件描述贡献，主板负责组装
- **effect**：可逆注册——注册即声明清理，卸载框架管
- **waterfall**：管线——审批/防线/治理的挂载面
- **inject**：依赖通道——依赖关系变成显式激活约束
- **Schema**：配置校验——错配 fail loud

对 agent 运行时来说，这套机制的价值不只是"解耦"：**高频问题（超时、幂等、重试、上下文管理）可以逐个沉淀为插件，挂在扩展点上，互不侵入**——业务逻辑与基础能力分离，迭代不伤内核。

这也是为什么我把 SDK 的内核押在 Cordis 上：它不是又一个框架，而是一套让"持续沉淀"成为可能的基础设施。
