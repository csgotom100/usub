import requests
import urllib.parse
import os

def main():
    # 1. 检查 sources.txt
    if not os.path.exists('sources.txt'):
        print("Error: sources.txt not found")
        return
    
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]
    
    if not urls:
        print("No URLs found in sources.txt")
        return

    # 2. 准备链接：SubConverter 用 "|" 符号连接多个订阅源
    combined_urls = "|".join(urls)
    encoded_urls = urllib.parse.quote(combined_urls)
    
    # 指向 Actions 临时运行的本地后端
    api_base = "http://127.0.0.1:25500/sub?"

    # 3. 定义转换任务
    # (生成文件名, 转换目标类型, 额外参数)
    tasks = [
        ("config.yaml", "clash", "&emoji=true&udp=true"),
        ("sub_v2ray.txt", "v2ray", "&emoji=true&list=true") # list=true 获取明文链接列表
    ]

    for filename, target, extra in tasks:
        try:
            print(f"--- Converting to {target} ---")
            # 构造完整的 API 请求
            api_url = f"{api_base}target={target}&url={encoded_urls}{extra}"
            
            # 发起请求
            r = requests.get(api_url, timeout=60)
            r.raise_for_status()
            
            # 保存结果
            with open(filename, "w", encoding="utf-8") as f:
                f.write(r.text)
            print(f"Done! Saved to {filename}")
            
        except Exception as e:
            print(f"Error during {target} conversion: {e}")

if __name__ == "__main__":
    main()
