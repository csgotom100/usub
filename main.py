import requests
import urllib.parse
import os

def main():
    # 1. 读取 sources.txt 里的所有原始订阅链接
    if not os.path.exists('sources.txt'):
        print("Error: sources.txt not found")
        return
    
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.startswith('http')]
    
    if not urls:
        print("No URLs found.")
        return

    # 将多个链接用 "|" 拼接，这是 SubConverter 的标准要求
    combined_urls = "|".join(urls)
    encoded_urls = urllib.parse.quote(combined_urls)

    # 2. 定义转换参数
    # target=clash: 生成 Clash 配置
    # target=v2ray: 生成 v2rayN 用的通用链接
    base_api = "http://127.0.0.1:25500/sub?"
    
    # 转换任务列表：(文件名, 转换目标类型)
    tasks = [
        ("config.yaml", "clash"),
        ("sub_v2ray.txt", "v2ray")
    ]

    for filename, target in tasks:
        try:
            # 构造请求 URL
            # emoji=true: 保留国旗图标
            # list=true: 如果是 v2ray 目标，返回明文列表而非 base64
            api_url = f"{base_api}target={target}&url={encoded_urls}&emoji=true&list=true"
            
            print(f"Converting to {target}...")
            r = requests.get(api_url, timeout=30)
            r.raise_for_status()
            
            with open(filename, "w", encoding="utf-8") as f:
                f.write(r.text)
            print(f"Successfully saved {filename}")
            
        except Exception as e:
            print(f"Failed to convert {target}: {e}")

if __name__ == "__main__":
    main()
