import requests
import os
import re

def extract_nodes_brute_force(text):
    """
    暴力拆解法：直接通过 server: 关键字定位节点
    """
    lines = text.splitlines()
    nodes = []
    current_node = []
    
    for line in lines:
        # 如果遇到 - name: 或者 name:，说明可能是一个新节点开始
        # 或者如果 current_node 已经有内容，且当前行包含 server:
        if "name:" in line and current_node:
            nodes.append("\n".join(current_node))
            current_node = []
        
        # 过滤掉那些明显的策略组干扰行
        if any(x in line for x in ["🚀", "🍎", "📲", "🍃", "🎯", "♻️", "Ⓜ️", "🛑"]):
            continue
            
        current_node.append(line)
    
    # 放入最后一个
    if current_node:
        nodes.append("\n".join(current_node))
        
    # 二次清洗：只保留真正含有 server 信息的块
    real_proxies = []
    for n in nodes:
        if "server:" in n and "type:" in n:
            real_proxies.append(n)
    return real_proxies

def main():
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]

    all_raw_chunks = []
    headers = {'User-Agent': 'clash-verge/1.0'}

    print(f"🚀 启动‘暴力扫描’模式...")
    for idx, url in enumerate(urls):
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                chunks = extract_nodes_brute_force(r.text)
                all_raw_chunks.extend(chunks)
                if chunks: print(f"   [{idx+1}] ✅ 发现 {len(chunks)} 个潜在节点")
        except: continue

    if not all_raw_chunks:
        print("❌ 依然没有提取到任何节点")
        return

    # 构造 Clash 结构
    clash_config = [
        "port: 7890",
        "socks-port: 7891",
        "allow-lan: true",
        "mode: rule",
        "proxies:"
    ]
    
    node_names = []
    # 记录已使用的服务器，防止完全重复的节点
    seen_servers = set()

    for i, chunk in enumerate(all_raw_chunks):
        # 提取 server 地址做去重
        server_match = re.search(r'server:\s*([^\s]+)', chunk)
        server_addr = server_match.group(1) if server_match else str(i)
        
        if server_addr in seen_servers: continue
        seen_servers.add(server_addr)

        # 提取类型
        type_match = re.search(r'type:\s*(\w+)', chunk)
        p_type = type_match.group(1) if type_match else "proxy"
        
        name = f"{p_type}_{i+1:02d}"
        node_names.append(name)

        # 压入 proxies 列表，强制对齐缩进
        clash_config.append(f"  - name: \"{name}\"")
        lines = chunk.splitlines()
        for l in lines:
            ls = l.strip()
            # 跳过原本的名字行和空行
            if "name:" in ls or not ls: continue
            clash_config.append(f"    {ls}")

    # 策略组
    clash_config.extend(["", "proxy-groups:", "  - name: 🚀 节点选择", "    type: select", "    proxies:"])
    for n in node_names:
        clash_config.append(f"      - \"{n}\"")
    
    clash_config.extend(["      - DIRECT", "", "rules:", "  - MATCH,🚀 节点选择"])

    with open("config.yaml", "w", encoding="utf-8") as f:
        f.write("\n".join(clash_config))
    
    print(f"🎉 成功！最终生成了 {len(node_names)} 个节点。")

if __name__ == "__main__":
    main()
