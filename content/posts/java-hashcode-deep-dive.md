---
title: "掰开 JDK 源码：hashCode 到底是个什么东西"
date: 2026-07-28T20:00:00+08:00
draft: false
tags: ["Java", "源码", "HashMap", "基础"]
series: ["Java 源码深挖"]
aiCoAuthor: true
summary: "从 Object.hashCode 的 native 声明，到 HashMap 的两步走定位，再到 String 的 31 进制多项式哈希——带源码逐行拆解 hashCode 的本质、用途，以及它和 equals 为什么必须一起重写。"
---

> 本文由 AI 辅助整理自对 JDK 17 源码的逐行阅读。所有引用的源码均来自 `java.base` 模块，行号为 OpenJDK 17.0.19。

很多人能背出 `hashCode` 的三条契约，但说不清它到底为什么存在、除了 HashMap 还有没有别的用场。与其反复念经，不如直接把 JDK 源码翻出来看一遍。结论先行：**`hashCode` 的唯一用途就是为哈希表提供「对象 → 整数」的映射，支撑 O(1) 的桶定位。** 下面用源码证明这件事。

---

## 一、Object.hashCode：一个 native 方法

打开 `java/lang/Object.java`，定位到第 102 行：

```java
// Object.java:101-102
@IntrinsicCandidate
public native int hashCode();
```

两个关键字值得停下来看一眼：

- `native` —— 这个方法**没有 Java 实现**，方法体在 JVM 的 C++ 代码里（HotSpot 中是 `ObjectSynchronizer::FastHashCode`，最终走到 `get_next_hash`，默认基于对象内存地址做随机化扰动）。Java 层面只能看到声明。
- `@IntrinsicCandidate` —— 标记它可能被 JVM 内联为硬件指令级别的优化（HotSpot 会把它编译成一条地址读取相关的指令）。

再看它头上的注释，**第一句话就把用途定死了**：

```java
// Object.java:69-71
/**
 * Returns a hash code value for the object. This method is
 * supported for the benefit of hash tables such as those provided
 * by {@link java.util.HashMap}.
 */
```

> 这个方法是为哈希表（如 `java.util.HashMap`）服务的。

官方原话，没给第二种用途留口子。紧接着注释列出了三条契约：

```java
// Object.java:73-91 契约原文
// 1. 一致性：同一对象多次调用，只要 equals 字段没变，返回值必须相同
// 2. equals 相等 ⇒ hashCode 必须相等
// 3. equals 不相等 ⇒ hashCode 不要求不同（允许冲突，但冲突少则性能好）
```

第 2 条是铁律，第 3 条是建议——这三条共同保证了哈希表能正确且高效地工作，后面讲 `equals` 关系时还会回到这里。

---

## 二、HashMap 怎么用 hashCode：两步走

光看定义还不够，得看调用方。整个 JDK 标准库里，`hashCode()` 的调用方就是 `HashMap`/`HashSet`/`Hashtable`/`ConcurrentHashMap` 这一组哈希表结构，别无分号。`HashMap` 是其中最典型的样本。

`HashMap` 内部是一个 `Node[]` 数组，存一个 key 要先算出落在哪个下标。入口是静态方法 `hash()`：

```java
// HashMap.java:336-339
static final int hash(Object key) {
    int h;
    return (key == null) ? 0 : (h = key.hashCode()) ^ (h >>> 16);
}
```

干了两件事：

1. 调 `key.hashCode()` 拿到原始哈希值；
2. `h ^ (h >>> 16)` —— 把高 16 位异或到低 16 位。

**为什么要做这个扰动？** 因为哈希表长度永远是 2 的幂，取下标用的是位掩码 `hash & (n-1)`，只用到哈希值的低位。如果某些 key 的哈希值只在高位有差异，低位全相同，就会全部挤进同一个桶（冲突）。注释里举的例子是 `Float` 键存连续整数——所以先 XOR 把高位的影响「压」到低位，让高位信息也参与下标计算。

注意这个扰动改变的是「哈希值怎么被用」，不改变 `hashCode` 本身的职责。它只是 `HashMap` 的工程优化。

定位到桶之后，还要在桶里逐个比对找到真正相等的 key——这一步用的是 `equals`。看 `getNode` 的完整路径：

