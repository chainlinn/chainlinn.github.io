# rss/fetch_rss.py

import os
import feedparser
import json
from datetime import datetime, timezone
from typing import Dict, List, Tuple
import math

# --- 全局配置 ---
# RSS 源列表
RSS_FEEDS = {
    "V2EX技术专区": "https://www.v2ex.com/feed/tab/tech.xml",
    "V2EX酷工作": "https://www.v2ex.com/feed/tab/jobs.xml",
    "潮流周刊": "https://weekly.tw93.fun/rss.xml",
    "美团技术团队": "https://tech.meituan.com/feed/"
}

# 设置存储的文章总数上限
MAX_ENTRIES_LIMIT = 200

# 负载均衡策略配置
BALANCE_STRATEGIES = {
    "equal": "平均分配",
    "weighted": "按权重分配",
    "dynamic": "动态分配（基于活跃度）"
}

# RSS源权重配置（仅在weighted策略下生效）
RSS_WEIGHTS = {
    "V2EX技术专区": 3,    # 高权重：技术内容丰富
    "V2EX酷工作": 2,      # 中权重：工作机会相关
    "潮流周刊": 2,        # 中权重：周刊类内容
    "美团技术团队": 3     # 高权重：技术团队博客
}

def get_output_path():
    """计算并返回 friends_feed.json 的绝对路径"""
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

def calculate_equal_allocation(feed_count: int, total_limit: int) -> Dict[str, int]:
    """等量分配策略：每个RSS源分配相等的文章数量"""
    base_allocation = total_limit // feed_count
    remaining = total_limit % feed_count
    
    allocation = {}
    feeds = list(RSS_FEEDS.keys())
    
    for i, feed_name in enumerate(feeds):
        # 余数分配给前几个RSS源
        allocation[feed_name] = base_allocation + (1 if i < remaining else 0)
    
    return allocation

def calculate_weighted_allocation(total_limit: int) -> Dict[str, int]:
    """权重分配策略：根据预设权重分配文章数量"""
    total_weight = sum(RSS_WEIGHTS.values())
    allocation = {}
    
    allocated_total = 0
    feeds = list(RSS_FEEDS.keys())
    
    for i, feed_name in enumerate(feeds):
        if i == len(feeds) - 1:  # 最后一个RSS源获得剩余所有配额
            allocation[feed_name] = total_limit - allocated_total
        else:
            weight = RSS_WEIGHTS.get(feed_name, 1)
            allocated = int((weight / total_weight) * total_limit)
            allocation[feed_name] = allocated
            allocated_total += allocated
    
    return allocation

def calculate_dynamic_allocation(existing_entries: Dict[str, dict], total_limit: int) -> Dict[str, int]:
    """动态分配策略：基于RSS源的活跃度（近期文章数量）进行分配"""
    # 统计每个RSS源在历史数据中的文章数量
    feed_counts = {feed_name: 0 for feed_name in RSS_FEEDS.keys()}
    
    for entry in existing_entries.values():
        blog_name = entry.get("blog_name")
        if blog_name in feed_counts:
            feed_counts[blog_name] += 1
    
    # 如果没有历史数据，回退到等量分配
    total_existing = sum(feed_counts.values())
    if total_existing == 0:
        return calculate_equal_allocation(len(RSS_FEEDS), total_limit)
    
    # 基于活跃度计算分配比例
    allocation = {}
    allocated_total = 0
    feeds = list(RSS_FEEDS.keys())
    
    for i, feed_name in enumerate(feeds):
        if i == len(feeds) - 1:  # 最后一个RSS源获得剩余所有配额
            allocation[feed_name] = total_limit - allocated_total
        else:
            # 活跃度越高，分配越多，但设置最小值防止某些源被忽略
            ratio = max(feed_counts[feed_name] / total_existing, 0.1)  # 最少10%
            allocated = int(ratio * total_limit)
            allocation[feed_name] = allocated
            allocated_total += allocated
    
    return allocation

def get_allocation_strategy(existing_entries: Dict[str, dict], strategy: str = "dynamic") -> Dict[str, int]:
    """根据策略返回每个RSS源的文章配额"""
    feed_count = len(RSS_FEEDS)
    
    if strategy == "equal":
        return calculate_equal_allocation(feed_count, MAX_ENTRIES_LIMIT)
    elif strategy == "weighted":
        return calculate_weighted_allocation(MAX_ENTRIES_LIMIT)
    elif strategy == "dynamic":
        return calculate_dynamic_allocation(existing_entries, MAX_ENTRIES_LIMIT)
    else:
        print(f"未知策略 '{strategy}'，使用默认的动态分配策略")
        return calculate_dynamic_allocation(existing_entries, MAX_ENTRIES_LIMIT)

