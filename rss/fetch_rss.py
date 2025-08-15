# rss/fetch_rss.py

import os
import feedparser
import json
from datetime import datetime, timezone
from typing import Dict, List
import hashlib
import re
import sys

# --- 1. 全局配置 ---

# -- 独立的大类配置 --
# 定义每个父类自己的属性，如通用的图标和颜色。
CATEGORIES = {
    "技术": {
        "icon": "💻",  # 代表“技术”大类的通用图标
        "color": "#4A90E2"
    },
    "工作": {
        "icon": "🏢",
        "color": "#50C878"
    },
    "资讯": {
        "icon": "🌐",
        "color": "#FF6B6B"
    }
}

# -- RSS 源（子类）配置 --
# 'category' 字段关联到上面的 CATEGORIES。
# 'icon' 字段是每个 RSS 源自己独特的图标。
RSS_FEEDS = {
    "V2EX技术专区": {
        "url": "https://www.v2ex.com/feed/tab/tech.xml",
        "category": "技术", # 关联到 CATEGORIES["技术"]
        "icon": "🔧",     # 源本身的图标
        "color": "#A5B4FC", # 可以为子类定义不同的颜色
        "description": "V2EX技术讨论区"
    },
    "美团技术团队": {
        "url": "https://tech.meituan.com/feed/",
        "category": "技术", # 关联到 CATEGORIES["技术"]
        "icon": "🚀",     # 源本身的图标
        "color": "#FFD93D",
        "description": "美团技术团队博客"
    },
    "V2EX酷工作": {
        "url": "https://www.v2ex.com/feed/tab/jobs.xml",
        "category": "工作",
        "icon": "💼",
        "color": "#A7F3D0",
        "description": "V2EX招聘信息"
    },
    "潮流周刊": {
        "url": "https://weekly.tw93.fun/rss.xml",
        "category": "资讯",
        "icon": "📰",
        "color": "#FCA5A5",
        "description": "前端潮流技术周刊"
    }
}

# -- 其他设置 --
MAX_ENTRIES_LIMIT = 200
ENTRIES_PER_PAGE = 20
BALANCE_STRATEGIES = {
    "equal": "平均分配",
    "weighted": "按权重分配",
    "dynamic": "动态分配（基于活跃度）"
}
RSS_WEIGHTS = {
    "V2EX技术专区": 3,
    "美团技术团队": 3,
    "V2EX酷工作": 2,
    "潮流周刊": 2
}


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
            if ":" == date_string[-3:-2]:
                date_string = date_string[:-3] + date_string[-2:]
            return datetime.strptime(date_string, fmt)
        except ValueError:
            pass
    print(f"警告：无法解析日期 '{date_string}'")
    return datetime(1970, 1, 1, tzinfo=timezone.utc)

def generate_entry_id(link: str) -> str:
    """为文章生成唯一ID"""
    return hashlib.md5(link.encode()).hexdigest()[:12]

def calculate_equal_allocation(feed_count: int, total_limit: int) -> Dict[str, int]:
    """等量分配策略"""
    if feed_count == 0: return {}
    base_allocation = total_limit // feed_count
    remaining = total_limit % feed_count
    allocation = {}
    feeds = list(RSS_FEEDS.keys())
    for i, feed_name in enumerate(feeds):
        allocation[feed_name] = base_allocation + (1 if i < remaining else 0)
    return allocation

def calculate_weighted_allocation(total_limit: int) -> Dict[str, int]:
    """权重分配策略"""
    total_weight = sum(RSS_WEIGHTS.values())
    if total_weight == 0: return {feed: 0 for feed in RSS_FEEDS.keys()}
    allocation = {}
    allocated_total = 0
    feeds = list(RSS_FEEDS.keys())
    for i, feed_name in enumerate(feeds):
        if i == len(feeds) - 1:
            allocation[feed_name] = total_limit - allocated_total
        else:
            weight = RSS_WEIGHTS.get(feed_name, 1)
            allocated = int((weight / total_weight) * total_limit)
            allocation[feed_name] = allocated
            allocated_total += allocated
    return allocation

def calculate_dynamic_allocation(existing_entries: List[dict], total_limit: int) -> Dict[str, int]:
    """动态分配策略"""
    feed_counts = {feed_name: 0 for feed_name in RSS_FEEDS.keys()}
    for entry in existing_entries:
        blog_name = entry.get("blog_name")
        if blog_name in feed_counts:
            feed_counts[blog_name] += 1
    total_existing = sum(feed_counts.values())
    if total_existing == 0:
        return calculate_equal_allocation(len(RSS_FEEDS), total_limit)
    allocation = {}
    allocated_total = 0
    feeds = list(RSS_FEEDS.keys())
    for i, feed_name in enumerate(feeds):
        if i == len(feeds) - 1:
            allocation[feed_name] = total_limit - allocated_total
        else:
            ratio = max(feed_counts[feed_name] / total_existing, 0.1) # 保证最低比例
            allocated = int(ratio * total_limit)
            allocation[feed_name] = allocated
            allocated_total += allocated
    return allocation

def get_allocation_strategy(existing_entries: List[dict], strategy: str) -> Dict[str, int]:
    """根据策略返回每个RSS源的文章配额"""
    if strategy == "equal":
        return calculate_equal_allocation(len(RSS_FEEDS), MAX_ENTRIES_LIMIT)
    elif strategy == "weighted":
        return calculate_weighted_allocation(MAX_ENTRIES_LIMIT)
    elif strategy == "dynamic":
        return calculate_dynamic_allocation(existing_entries, MAX_ENTRIES_LIMIT)
    else:
        print(f"未知策略 '{strategy}'，使用默认的动态分配策略")
        return calculate_dynamic_allocation(existing_entries, MAX_ENTRIES_LIMIT)