```java
// HashMap.java:565-583
final Node<K,V> getNode(Object key) {
    Node<K,V>[] tab; Node<K,V> first, e; int n, hash; K k;
    if ((tab = table) != null && (n = tab.length) > 0 &&
        (first = tab[(n - 1) & (hash = hash(key))]) != null) {   // ① 用 hashCode 定位桶
        if (first.hash == hash &&
            ((k = first.key) == key || (key != null && key.equals(k))))  // ② 用 equals 确认
            return first;
        if ((e = first.next) != null) {
            if (first instanceof TreeNode)
                return ((TreeNode<K,V>)first).getTreeNode(hash, key);
            do {
                if (e.hash == hash &&
                    ((k = e.key) == key || (key != null && key.equals(k))))  // ② 同上
                    return e;
            } while ((e = e.next) != null);
        }
    }
    return null;
}
```

这就是 `hashCode` 和 `equals` 的分工，一清二楚：

| 步骤 | 方法 | 作用 | 粒度 |
|------|------|------|------|
| ① 定位桶 | `hashCode` | `tab[(n-1) & hash]` 算出数组下标 | **粗筛**，可能多个对象落同桶 |
| ② 确认身份 | `equals` | 桶里逐个比对，确定是不是同一个 key | **精筛**，完全相等 |

`hashCode` 负责「去哪儿找」，`equals` 负责「是不是它」。一个定位，一个比对，缺一不可。**这就是 `hashCode` 的全部用途**——把 O(n) 的线性查找变成 O(1) 的直接定位。

---

## 三、equals 和 hashCode 为什么必须一起重写

承接上面的两步走，就明白为什么 `Object.equals` 的 `@apiNote` 会写这么一句警告：

```java
// Object.java:150-154
@apiNote
It is generally necessary to override the {@link hashCode hashCode}
method whenever this method is overridden, so as to maintain the
general contract for the {@code hashCode} method, which states that
equal objects must have equal hash codes.
```

契约就一条铁律：**`a.equals(b)` 为 true ⇒ `a.hashCode() == b.hashCode()` 必须成立。** 这条是上面「两步走」能正确运转的前提。破坏它，`HashMap` 直接出错。看两种典型翻车：

### 翻车 1：只重写 equals，没重写 hashCode

```java
Person p1 = new Person("Alice", 20);
Person p2 = new Person("Alice", 20);
p1.equals(p2);  // true，逻辑上是同一个人

Map<Person, String> map = new HashMap<>();
map.put(p1, "A");
map.get(p2);    // 返回 null！应该是 "A"
```

**源码层面发生了什么：** `p1`、`p2` 是两个不同对象，`Object` 默认的 `hashCode` 基于内存地址，所以 `p1.hashCode() != p2.hashCode()`。`put(p1)` 时算出下标放进桶 X，`get(p2)` 时算出**另一个**下标去桶 Y 找——第 ① 步就被筛掉了，`equals` 连执行的机会都没有。结果：明明相等的两个 key，`HashMap` 当成两个。

### 翻车 2：只重写 hashCode，没重写 equals

`equals` 还是 `Object` 默认的 `this == obj`（引用相等）。逻辑上相等的两个对象哈希相同→落同一个桶，但 `equals` 永远 false→第 ② 步确认失败→`HashMap` 认为是两个不同 key，桶里堆成一串。同一个「逻辑 key」被存多份，`get` 还是取不到。

### 本质

`equals` 定义了「什么算相等」，`hashCode` 必须和这个定义保持一致——相等的对象必须映射到同一个桶。两者描述的是**同一套相等逻辑的两个侧面**：`equals` 是完整判断，`hashCode` 是它的一个「摘要」。摘要可以冲突（多对一），但绝不能把相等的对象分到不同摘要里。所以重写了一个，另一个必须跟着改，否则 `HashMap` 的两步走就断了链。

---

## 四、String.hashCode：31 进制多项式哈希

`Object` 的 `hashCode` 是 native，看不到实现；但 `String` 的 `hashCode` 是纯 Java，而且是 JDK 里最经典的一份哈希实现。`java/lang/String.java` 第 2333 行：

```java
// String.java:2320-2353
/**
 * Returns a hash code for this string. The hash code for a
 * {@code String} object is computed as
 * s[0]*31^(n-1) + s[1]*31^(n-2) + ... + s[n-1]
 * using {@code int} arithmetic, where {@code s[i]} is the
 * i-th character of the string, and {@code n} is the length.
 * (The hash value of the empty string is zero.)
 */
public int hashCode() {
    // The hash or hashIsZero fields are subject to a benign data race ...
    int h = hash;
    if (h == 0 && !hashIsZero) {
        h = isLatin1() ? StringLatin1.hashCode(value)
                       : StringUTF16.hashCode(value);
        if (h == 0) {
            hashIsZero = true;
        } else {
            hash = h;
        }
    }
    return h;
}
```

