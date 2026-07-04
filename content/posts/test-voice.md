---
title: "评论引用测试"
date: 2026-07-05T00:00:00+08:00
draft: false
---

## 基础用法

{{< voice name="santu" handle="@santuchuan" date="2026-07-04" >}}
写了个音乐播放器，音频存在网盘，让浏览器直接播 FLAC。
{{< /voice >}}

## 短文本

{{< voice name="路人甲" >}}
这项目思路不错，学到了。
{{< /voice >}}

## 长文本

{{< voice name="santu" handle="@santuchuan" date="2026-07-04" >}}
逆向过程中遇到了几个坑。首先是 XOR 的分段逻辑——Python 源码里的 `xor()` 函数不是简单的逐字节异或，而是先取 `len & 0b11` 的残留字节单独处理，剩余按 key 长度分组，每组从 key[0] 重新开始。这和直觉上的循环异或完全不同，如果直接用 `i % keyLen` 循环会导致密钥偏移累积，整个加密结果出错。这个 bug 定位了整整一个下午。
{{< /voice >}}

## 内嵌代码

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
