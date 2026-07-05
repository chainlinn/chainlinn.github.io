---
title: "草稿 | ReAct、Plan-and-Execute、Reflection：三种 Agent 范式梳理"
date: 2026-07-05T23:16:17+08:00
draft: false
tags: ["AI", "Agent", "LLM"]
series: ["Agent 笔记"]
aiCoAuthor: true
summary: "ReAct 边想边做、Plan-and-Execute 先规划再执行、Reflection 自我反思复盘——三种主流 Agent 范式的原理、流程、对比与适用场景。"
---

把 LLM 当成调用工具的「大脑」，就构成了 Agent。但「怎么调用工具」这件事，社区已经沉淀出几种相对成熟的范式。本文梳理三种最常被提及的：**ReAct**、**Plan-and-Execute**、**Reflection**。

## TL;DR

| 范式 | 核心思路 | 一句话 |
|------|---------|--------|
| ReAct | 推理与行动交替 | 想一步，做一步，看一步 |
| Plan-and-Execute | 先规划，再执行 | 先出整体计划，再逐步落地 |
| Reflection | 自我评估与修正 | 做完回头复盘，错了就重来 |

三者并非互斥，实践中常常组合使用。

---

## 一、ReAct：Reasoning + Acting

ReAct（Yao et al., 2022）的核心思想是让模型在**推理（Thought）**和**行动（Action）**之间交替推进，每一步行动后观察结果（Observation），再决定下一步。

### 循环结构

```
Thought（想） → Action（做） → Observation（看） → Thought → ...
```

一个典型轨迹：

```
Thought: 用户问的是 2024 年诺贝尔文学奖得主，我需要搜索。
Action: search("2024 Nobel Prize in Literature")
Observation: 韩江，韩国作家。
Thought: 拿到答案了，可以回复。
Action: finish("韩江")
```

### 优点

- **简单直观**：一个循环搞定，prompt 工程成本低。
- **灵活**：每一步都能根据最新观察调整方向，适合信息检索、Web 浏览这类结果不可预知的任务。

### 缺点

- **容易跑偏**：没有全局规划，长任务里可能反复试错、来回横跳。
- **token 消耗高**：每一步都要把历史 Thought/Observation 塞进上下文。
- **延迟累积**：串行执行，步骤多时延迟叠加。

### 适用场景

- 搜索问答、事实核查
- Web 浏览、信息抽取
- 短链路、步骤数不确定的任务

---

## 二、Plan-and-Execute：先规划，再执行

Plan-and-Execute（LangChain 提出）把流程拆成两段：先用一个 **Planner** 生成完整的步骤计划，再由 **Executor** 逐步执行每个步骤，必要时回到 Planner 重新规划。

### 流程结构

```
Planner：生成 [步骤1, 步骤2, 步骤3, ...]
        ↓
Executor：执行步骤1 → 结果1
        执行步骤2 → 结果2
        ...
        ↓
（若中途发现计划不合适）→ 重新规划
```

### 优点

- **全局视野**：先有整体蓝图，减少来回试错。
- **可执行性强**：计划显式列出，便于人工审阅、干预。
- **可并行**：无依赖的步骤可以并行执行，降低延迟。

### 缺点

- **计划可能脱离实际**：Planner 一次性输出，若对工具能力或数据估计错误，整条计划都得返工。
- **需要 re-plan 机制**：现实任务很少能完全按原计划走，得容忍中途改计划。
- **冷启动成本**：对简单任务也要先走一遍规划，过重。

### 适用场景

- 多步骤、有明确目标的任务（数据分析、报告生成、PR 实现）
- 需要可审计计划的工作流
- 步骤间存在并行可能的场景

---

## 三、Reflection：自我反思与修正

Reflection 不是独立的工作流，而是一种**增强机制**：让 Agent 在产出结果后，对自己的过程或输出进行评估（Reflection / Critique），并据此修订。

### 流程结构

```
执行 → 产出结果 → 反思（哪里不对/哪里可以更好） → 修订 → 再反思 → ...
```

典型实现：

- **Reflexion**（Shinn et al., 2023）：失败后把教训写进记忆，下一轮带上这些教训重试。
- **Self-Refine**：模型先输出草稿，再自己给草稿挑刺，迭代若干轮。

### 优点

- **提升质量**：在编程、推理等可验证任务上，迭代反思能显著抬升准确率。
- **可叠加**：能挂在 ReAct 或 Plan-and-Execute 外层作为增强。
- **可解释**：反思过程本身就是一种 trace。

### 缺点

- **依赖可验证性**：反思要靠谱，得有客观信号（测试用例、编译结果、对答案）；纯文本任务容易「自我感动」。
- **成本翻倍**：每轮反思都是一次完整推理。
- **可能陷入死循环**：反思不出新东西，或反复在两个错误版本间横跳。

### 适用场景

- 代码任务（有测试反馈）
- 数学/逻辑推理（有标准答案）
- 长任务收尾时的质量兜底

---

## 四、对比与组合

### 三者对比

| 维度 | ReAct | Plan-and-Execute | Reflection |
|------|-------|------------------|------------|
| 结构 | 单循环 | 规划+执行两段 | 评估+修订循环 |
| 全局性 | 弱 | 强 | 中 |
| 灵活性 | 强 | 中（需 re-plan） | 强 |
| Token 成本 | 中 | 高 | 高 |
| 适合任务 | 短、探索性 | 长、目标明确 | 需要质量兜底 |

### 常见组合

- **Plan-and-Execute + Reflection**：先规划，执行后反思是否达预期，未达则 re-plan。这是当下生产环境里相当稳的搭配。
- **ReAct + Reflection**：在 ReAct 循环里，每若干步插入一次反思，判断是否还走在正确方向。
- **三者叠满**：Planner 出计划 → Executor 用 ReAct 跑每一步 → 结束后 Reflection 复盘 → 触发 re-plan。能力上限高，但复杂度和成本也高。

---

## 五、怎么选

给个粗糙的决策路径：

1. 任务步骤数 ≤ 3、结果不可预知 → **ReAct**
2. 任务步骤多、目标明确、希望可审计 → **Plan-and-Execute**
3. 任务有可验证信号（测试、答案、编译） → **加一层 Reflection**
4. 都不确定 → 先上 ReAct 跑通，再加 Reflection，最后再考虑拆出 Planner

范式的价值不在于教条，而在于给「调工具的 LLM」提供一个可复用的结构。先有结构，再在结构上做工程优化（缓存、并行、截断、重试），才是 Agent 落地的关键。

---

## 参考

- ReAct: Synergizing Reasoning and Acting in Language Models (Yao et al., 2022)
- Plan-and-Execute Agents — LangChain Blog
- Reflexion: Language Agents with Verbal Reinforcement Learning (Shinn et al., 2023)
- Self-Refine: Iterative Refinement with Self-Feedback (Madaan et al., 2023)