第 2344 行分两条路：`StringLatin1.hashCode` 和 `StringUTF16.hashCode`。两个实现算法完全一样，只是取字符的方式不同。

### 4.1 核心算法：4 行代码

`StringLatin1.hashCode`（第 194-200 行）就 4 行核心：

```java
// StringLatin1.java:194-200
public static int hashCode(byte[] value) {
    int h = 0;
    for (byte v : value) {
        h = 31 * h + (v & 0xff);
    }
    return h;
}
```

展开就是注释里的公式：

```
s[0]*31^(n-1) + s[1]*31^(n-2) + ... + s[n-1]
```

本质是把字符串当成一个 **31 进制的数**来算它的「数值」。每来一个字符，旧的哈希左移一位（×31）再补上新字符。这样每个字符的位置都会影响最终结果——交换任意两个字符，哈希必然不同。

UTF16 版本只是把 `value.length >> 1`（字节数/2 = 字符数）算出长度，用 `getChar(value, i)` 取双字节字符：

```java
// StringUTF16.java:414-421
public static int hashCode(byte[] value) {
    int h = 0;
    int length = value.length >> 1;
    for (int i = 0; i < length; i++) {
        h = 31 * h + getChar(value, i);
    }
    return h;
}
```

两条路算法一致，所以同一个字符串无论走 Latin1 还是 UTF16 编码路径，`hashCode` 结果相同——这是保证一致性的关键。

### 4.2 为什么是 31？

这是整个实现里最被追问的点：

- **奇质数**：质数能让分布更均匀，奇数保证 `31*h` 不会丢失低位信息（偶数乘法末位必为 0，丢信息）。
- **可被优化成位移**：`31 * h` JVM 会优化成 `(h << 5) - h`，即 `32h - h`，比乘法快。
- **不大不小**：太小（如 1、2）冲突高，字符差异传播不开；太大（如 101）算长字符串容易溢出成 0，反而冲突。31 是经验上分布和性能的甜点。

这是 JDK 早期就定下来的选择，沿用至今。

### 4.3 惰性缓存与 hashIsZero 标志位

```java
// String.java:2342-2352
int h = hash;                       // 先读缓存
if (h == 0 && !hashIsZero) {        // 没算过才算
    h = isLatin1() ? ... : ...;
    if (h == 0) {
        hashIsZero = true;          // 哈希恰好为0，单独标记
    } else {
        hash = h;                   // 缓存
    }
}
return h;
```

两个亮点：

- **惰性求值**：`String` 不可变，哈希算一次就永远不会变，所以第一次调用才算，之后直接返回缓存。这对 `HashMap` 里大量用 `String` 作 key 的场景是巨大优化——不用每次 `get`/`put` 都重算。
- **`hashIsZero` 标志位**（JDK 13 加入）：`hash` 字段默认值是 0，如果某个字符串算出来哈希正好是 0（比如空串，或某些凑巧的字符串），光看 `hash == 0` 分不清「没算过」还是「算出来就是 0」。加个布尔标志区分这两种情况，避免每次都重算。

注释（2334-2341 行）还提到这是**良性数据竞争**——多线程下 `hash` 字段无锁读写是安全的，因为 `String` 不可变、计算幂等、对同一实例只会写入 `hash` 和 `hashIsZero` 中的一个。最坏情况多算几次，结果不会错。

---

## 五、收束

把源码串起来，`hashCode` 的全貌就清楚了：

1. **定义**：`Object.hashCode()` 是 native 方法，委托给 JVM，注释明说「为哈希表服务」。
2. **调用**：`HashMap.hash()` 是唯一入口，调一次 `hashCode()` 拿原始值，再 XOR 高位做扰动减少冲突。
3. **协作**：`getNode()` 里 `hashCode` 定位桶（粗筛）、`equals` 确认身份（精筛）——两步走缺一不可，所以重写 `equals` 必须同时重写 `hashCode`，否则相等的对象被分到不同桶，`HashMap` 失效。
4. **最佳样本**：`String.hashCode` = 31 进制多项式哈希 + 惰性缓存 + 零值标志位，4 行核心算法配一堆工程优化，是「为什么 String 适合做 HashMap key」的直接答案。

一句话：**`hashCode` 就是对象的数字指纹，唯一用途是让哈希表能 O(1) 地找到它。** 没有这个需求，你完全不需要写 `hashCode`。
