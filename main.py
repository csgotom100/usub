import requests
import os
import base64

def main():
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]

    all_raw_data = []
    headers = {'User-Agent': 'clash-verge/1.0; Mozilla/5.0'}

    print(f"🚀 正在本地下载源数据...")
    for idx, url in enumerate(urls):
        try:
            # 加上较短的超时，避免浪费时间在死链上
            r = requests.get(url, headers=headers, timeout=8)
            if r.status_code == 200 and len(r.text) > 100:
                all_raw_data.append(r.text)
                print(f"   [{idx+1}] ✅ 抓取成功")
        except: continue

    if not all_raw_data:
        print("❌ 没有任何有效数据")
        return

    # 将所有内容合并成一个巨大的临时文件
    # 这样我们可以通过 POST 传输而不受 URL 长度限制
    combined_content = "\n".join(all_raw_data)
    
    print(f"📊 准备进行本地渲染 (混合模式)...")

    api_url = "http://127.0.0.1:25500/sub"
    
    # 核心策略：
    # 1. 使用 target=clash
    # 2. 增加 &list=true (只输出节点列表，避开复杂的规则集下载)
    # 3. 之后我们再手动给它加上简单的头信息
    
    try:
        # 第一步：先尝试获取纯节点列表格式 (这个最不容易报错)
        payload = {
            "target": "clash",
            "data": combined_content,
            "list": "true", # 关键：只输出节点，不输出规则和分组
            "emoji": "true"
        }
        
        print("📦 请求后端提取纯净节点...")
        r = requests.post(api_url, data=payload, timeout=60)
        
        if "proxies:" in r.text or "- name:" in r.text:
            # 如果返回的内容没有 proxies: 开头，我们帮它加上
            final_clash = r.text
            if "proxies:" not in r.text:
                final_clash = "proxies:\n" + r.text
            
            with open("config.yaml", "w", encoding="utf-8") as f:
                f.write(final_clash)
            print(f"🎉 config.yaml 已生成 (大小: {len(final_clash)} 字节)")
            
            # 同步生成 V2Ray 订阅
            payload["target"] = "v2ray"
            r_v2ray = requests.post(api_url, data=payload, timeout=60)
            with open("sub_v2ray.txt", "w", encoding="utf-8") as f:
                f.write(r_v2ray.text)
            print("🎉 sub_v2ray.txt 已生成")
        else:
            print("❌ 提取失败，后端未返回有效节点。")
            # 打印前 200 个字符看看后端到底说了什么
            print(f"DEBUG 后端原始输出: {r.text[:200]}")

    except Exception as e:
        print(f"❌ 运行异常: {e}")

if __name__ == "__main__":
    main()
