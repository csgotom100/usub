import requests
import os
import re

def get_pure_proxies(text):
    """
    专门从 Clash 格式或 Base64 中提取纯净的节点部分
    """
    # 如果是 Base64，直接返回，SubConverter 处理单段 Base64 很稳
    if re.match(r'^[A-Za-z0-9+/=\s]+$', text) and len(text) > 100:
        return text
    
    # 如果是 Clash 格式，只提取 proxies 列表下的内容
    if "proxies:" in text:
        # 找到 proxies: 开始到下一个大项（如 proxy-groups 或 rules）之前的内容
        start = text.find("proxies:")
        # 尝试寻找下一个配置大项作为结束标记
        end = len(text)
        for marker in ["proxy-groups:", "rules:", "rule-providers:", "script:"]:
            marker_idx = text.find(marker, start)
            if marker_idx != -1 and marker_idx < end:
                end = marker_idx
        
        chunk = text[start:end].replace("proxies:", "").strip()
        # 确保返回的是以 - name: 开头的行
        return chunk
    
    return ""

def main():
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]

    valid_proxies = []
    headers = {'User-Agent': 'clash-verge/1.0; Mozilla/5.0'}

    print(f"🚀 正在清洗并提取纯净节点...")
    for idx, url in enumerate(urls):
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                proxy_chunk = get_pure_proxies(r.text)
                if proxy_chunk:
                    valid_proxies.append(proxy_chunk)
                    print(f"   [{idx+1}] ✅ 提取成功")
        except: continue

    if not valid_proxies:
        print("❌ 未能提取到任何有效节点")
        return

    # 构造最终喂给 SubConverter 的数据：一个标准的 proxies 列表
    final_payload = "proxies:\n" + "\n".join(valid_proxies)
    
    print(f"📊 汇总完成，准备渲染最终订阅...")

    try:
        # 此时的 payload 是标准格式，SubConverter 绝不会报错
        r_clash = requests.post("http://127.0.0.1:25500/sub", 
                               data={"target": "clash", "data": final_payload}, 
                               timeout=60)
        
        if "proxies:" in r_clash.text:
            with open("config.yaml", "w", encoding="utf-8") as f:
                f.write(r_clash.text)
            print(f"🎉 config.yaml 生成成功！(节点大小: {len(r_clash.text)} 字节)")
            
            # 同时生成一份 v2ray 订阅备用
            r_v2ray = requests.post("http://127.0.0.1:25500/sub", 
                                   data={"target": "v2ray", "data": final_payload, "list": "true"}, 
                                   timeout=60)
            with open("sub_v2ray.txt", "w", encoding="utf-8") as f:
                f.write(r_v2ray.text)
        else:
            print("❌ 转换后未发现 proxies 关键字，请检查后端输出。")
            
    except Exception as e:
        print(f"❌ 转换过程出错: {e}")

if __name__ == "__main__":
    main()