def fetch_feed_entries(blog_name: str, feed_url: str, max_entries: int) -> List[dict]:
    """抓取单个RSS源的文章，限制数量"""
    entries = []
    try:
        print(f"  处理中: {blog_name} (配额: {max_entries})")
        feed = feedparser.parse(feed_url)
        if feed.bozo:
            print(f"    -> 警告: '{blog_name}' RSS 源可能格式不正确。")
        
        # 按时间排序RSS条目，取最新的
        feed_entries = feed.entries
        if feed_entries:
            # 尝试按发布时间排序
            try:
                feed_entries.sort(key=lambda x: parse_date(
                    x.get("published", x.get("updated", ""))
                ), reverse=True)
            except:
                pass  # 如果排序失败，保持原顺序
        
        count = 0
        for entry in feed_entries:
            if count >= max_entries:
                break
                
            published_str = entry.get("published", entry.get("updated"))
            if not published_str:
                continue
            
            dt_object = parse_date(published_str)
            
            entries.append({
                "blog_name": blog_name,
                "title": entry.title,
                "link": entry.link,
                "published": dt_object.isoformat(),
                "summary": entry.get("summary", "")[:150]
            })
            count += 1
            
        print(f"    -> 成功抓取 {len(entries)} 篇文章")
        
    except Exception as e:
        print(f"    -> 错误: 抓取 '{blog_name}' 时发生错误: {e}")
    
    return entries

def main(strategy: str = "dynamic"):
    """
    主函数：使用负载均衡策略更新RSS数据
    
    Args:
        strategy: 分配策略 ("equal", "weighted", "dynamic")
    """
    output_path = get_output_path()
    
    # 步骤 1: 读取旧数据
    print("--- 1. 正在读取历史数据... ---")
    existing_entries = {}
    if os.path.exists(output_path):
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                old_data = json.load(f)
                # 使用文章链接作为 key，方便快速去重
                for entry in old_data:
                    existing_entries[entry['link']] = entry
            print(f"成功加载 {len(existing_entries)} 条历史文章。")
        except (json.JSONDecodeError, IOError) as e:
            print(f"警告: 读取或解析旧数据文件失败: {e}")
    
    # 步骤 2: 计算分配策略
    print(f"\n--- 2. 计算负载均衡分配 (策略: {BALANCE_STRATEGIES.get(strategy, strategy)}) ---")
    allocation = get_allocation_strategy(existing_entries, strategy)
    
    print("分配结果:")
    total_allocated = 0
    for feed_name, count in allocation.items():
        print(f"  {feed_name}: {count} 篇")
        total_allocated += count
    print(f"  总计: {total_allocated} 篇")
    
    # 步骤 3: 抓取新数据
    print(f"\n--- 3. 正在抓取RSS feeds... ---")
    all_new_entries = []
    
    for blog_name, feed_url in RSS_FEEDS.items():
        max_entries = allocation.get(blog_name, 0)
        if max_entries <= 0:
            continue
            
        feed_entries = fetch_feed_entries(blog_name, feed_url, max_entries)
        all_new_entries.extend(feed_entries)
    
    print(f"总共抓取到 {len(all_new_entries)} 篇文章。")
    
    # 步骤 4: 去重合并
    print("\n--- 4. 去重与合并... ---")
    final_entries = []
    existing_links = set(existing_entries.keys())
    
    new_count = 0
    for entry in all_new_entries:
        if entry['link'] not in existing_links:
            final_entries.append(entry)
            existing_links.add(entry['link'])
            new_count += 1
        # 如果已存在，跳过（保持负载均衡的同时避免重复）
    
    # 添加部分历史文章（保持总数在限制内）
    remaining_slots = MAX_ENTRIES_LIMIT - len(final_entries)
    if remaining_slots > 0:
        # 按时间排序历史文章，取最新的填充剩余槽位
        historical_entries = sorted(existing_entries.values(), 
                                  key=lambda x: x["published"], reverse=True)
        for entry in historical_entries:
            if len(final_entries) >= MAX_ENTRIES_LIMIT:
                break
            if entry['link'] not in existing_links:
                final_entries.append(entry)
    
    print(f"新增 {new_count} 篇文章，保留历史文章，最终共 {len(final_entries)} 篇。")
    
    # 步骤 5: 最终排序
    print("\n--- 5. 按时间排序... ---")
    final_entries.sort(key=lambda x: x["published"], reverse=True)
    
    # 确保不超过上限
    if len(final_entries) > MAX_ENTRIES_LIMIT:
        final_entries = final_entries[:MAX_ENTRIES_LIMIT]
        print(f"截取到上限 {MAX_ENTRIES_LIMIT} 篇文章。")
    
    # 步骤 6: 写入文件
    print("\n--- 6. 保存到文件... ---")
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(final_entries, f, ensure_ascii=False, indent=2)
        print(f"成功！{len(final_entries)} 篇文章已保存到: {output_path}")
        
        # 显示每个RSS源的最终文章数统计
        print("\n--- 最终统计 ---")
        feed_stats = {}
        for entry in final_entries:
            blog_name = entry.get("blog_name", "未知")
            feed_stats[blog_name] = feed_stats.get(blog_name, 0) + 1
        
        for feed_name, count in feed_stats.items():
            print(f"  {feed_name}: {count} 篇")
            
    except IOError as e:
        print(f"错误！无法写入文件: {e}")

if __name__ == "__main__":
    import sys
    
    # 支持命令行参数指定策略
    strategy = "dynamic"  # 默认策略
    if len(sys.argv) > 1 and sys.argv[1] in BALANCE_STRATEGIES:
        strategy = sys.argv[1]
    
    print(f"使用负载均衡策略: {BALANCE_STRATEGIES[strategy]}")
    print("=" * 60)
    
    main(strategy)