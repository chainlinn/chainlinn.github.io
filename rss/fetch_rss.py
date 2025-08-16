# rss/fetch_rss.py

import os
import feedparser
import json
from datetime import datetime, timezone
from typing import Dict, List
import hashlib
import re
import sys
import socket
from concurrent.futures import ThreadPoolExecutor

# --- 新增依赖，请先安装: pip install requests beautifulsoup4 lxml bleach ---
import requests
from bs4 import BeautifulSoup
import bleach


# --- 1. 全局配置 ---

# -- 独立的大类配置 --
CATEGORIES = {
    "技术": {"icon": "💻", "color": "#4A90E2"},
    "工作": {"icon": "🏢", "color": "#50C878"},
    "资讯": {"icon": "🌐", "color": "#FF6B6B"}
}

# -- RSS 源（子类）配置 --
# 新增参数说明:
# fetch_full_content (bool): 是否需要二次抓取网页以获取全文。
#   - True:  适用于RSS只提供摘要，需要访问原文链接获取全文的网站。
#   - False: 适用于RSS本身就提供全文（如V2EX），或无法/不想抓取全文的情况。
# content_selector (str):  当 fetch_full_content 为 True 时，用于提取正文的CSS选择器。
#   - 这是最关键的配置，需要针对每个网站的HTML结构进行分析。
# sanitize_summary (bool): 是否对RSS源中的summary/description字段进行HTML净化，而不是粗暴移除标签。
#   - True:  保留摘要中的格式（加粗、链接、图片等），提升阅读体验。
RSS_FEEDS = {
    "美团技术团队": {
        "url": "https://tech.meituan.com/feed/",
        "category": "技术",
        "icon": "🚀",
        "color": "#FFD93D",
        "description": "美团技术团队博客",
        "fetch_full_content": True,
        "content_selector": "div.post-content", # 美团文章正文在<div class="post-content">中
        "sanitize_summary": False
    },
    "潮流周刊": {
        "url": "https://weekly.tw93.fun/rss.xml",
        "category": "资讯",
        "icon": "📰",
        "color": "#FCA5A5",
        "description": "前端潮流技术周刊",
        "fetch_full_content": False, # RSS内容已是全文
        "sanitize_summary": True # 需要净化HTML以保留格式
    },
    "V2EX技术专区": {
        "url": "https://www.v2ex.com/feed/tab/tech.xml",
        "category": "技术",
        "icon": "🔧",
        "color": "#A5B4FC",
        "description": "V2EX技术讨论区",
        "fetch_full_content": False, # V2EX的description就是帖子内容
        "sanitize_summary": True # 需要净化HTML来展示帖子内容
    },
    "V2EX酷工作": {
        "url": "https://www.v2ex.com/feed/tab/jobs.xml",
        "category": "工作",
        "icon": "💼",
        "color": "#A7F3D0",
        "description": "V2EX招聘信息",
        "fetch_full_content": False,
        "sanitize_summary": True
    }
}

# -- 其他设置 --
MAX_ENTRIES_LIMIT = 200
ENTRIES_PER_PAGE = 20
FETCH_CONCURRENCY = 5  # 并发抓取线程数
REQUEST_TIMEOUT = 15   # 网络请求超时时间（秒）

# 模拟普通 Windows 10 上 Chrome 浏览器的请求头
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    # --- 新增/修改的头 ---
    'Referer': 'https://tech.meituan.com/', # 伪造一个来源页
    'DNT': '1', # Do Not Track
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
}
BALANCE_STRATEGIES = {"equal": "平均分配", "weighted": "按权重分配", "dynamic": "动态分配（基于活跃度）"}
RSS_WEIGHTS = {"V2EX技术专区": 3, "美团技术团队": 3, "V2EX酷工作": 2, "潮流周刊": 2}


# --- 2. 辅助函数 ---

