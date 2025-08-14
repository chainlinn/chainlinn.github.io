# rss/fetch_rss.py

import os
import feedparser
import json
from datetime import datetime, timezone

# --- 全局配置 ---
# RSS 源列表
RSS_FEEDS = {
    "V2EX": "https://www.v2ex.com/index.xml",
    "LINUX DO": "https://linux.do/latest.rss",
}
# 设置存储的文章总数上限
MAX_ENTRIES_LIMIT = 200

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

def main():
    """
    主函数：增量更新 RSS 数据并保持上限。
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
            
    # 步骤 2: 抓取新数据
    print("\n--- 2. 正在抓取新的 RSS feeds... ---")
    new_entries_count = 0
    for blog_name, feed_url in RSS_FEEDS.items():
        try:
            print(f"处理中: {blog_name}")
            feed = feedparser.parse(feed_url)
            if feed.bozo:
                print(f"  -> 警告: '{blog_name}' RSS 源可能格式不正确。")
            
            for entry in feed.entries: # 不再限制只取5篇，全部抓取
                # 步骤 3: 合并与去重
                if entry.link not in existing_entries:
                    published_str = entry.get("published", entry.get("updated"))
                    if not published_str:
                        continue
                    
                    dt_object = parse_date(published_str)
                    
                    # 将新文章添加到我们的数据集中
                    existing_entries[entry.link] = {
                        "blog_name": blog_name, "title": entry.title,
                        "link": entry.link, "published": dt_object.isoformat(),
                        "summary": entry.get("summary", "")[:150]
                    }
                    new_entries_count += 1
        except Exception as e:
            print(f"  -> 错误: 抓取 '{blog_name}' 时发生错误: {e}")

    print(f"抓取到 {new_entries_count} 篇新文章。")
    
    # 将字典的值转换回列表
    all_entries = list(existing_entries.values())
    
    # 步骤 4: 排序
    print("\n--- 3. 正在排序所有文章... ---")
    all_entries.sort(key=lambda x: x["published"], reverse=True)
    
    # 步骤 5: 截断与清理
    print(f"当前共有 {len(all_entries)} 篇文章，上限为 {MAX_ENTRIES_LIMIT}。")
    if len(all_entries) > MAX_ENTRIES_LIMIT:
        print(f"文章数量超出上限，将截取最新的 {MAX_ENTRIES_LIMIT} 篇。")
        final_entries = all_entries[:MAX_ENTRIES_LIMIT]
    else:
        final_entries = all_entries
        
    # 步骤 6: 写入新数据
    print("\n--- 4. 正在将最终数据写入文件... ---")
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(final_entries, f, ensure_ascii=False, indent=2)
        print(f"成功！{len(final_entries)} 篇文章已保存到: {output_path}")
    except IOError as e:
        print(f"错误！无法写入文件: {e}")

if __name__ == "__main__":
    main()