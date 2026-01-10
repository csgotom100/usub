import requests
import os
import re

def is_valid_clash_proxy(block):
    """校验节点是否包含必要字段，防止 Clash 报错"""
    # 基础检查：必须包含 type, server, port
    if not all(k in block for k in ["type:", "server:", "port:"]):
        return False
    # 针对 TUIC 协议的特殊检查
    if "type: tuic" in block:
        if "uuid:" not in block and "username:" not in block:
            return False
    return True

def extract_nodes_brute_force(text):
    lines = text.splitlines()
    nodes = []
    current_node = []
    for line in lines:
        if "name:" in line and current_node:
            nodes.append("\n".join(current_node))
            current_node = []
        # 过滤掉干扰行
        if any(x in line for x in ["🚀", "🍎", "🎯", "♻️", "🛑"]): continue
        current_node.append(line)
    if current_node: nodes.append("\n".join(current_node))
    
    # 关键：只保留通过校验的节点
    return [n for n in nodes if is_valid_clash_proxy(n)]

def main():
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]

    all_raw_chunks = []
    headers = {'User-Agent': 'clash-verge/1.0'}

    for idx, url in enumerate(urls):
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                chunks = extract_nodes_brute_force(r.text)
                all_raw_chunks.extend(chunks)
        except: continue

    # 按 server 地址去重
    unique_nodes = list({re.search(r'server:\s*([^\s]+)', n).group(1): n for n in all_raw_chunks if "server:" in n}.values())

    if not unique_nodes: return

    clash_config = ["port: 7890", "mode: rule", "proxies:"]
    node_names = []
    for i, chunk in enumerate(unique_nodes):
        name = f"Node_{i+1:02d}"
        node_names.append(name)
        clash_config.append(f"  - name: \"{name}\"")
        for l in chunk.splitlines():
            if "name:" in l or not l.strip(): continue
            clash_config.append(f"    {l.strip()}")

    clash_config.extend(["", "proxy-groups:", "  - name: 🚀 节点选择", "    type: select", "    proxies:"])
    clash_config.extend([f"      - \"{n}\"" for n in node_names])
    clash_config.extend(["      - DIRECT", "", "rules:", "  - MATCH,🚀 节点选择"])

    with open("config.yaml", "w", encoding="utf-8") as f:
        f.write("\n".join(clash_config))
    print(f"🎉 成功生成 {len(node_names)} 个有效节点")

if __name__ == "__main__":
    main()