def get_output_path():
    """计算并返回JSON文件的绝对路径"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    data_dir = os.path.join(project_root, 'data')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    return os.path.join(data_dir, 'friends_feed.json')

def parse_date(date_string):
    """解析多种日期格式"""
    formats = [
        "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z",
    ]
    for fmt in formats:
        try:
            if ":" == date_string[-3:-2]: date_string = date_string[:-3] + date_string[-2:]
            return datetime.strptime(date_string, fmt)
        except ValueError:
            pass
    return datetime(1970, 1, 1, tzinfo=timezone.utc)

def generate_entry_id(link: str) -> str:
    """为文章生成唯一ID"""
    return hashlib.md5(link.encode()).hexdigest()[:12]

def sanitize_html(html_content: str) -> str:
    """使用bleach净化HTML，保留安全标签和格式"""
    allowed_tags = [
        'p', 'br', 'a', 'img', 'video', 'audio',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'strong', 'em', 'u', 's', 'b', 'i',
        'ul', 'ol', 'li', 'blockquote',
        'pre', 'code', 'figure', 'figcaption'
    ]
    allowed_attrs = {
        '*': ['class', 'style'],
        'a': ['href', 'title', 'target'],
        'img': ['src', 'alt', 'title', 'width', 'height', 'loading'],
        'video': ['src', 'controls', 'width', 'height'],
        'audio': ['src', 'controls'],
    }
    return bleach.clean(html_content, tags=allowed_tags, attributes=allowed_attrs, strip=True)

def fetch_full_content(url: str, selector: str) -> str:
    """抓取并解析网页，提取指定部分HTML"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        response.encoding = response.apparent_encoding # 自动检测编码
        soup = BeautifulSoup(response.text, 'lxml')
        content_element = soup.select_one(selector)
        if content_element:
            # 可以在这里做一些清理，例如移除不想关的子元素
            return str(content_element)
    except requests.exceptions.RequestException as e:
        print(f"    -> 抓取全文失败: {url}, 错误: {e}")
    except Exception as e:
        print(f"    -> 解析全文失败: {url}, 错误: {e}")
    return ""


# --- 3. 核心抓取与处理逻辑 ---

def fetch_and_process_feed(args) -> List[dict]:
    """抓取并处理单个RSS源（设计为可并发调用）"""
    blog_name, feed_config, max_entries = args
    entries = []
    feed_url = feed_config["url"]
    
    print(f"  处理中: {blog_name} (配额: {max_entries})")
    
    try:
        # 使用全局socket超时来控制feedparser的请求
        socket.setdefaulttimeout(REQUEST_TIMEOUT)
        feed = feedparser.parse(feed_url, agent=HEADERS.get('User-Agent'))
        
        if feed.bozo:
            bozo_exception = feed.get('bozo_exception', '未知错误')
            print(f"    -> 警告: '{blog_name}' RSS 源格式不正确。错误: {bozo_exception}")

        # 按发布日期排序
        feed_entries = sorted(feed.entries, key=lambda x: parse_date(x.get("published", x.get("updated", ""))), reverse=True)
        
        for entry in feed_entries[:max_entries]:
            published_str = entry.get("published", entry.get("updated"))
            if not published_str: continue
            
            dt_object = parse_date(published_str)
            summary_html = entry.get("summary", entry.get("description", ""))

            # --- 全文获取与内容处理 ---
            summary = ""
            content = ""

            # 1. 优先获取全文
            if feed_config.get("fetch_full_content") and feed_config.get("content_selector"):
                content_html = fetch_full_content(entry.link, feed_config["content_selector"])
                if content_html:
                    content = sanitize_html(content_html)
            
            # 2. 如果没有全文，或配置了净化摘要，则处理摘要
            if feed_config.get("sanitize_summary", False):
                summary = sanitize_html(summary_html)
            else:
                summary = re.sub(r'<[^>]+>', '', summary_html).strip()[:200]
            
            # 如果content为空，但净化后的summary不为空，则将summary作为content
            if not content and feed_config.get("sanitize_summary", False):
                content = summary

            # 提取作者和标签
            author = entry.get("author", "未知")
            tags = [tag.get('term') for tag in entry.get("tags", [])]
            
            entries.append({
                "id": generate_entry_id(entry.link),
                "blog_name": blog_name, "title": entry.title, "link": entry.link,
                "published": dt_object.isoformat(), "timestamp": int(dt_object.timestamp()),
                "summary": summary,
                "content": content, # << 新增完整内容字段
                "author": author,   # << 新增作者字段
                "tags": tags,       # << 新增标签字段
                "category": feed_config.get("category", "其他"),
                "source_icon": feed_config.get("icon", "📄"), "source_color": feed_config.get("color", "#666666")
            })
        print(f"    -> 成功处理 {len(entries)} 篇文章")
    except Exception as e:
        print(f"    -> 错误: 抓取或处理 '{blog_name}' 时发生严重错误: {e}")
    return entries


