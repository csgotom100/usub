import requests
import urllib.parse
import os
import time

def main():
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = list(set([l.strip() for l in f if l.startswith('http')]))
    
    if not urls: return

    print(f"🚀 启动‘万能提取’模式，正在处理 {len(urls)} 个源...")
    api_base = "http://127.0.0.1:25500/sub?"
    
    all_nodes = []

    for idx, url in enumerate(urls):
        print(f"[{idx+1}/{len(urls)}] 尝试提取: {url[:50]}...")
        try:
            # 这里的关键改动：target 设置为 v2ray，但 url 后面不加 list=true
            # 让 SubConverter 自动识别源格式 (YAML/Base64/SIP002)
            # 我们直接请求它把源转成最通用的 v2ray base64 格式
            api_url = f"{api_base}target=v2ray&url={urllib.parse.quote(url)}"
            r = requests.get(api_url, timeout=20)
            
            if r.status_code == 200 and r.text.strip():
                # SubConverter 返回的是 Base64，我们不用解码，直接存着
                all_nodes.append(r.text.strip())
                print(f"   ✅ 提取成功 (数据长度: {len(r.text)})")
            else:
                print(f"   ❌ 失败: HTTP {r.status_code}")
        except:
            print(f"   ⚠️ 超时")
        time.sleep(0.3)

    if not all_nodes:
        print("❌ 依然没有提取到任何有效数据")
        return

    # 将所有拿到的 base64 块拼接，SubConverter 能识别这种“多重 base64”
    print(f"--- 📊 抓取完成，正在合并并生成最终配置 ---")
    
    # 将汇总后的 base64 数据再次喂回给 SubConverter
    # 这一次我们让它生成最终的 Clash 和 V2Ray
    final_data = "|".join(all_nodes) 

    try:
        # 生成 Clash
        r_clash = requests.post("http://127.0.0.1:25500/sub", data={"target": "clash", "data": final_data}, timeout=60)
        if "proxies:" in r_clash.text:
            with open("config.yaml", "w", encoding="utf-8") as f:
                f.write(r_clash.text)
            print("🎉 config.yaml 生成成功！")

        # 生成 V2Ray (明文列表)
        r_v2ray = requests.post("http://127.0.0.1:25500/sub", data={"target": "v2ray", "data": final_data, "list": "true"}, timeout=60)
        with open("sub_v2ray.txt", "w", encoding="utf-8") as f:
            f.write(r_v2ray.text)
        print("🎉 sub_v2ray.txt 生成成功！")
        
    except Exception as e:
        print(f"❌ 汇总环节出错: {e}")

if __name__ == "__main__":
    main()