def fetch_feed_entries(blog_name: str, feed_config: dict, max_entries: int) -> List[dict]:
    """抓取单个RSS源的文章"""
    entries = []
    feed_url = feed_config["url"]
    try:
        print(f"  处理中: {blog_name} (配额: {max_entries})")
        feed = feedparser.parse(feed_url)
        if feed.bozo:
            print(f"    -> 警告: '{blog_name}' RSS 源可能格式不正确。")
        
        feed_entries = sorted(feed.entries, key=lambda x: parse_date(x.get("published", x.get("updated", ""))), reverse=True)
        
        for entry in feed_entries[:max_entries]:
            published_str = entry.get("published", entry.get("updated"))
            if not published_str: continue
            
            dt_object = parse_date(published_str)
            summary = re.sub(r'<[^>]+>', '', entry.get("summary", "")).strip()[:200]
            
            entries.append({
                "id": generate_entry_id(entry.link),
                "blog_name": blog_name, "title": entry.title, "link": entry.link,
                "published": dt_object.isoformat(), "timestamp": int(dt_object.timestamp()),
                "summary": summary, "category": feed_config.get("category", "其他"),
                "source_icon": feed_config.get("icon", "📄"), "source_color": feed_config.get("color", "#666666")
            })
        print(f"    -> 成功抓取 {len(entries)} 篇文章")
    except Exception as e:
        print(f"    -> 错误: 抓取 '{blog_name}' 时发生错误: {e}")
    return entries

# --- 3. 主函数 ---

def main(strategy: str):
    output_path = get_output_path()
    
    # 步骤 1: 读取历史数据
    print("--- 1. 正在读取历史数据... ---")
    existing_entries, existing_links = [], set()
    if os.path.exists(output_path):
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                old_data = json.load(f)
                existing_entries = old_data.get('articles', [])
                existing_links = {e.get('link') for e in existing_entries if e.get('link')}
            print(f"成功加载 {len(existing_entries)} 条历史文章。")
        except (json.JSONDecodeError, IOError) as e:
            print(f"警告: 读取或解析旧数据文件失败: {e}")

    # 步骤 2: 计算分配策略
    print(f"\n--- 2. 计算负载均衡分配 (策略: {BALANCE_STRATEGIES.get(strategy, strategy)}) ---")
    allocation = get_allocation_strategy(existing_entries, strategy)
    print("分配结果:")
    for name, count in allocation.items(): print(f"  {name}: {count} 篇")
    
    # 步骤 3: 抓取新数据
    print(f"\n--- 3. 正在抓取RSS feeds... ---")
    all_new_entries = []
    for name, config in RSS_FEEDS.items():
        if allocation.get(name, 0) > 0:
            all_new_entries.extend(fetch_feed_entries(name, config, allocation[name]))
    print(f"总共抓取到 {len(all_new_entries)} 篇文章。")
    
    # 步骤 4: 合并与去重
    print("\n--- 4. 去重与合并... ---")
    combined_entries = {e['link']: e for e in existing_entries}
    new_count = 0
    for entry in all_new_entries:
        if entry['link'] not in combined_entries:
            new_count += 1
        combined_entries[entry['link']] = entry

    # 排序并截断
    final_entries = sorted(combined_entries.values(), key=lambda x: x.get('timestamp', 0), reverse=True)
    final_entries = final_entries[:MAX_ENTRIES_LIMIT]
    print(f"新增 {new_count} 篇文章，最终共 {len(final_entries)} 篇。")
    
    # 步骤 5: 生成元数据
    # 1. 直接从独立的 CATEGORIES 配置初始化父类结构
    categories_meta = {}
    for cat_name, cat_config in CATEGORIES.items():
        categories_meta[cat_name] = {
            "icon": cat_config.get("icon", "📁"), "color": cat_config.get("color", "#666666"),
            "count": 0, "sources": {}
        }
    
    # 2. 计算每个 RSS 源的文章数量
    source_counts = {name: 0 for name in RSS_FEEDS.keys()}
    for entry in final_entries:
        if entry.get('blog_name') in source_counts:
            source_counts[entry['blog_name']] += 1
    
    # 3. 将 RSS 源信息填充到对应的父类下
    for source_name, source_config in RSS_FEEDS.items():
        category_name = source_config.get('category')
        if category_name in categories_meta:
            categories_meta[category_name]['sources'][source_name] = {
                "icon": source_config.get("icon", "📄"), "color": source_config.get("color", "#888888"),
                "description": source_config.get("description", ""), "count": source_counts.get(source_name, 0)
            }
            categories_meta[category_name]['count'] += source_counts.get(source_name, 0)

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
        print(f"成功！{len(final_entries)} 篇文章已保存到: {output_path}")
        
        print("\n--- 最终统计 ---")
        for cat, info in categories_meta.items():
            if info['count'] > 0:
                print(f"  {info['icon']} {cat}: {info['count']} 篇")
                for src, s_info in info['sources'].items():
                    if s_info['count'] > 0:
                        print(f"    - {s_info['icon']} {src}: {s_info['count']} 篇")
            
    except IOError as e:
        print(f"错误！无法写入文件: {e}")

# --- 4. 脚本执行入口 ---

if __name__ == "__main__":
    strategy_arg = "dynamic"
    if len(sys.argv) > 1 and sys.argv[1] in BALANCE_STRATEGIES:
        strategy_arg = sys.argv[1]
    
    print(f"使用负载均衡策略: {BALANCE_STRATEGIES.get(strategy_arg, '未知')}")
    print("=" * 60)
    
    main(strategy_arg)