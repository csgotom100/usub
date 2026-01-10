import requests
import os
import re
import base64

def get_raw_content(text):
    # 尝试寻找 Base64 特征
    b64_match = re.search(r'[A-Za-z0-9+/]{100,}', text)
    if b64_match: 
        return b64_match.group(0)
    
    # 尝试寻找 Clash 特征
    if "proxies:" in text:
        start_idx = text.find("proxies:")
        return text[start_idx:]
    return ""

def main():
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]

    all_raw_data = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    print(f"🚀 正在提取节点...")
    for idx, url in enumerate(urls):
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                clean_data = get_raw_content(r.text)
                if clean_data:
                    all_raw_data.append(clean_data)
                    print(f"   [{idx+1}] ✅ 提取成功")
        except: continue

    if not all_raw_data:
        print("❌ 没有任何原始数据被提取到！")
        return

    # --- 诊断：查看合并后的内容 ---
    # 我们把所有提取出的块再次用换行连接
    combined_payload = "\n".join(all_raw_data)
    print(f"📊 合并完成，预览数据前100位: {combined_payload[:100]}...")

    try:
        # 使用 POST 转换，显式告诉 SubConverter 我们传的是本地数据
        # 加上 target=clash 以及关键参数
        print("📦 正在请求后端渲染 config.yaml...")
        
        # 构造 POST 参数
        # url 指定为一个占位符，data 字段传实际内容
        params = {
            "target": "clash",
            "data": combined_payload,
            "emoji": "true",
            "list": "false"
        }
        
        r_clash = requests.post("http://127.0.0.1:25500/sub", data=params, timeout=60)
        
        if "proxies:" in r_clash.text:
            with open("config.yaml", "w", encoding="utf-8") as f:
                f.write(r_clash.text)
            print(f"🎉 config.yaml 生成成功！内容长度: {len(r_clash.text)}")
        else:
            print("❌ 后端返回的内容中没有 proxies 关键字，转换可能失败了。")
            print(f"后端返回预览: {r_clash.text[:200]}")

        # 生成 V2Ray
        params["target"] = "v2ray"
        params["list"] = "true"
        r_v2ray = requests.post("http://127.0.0.1:25500/sub", data=params, timeout=60)
        if r_v2ray.status_code == 200:
            with open("sub_v2ray.txt", "w", encoding="utf-8") as f:
                f.write(r_v2ray.text)
            print("🎉 sub_v2ray.txt 生成成功")
            
    except Exception as e:
        print(f"❌ 转换过程崩溃: {e}")

if __name__ == "__main__":
    main()