# --- 4. 分配策略函数 (与原版相同，为保持完整性而保留) ---

def calculate_equal_allocation(feed_count: int, total_limit: int) -> Dict[str, int]:
    if feed_count == 0: return {}
    base = total_limit // feed_count
    rem = total_limit % feed_count
    return {name: base + (1 if i < rem else 0) for i, name in enumerate(RSS_FEEDS.keys())}

def calculate_weighted_allocation(total_limit: int) -> Dict[str, int]:
    total_weight = sum(RSS_WEIGHTS.values())
    if total_weight == 0: return calculate_equal_allocation(len(RSS_FEEDS), total_limit)
    allocation = {name: int(total_limit * (RSS_WEIGHTS.get(name, 1) / total_weight)) for name in RSS_FEEDS.keys()}
    # 修正因取整导致的和不等于total_limit的问题
    current_total = sum(allocation.values())
    diff = total_limit - current_total
    for i in range(diff): allocation[list(RSS_FEEDS.keys())[i % len(RSS_FEEDS)]] += 1
    return allocation

def calculate_dynamic_allocation(existing_entries: List[dict], total_limit: int) -> Dict[str, int]:
    counts = {name: 0 for name in RSS_FEEDS.keys()}
    for entry in existing_entries:
        if entry.get("blog_name") in counts: counts[entry["blog_name"]] += 1
    total = sum(counts.values())
    if total == 0: return calculate_equal_allocation(len(RSS_FEEDS), total_limit)
    
    # 动态分配，基于历史文章比例，但保证每个源至少有1个配额
    ratios = {name: count / total for name, count in counts.items()}
    allocation = {name: max(1, int(ratio * total_limit)) for name, ratio in ratios.items()}
    
    # 修正总数
    current_total = sum(allocation.values())
    while current_total < total_limit:
        # 将剩余配额加到比例最高的源上
        max_ratio_feed = max(ratios, key=ratios.get)
        allocation[max_ratio_feed] += 1
        current_total += 1
    return allocation

def get_allocation_strategy(existing_entries: List[dict], strategy: str) -> Dict[str, int]:
    if strategy == "equal": return calculate_equal_allocation(len(RSS_FEEDS), MAX_ENTRIES_LIMIT)
    if strategy == "weighted": return calculate_weighted_allocation(MAX_ENTRIES_LIMIT)
    if strategy == "dynamic": return calculate_dynamic_allocation(existing_entries, MAX_ENTRIES_LIMIT)
    return calculate_dynamic_allocation(existing_entries, MAX_ENTRIES_LIMIT)


# --- 5. 主函数 ---

