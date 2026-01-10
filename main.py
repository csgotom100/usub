import requests
import urllib.parse
import os

def main():
    # 获取当前脚本所在目录，确保路径绝对正确
    current_dir = os.path.dirname(os.path.abspath(__file__))
    source_path = os.path.join(current_dir, 'sources.txt')
    
    print(f"--- 诊断模式 ---")
    print(f"当前运行目录: {current_dir}")
    print(f"尝试读取文件: {source_path}")

    # 1. 检查并读取 sources.txt
    if not os.path.exists(source_path):
        print("❌ 错误: 没找到 sources.txt 文件！请确认它在仓库根目录。")
        # 列出当前目录所有文件，帮你排查
        print(f"当前目录下的文件列表: {os.listdir(current_dir)}")
        return
    
    with open(source_path, 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]
    
    if not urls:
        print("⚠️ 警告: sources.txt 是空的，或者里面没有以 http 开头的链接。")
        return

    print(f"✅ 成功读取到 {len(urls)} 个链接。")
    for idx, url in enumerate(urls):
        print(f"   链接 {idx+1}: {url[:30]}...")

    # 2. 准备转换
    combined_urls = "|".join(urls)
    encoded_urls = urllib.parse.quote(combined_urls)
    api_base = "http://127.0.0.1:25500/sub?"

    tasks = [
        ("config.yaml", "clash", "&emoji=true&udp=true"),
        ("sub_v2ray.txt", "v2ray", "&emoji=true&list=true")
    ]

    for filename, target, extra in tasks:
        try:
            print(f"--- 正在转换至 {target} ---")
            api_url = f"{api_base}target={target}&url={encoded_urls}{extra}"
            
            # SubConverter 可能会处理较慢，设置 60 秒超时
            r = requests.get(api_url, timeout=60)
            r.raise_for_status()
            
            with open(filename, "w", encoding="utf-8") as f:
                f.write(r.text)
            print(f"🎉 成功保存到 {filename} (文件大小: {len(r.text)} 字节)")
            
        except Exception as e:
            print(f"❌ 转换 {target} 时出错: {e}")

if __name__ == "__main__":
    main()
