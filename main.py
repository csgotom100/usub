import requests
import os
import re
import base64

def get_raw_content(text):
    """
    如果下载的是网页，提取其中可能存在的节点信息。
    不管是 Base64 还是 YAML 格式，只要它是节点，就一定有特征。
    """
    # 1. 尝试寻找 Base64 订阅特征 (长串且无空格)
    b64_match = re.search(r'[A-Za-z0-9+/]{100,}', text)
    if b64_match:
        return b64_match.group(0)
    
    # 2. 尝试提取 Clash 格式 (寻找 proxies: 关键字)
    if "proxies:" in text:
        start_index = text.find("proxies:")
        return text[start_index:]
        
    return ""

def main():
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]

    all_raw_data = []
    print(f"🚀 正在深度清洗 {len(urls)} 个源...")
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    for idx, url in enumerate(urls):
        try:
            # 关键：手动下载并清洗 HTML
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                clean_data = get_raw_content(r.text)
                if clean_data:
                    all_raw_data.append(clean_data)
                    print(f"   [{idx+1}] ✅ 提取成功")
                else:
                    print(f"   [{idx+1}] ❌ 网页中未找到节点数据")
        except:
            continue

    if not all_raw_data:
        print("❌ 没有任何有效数据，请检查 sources.txt 里的链接是否有效。")
        return

    # 将清洗后的纯净数据存为临时文件
    with open("pure_nodes.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(all_raw_data))

    print(f"📦 正在进行本地格式转换...")
    
    try:
        # 使用本地 SubConverter 处理刚才生成的纯净文件
        # 我们用 POST data 方式发送，这是最稳的
        with open("pure_nodes.txt", "r", encoding="utf-8") as f:
            payload = f.read()

        # 1. 生成 Clash
        r_clash = requests.post("http://127.0.0.1:25500/sub", data={"target": "clash", "data": payload}, timeout=60)
        if "proxies:" in r_clash.text:
            with open("config.yaml", "w", encoding="utf-8") as f:
                f.write(r_clash.text)
            print("🎉 config.yaml 生成成功！")

        # 2. 生成 V2Ray
        r_v2ray = requests.post("http://127.0.0.1:25500/sub", data={"target": "v2ray", "data": payload, "list": "true"}, timeout=60)
        with open("sub_v2ray.txt", "w", encoding="utf-8") as f:
            f.write(r_v2ray.text)
        print("🎉 sub_v2ray.txt 生成成功！")
        
    except Exception as e:
        print(f"❌ 最终转换出错: {e}")
    finally:
        if os.path.exists("pure_nodes.txt"): os.remove("pure_nodes.txt")

if __name__ == "__main__":
    main()
