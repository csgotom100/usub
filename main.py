import requests
import os
import re
import base64
import urllib.parse

def main():
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]

    all_raw_data = []
    headers = {'User-Agent': 'clash-verge/1.0; Mozilla/5.0'}

    print(f"🚀 正在抓取并预处理源数据...")
    for idx, url in enumerate(urls):
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                # 不管它是什么格式，直接把整个内容做 Base64 编码
                # SubConverter 能够自动识别 Base64 里的 Clash、V2ray、SS 等各种格式
                encoded_part = base64.b64encode(r.content).decode('utf-8')
                all_raw_data.append(encoded_part)
                print(f"   [{idx+1}] ✅ 抓取并编码成功")
        except: continue

    if not all_raw_data:
        print("❌ 未抓取到任何数据")
        return

    # 将多个 Base64 块用管道符 | 拼接，这是 SubConverter 识别多订阅的官方方式
    # 虽然这是 Base64 字符串，但在 SubConverter 逻辑里，这相当于多个订阅源
    combined_data = "|".join(all_raw_data)
    
    print(f"📊 正在请求后端执行万能转换...")

    try:
        # 使用 data 协议：告诉 SubConverter 直接处理这段数据
        # 这种方式最稳，因为它强迫后端进入“混合解析”模式
        api_url = "http://127.0.0.1:25500/sub"
        
        # 1. 生成 Clash
        payload_clash = {
            "target": "clash",
            "data": combined_data,
            "emoji": "true",
            "udp": "true"
        }
        r_clash = requests.post(api_url, data=payload_clash, timeout=60)
        
        if "proxies:" in r_clash.text:
            with open("config.yaml", "w", encoding="utf-8") as f:
                f.write(r_clash.text)
            print(f"🎉 config.yaml 生成成功！大小: {len(r_clash.text)} 字节")
        else:
            print("❌ Clash 转换结果无效，后端输出预览：", r_clash.text[:100])

        # 2. 生成 V2Ray 列表
        payload_v2ray = payload_clash.copy()
        payload_v2ray["target"] = "v2ray"
        payload_v2ray["list"] = "true"
        r_v2ray = requests.post(api_url, data=payload_v2ray, timeout=60)
        
        if r_v2ray.status_code == 200:
            with open("sub_v2ray.txt", "w", encoding="utf-8") as f:
                f.write(r_v2ray.text)
            print("🎉 sub_v2ray.txt 生成成功")
            
    except Exception as e:
        print(f"❌ 运行出错: {e}")

if __name__ == "__main__":
    main()
