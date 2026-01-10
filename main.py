import requests
import os
import re
import base64
import urllib.parse

def clean_text(text):
    if "<html" in text.lower():
        match = re.search(r'[A-Za-z0-9+/=]{50,}', text)
        return match.group(0) if match else ""
    return text

def main():
    if not os.path.exists('sources.txt'):
        print("❌ 没找到 sources.txt")
        return
    
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]
    
    all_raw_content = []
    print(f"🚀 开始下载 {len(urls)} 个源...")
    headers = {'User-Agent': 'clash-verge/1.0; Mozilla/5.0'}

    for idx, url in enumerate(urls):
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                content = clean_text(r.text.strip())
                if content:
                    all_raw_content.append(content)
                    print(f"   [{idx+1}] 下载成功")
        except:
            continue

    if not all_raw_content:
        print("❌ 没有任何有效内容")
        return

    final_links = set()
    print(f"📦 正在通过 API 提取节点 (共 {len(all_raw_content)} 段)...")
    
    for i, content in enumerate(all_raw_content):
        try:
            # 核心改进：将内容转为 Base64，利用 SubConverter 的 data 协议
            # 路径使用 /sub 而非 POST
            b64_data = base64.b64encode(content.encode('utf-8')).decode('utf-8')
            data_url = f"data:text/plain;base64,{b64_data}"
            
            # 使用 GET 请求，这是 SubConverter 最稳定的路径
            api_url = f"http://127.0.0.1:25500/sub?target=v2ray&url={urllib.parse.quote(data_url)}&list=true"
            
            r = requests.get(api_url, timeout=30)
            
            if r.status_code == 200:
                lines = r.text.splitlines()
                added = 0
                for line in lines:
                    if line.strip() and "://" in line: 
                        final_links.add(line.strip())
                        added += 1
                print(f"   进度: {i+1}/{len(all_raw_content)} 成功提取 {added} 个")
            else:
                print(f"   跳过第 {i+1} 段: HTTP {r.status_code} (尝试检查 API 路径)")
        except Exception as e:
            print(f"   第 {i+1} 段处理出错: {e}")

    links_list = list(final_links)
    print(f"✅ 汇总去重完成，共 {len(links_list)} 个唯一节点")

    if not links_list:
        return

    # 保存明文列表
    with open("sub_v2ray.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(links_list))

    # 生成最终 Clash
    print("🎨 正在生成最终 config.yaml...")
    try:
        final_b64 = base64.b64encode("\n".join(links_list).encode('utf-8')).decode('utf-8')
        final_data_url = f"data:text/plain;base64,{final_b64}"
        final_api = f"http://127.0.0.1:25500/sub?target=clash&url={urllib.parse.quote(final_data_url)}"
        
        r_clash = requests.get(final_api, timeout=60)
        if "proxies:" in r_clash.text:
            with open("config.yaml", "w", encoding="utf-8") as f:
                f.write(r_clash.text)
            print("🎉 全部完成！")
    except Exception as e:
        print(f"❌ 最终转换失败: {e}")

if __name__ == "__main__":
    main()
