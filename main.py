import requests
import os
import re

def fix_url(url):
    """自动将 GitLab 的浏览链接转换为 Raw 原始链接"""
    if "gitlab.com" in url and "/refs/heads/master/" in url:
        return url.replace("/refs/heads/master/", "/- /raw/master/")
    return url

def get_raw_content(text):
    # 1. 尝试寻找 Base64 特征
    b64_match = re.search(r'[A-Za-z0-9+/]{100,}', text)
    if b64_match: 
        return b64_match.group(0)
    
    # 2. 尝试寻找 Clash 特征 (修复了切片语法错误)
    if "proxies:" in text:
        start_idx = text.find("proxies:")
        return text[start_idx:]
    return ""

def main():
    if not os.path.exists('sources.txt'): 
        print("❌ 没找到 sources.txt")
        return
        
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [fix_url(l.strip()) for l in f if l.startswith('http')]

    all_raw_data = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    print(f"🚀 正在处理 {len(urls)} 个源...")

    for idx, url in enumerate(urls):
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                clean_data = get_raw_content(r.text)
                if clean_data:
                    all_raw_data.append(clean_data)
                    print(f"[{idx+1}] ✅ 提取成功")
                else:
                    print(f"[{idx+1}] ⚠️ 未找到有效节点数据")
            else:
                print(f"[{idx+1}] ❌ HTTP {r.status_code}")
        except Exception as e:
            print(f"[{idx+1}] ⚠️ 连接超时")
            continue

    if not all_raw_data:
        print("❌ 提取失败，所有源均无效")
        return

    # 合并所有提取到的原始数据
    payload = "\n".join(all_raw_data)

    try:
        # 生成 Clash (请求本地 SubConverter)
        r_clash = requests.post("http://127.0.0.1:25500/sub", data={"target": "clash", "data": payload}, timeout=60)
        if "proxies:" in r_clash.text:
            with open("config.yaml", "w", encoding="utf-8") as f:
                f.write(r_clash.text)
            print("🎉 config.yaml 生成成功")

        # 生成 V2Ray
        r_v2ray = requests.post("http://127.0.0.1:25500/sub", data={"target": "v2ray", "data": payload, "list": "true"}, timeout=60)
        if r_v2ray.status_code == 200:
            with open("sub_v2ray.txt", "w", encoding="utf-8") as f:
                f.write(r_v2ray.text)
            print("🎉 sub_v2ray.txt 生成成功")
    except Exception as e:
        print(f"❌ 转换过程出错: {e}")

if __name__ == "__main__":
    main()