def main(strategy: str):
    output_path = get_output_path()
    
    # 步骤 1: 读取历史数据
    print("--- 1. 正在读取历史数据... ---")
    existing_entries = []
    if os.path.exists(output_path):
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                old_data = json.load(f)
                existing_entries = old_data.get('articles', [])
            print(f"成功加载 {len(existing_entries)} 条历史文章。")
        except (json.JSONDecodeError, IOError) as e:
            print(f"警告: 读取或解析旧数据文件失败: {e}")

    # 步骤 2: 计算分配策略
    print(f"\n--- 2. 计算负载均衡分配 (策略: {BALANCE_STRATEGIES.get(strategy, strategy)}) ---")
    allocation = get_allocation_strategy(existing_entries, strategy)
    print("分配结果:")
    for name, count in allocation.items(): print(f"  {name}: {count} 篇")
    
    # 步骤 3: 并发抓取新数据
    print(f"\n--- 3. 正在并发抓取RSS feeds (并发数: {FETCH_CONCURRENCY})... ---")
    all_new_entries = []
    tasks = [(name, config, allocation.get(name, 0)) for name, config in RSS_FEEDS.items() if allocation.get(name, 0) > 0]
    
    with ThreadPoolExecutor(max_workers=FETCH_CONCURRENCY) as executor:
        results = executor.map(fetch_and_process_feed, tasks)
        for result in results:
            all_new_entries.extend(result)
            
    print(f"抓取完成，共获得 {len(all_new_entries)} 篇文章。")
    
    # 步骤 4: 合并与去重
    print("\n--- 4. 去重与合并... ---")
    combined_entries = {e['link']: e for e in existing_entries}
    new_count = 0
    for entry in all_new_entries:
        if entry['link'] not in combined_entries:
            new_count += 1
        combined_entries[entry['link']] = entry

    # 排序并截断
    final_entries = sorted(combined_entries.values(), key=lambda x: x.get('timestamp', 0), reverse=True)[:MAX_ENTRIES_LIMIT]
    print(f"新增 {new_count} 篇文章，去重和截断后，最终共 {len(final_entries)} 篇。")
    
    # 步骤 5: 生成元数据 (与原版类似，但更健壮)
    categories_meta = {name: {"icon": conf.get("icon", "📁"), "color": conf.get("color", "#666"), "count": 0, "sources": {}}
                       for name, conf in CATEGORIES.items()}
    source_counts = {name: 0 for name in RSS_FEEDS.keys()}
    for entry in final_entries:
        if entry.get('blog_name') in source_counts:
            source_counts[entry['blog_name']] += 1
    
    for src_name, src_config in RSS_FEEDS.items():
        cat_name = src_config.get('category')
        if cat_name in categories_meta:
            count = source_counts.get(src_name, 0)
            categories_meta[cat_name]['sources'][src_name] = {
                "icon": src_config.get("icon", "📄"), "color": src_config.get("color", "#888"),
                "description": src_config.get("description", ""), "count": count
            }
            categories_meta[cat_name]['count'] += count

    # 构建最终输出数据
    output_data = {
        "meta": {
            "total_articles": len(final_entries), "last_updated": datetime.now(timezone.utc).isoformat(),
            "entries_per_page": ENTRIES_PER_PAGE, "categories": categories_meta
        },
        "articles": final_entries
    }
    
    # 步骤 6: 写入文件
    print("\n--- 5. 保存到文件... ---")
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"成功！数据已保存到: {output_path}")
        
        print("\n--- 最终统计 ---")
        for cat, info in categories_meta.items():
            if info['count'] > 0:
                print(f"  {info['icon']} {cat}: {info['count']} 篇")
                for src, s_info in info['sources'].items():
                    if s_info['count'] > 0:
                        print(f"    - {s_info['icon']} {src}: {s_info['count']} 篇")
    except IOError as e:
        print(f"错误！无法写入文件: {e}")

# --- 6. 脚本执行入口 ---

if __name__ == "__main__":
    strategy_arg = "dynamic"
    if len(sys.argv) > 1 and sys.argv[1] in BALANCE_STRATEGIES:
        strategy_arg = sys.argv[1]
    
    print(f"使用负载均衡策略: {BALANCE_STRATEGIES.get(strategy_arg, '未知')}")
    print("=" * 60)
    
    main(strategy_arg)