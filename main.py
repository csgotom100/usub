import requests
import os
import re

def clean_node_block(block):
    """深度清洗：根据内核严格要求强制对齐字段"""
    lines = block.splitlines()
    data = {}
    for line in lines:
        line = line.strip()
        if ':' not in line: continue
        k = line.split(':')[0].strip().lower()
        v = line.split(':', 1)[1].strip()
        if v: data[k] = v

    cleaned = []
    node_type = data.get("type", "").lower()

    # 1. 基础字段
    base_keys = ["type", "server", "port", "uuid", "password", "auth-str", "sni", "skip-cert-verify"]
    for k in base_keys:
        if k in data: cleaned.append(f"{k}: {data[k]}")

    # 2. 针对 Hysteria (Node 01, 02, 04, 05, 12)
    if "hysteria" in node_type:
        cleaned.append("alpn: [h3]")
        cleaned.append("protocol: udp")
        if "up" in data: cleaned.append(f"up: {data['up']}")
        if "down" in data: cleaned.append(f"down: {data['down']}")

    # 3. 针对 Mieru (Node 09) - 修复 transport missing
    elif node_type == "mieru":
        cleaned.append("transport: tcp")

    # 4. 针对 TUIC (Node 10, 11) - 修复 username missing
    elif node_type == "tuic":
        cleaned.append("alpn: [h3]")
        # 强制将 uuid 或 password 映射为 username
        u_val = data.get("username", data.get("uuid", data.get("password", "default")))
        cleaned.append(f"username: {u_val}")
        for k in ["congestion-controller", "reduce-rtt"]:
            if k in data: cleaned.append(f"{k}: {data[k]}")

    # 5. 针对 VLESS (Node 03, 07, 08) - 剔除错误的 up/down 字段
    elif node_type == "vless":
        cleaned.append("udp: true")
        cleaned.append("network: tcp")
        cleaned.append("tls: true")
        if "public-key" in data:
            cleaned.append("reality-opts:")
            cleaned.append(f"  public-key: {data['public-key']}")
            if "short-id" in data: cleaned.append(f"  short-id: {data['short-id']}")
        if "client-fingerprint" in data:
            cleaned.append(f"client-fingerprint: {data['client-fingerprint']}")

    # 6. 其他协议 (如 anytls)
    elif "udp" in data:
        cleaned.append(f"udp: {data['udp']}")

    return cleaned

def main():
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]

    all_raw_chunks = []
    for url in urls:
        try:
            r = requests.get(url, headers={'User-Agent': 'clash-verge/1.0'}, timeout=10)
            if r.status_code == 200:
                chunks = re.split(r'-\s*name:', r.text)
                for c in chunks:
                    if "server:" in c and "type:" in c: all_raw_chunks.append(c)
        except: continue

    unique_dict = {}
    for chunk in all_raw_chunks:
        s_match = re.search(r'server:\s*([^\s]+)', chunk)
        if s_match: unique_dict[s_match.group(1)] = chunk
    
    clash_config = [
        "port: 7890", "allow-lan: true", "mode: rule", "log-level: info", "proxies:"
    ]
    node_names = []
    for chunk in unique_dict.values():
        name = f"Node_{len(node_names) + 1:02d}"
        node_names.append(name)
        clash_config.append(f"  - name: \"{name}\"")
        for attr in clean_node_block(chunk):
            clash_config.append(f"    {attr}")

    clash_config.extend([
        "", "proxy-groups:",
        "  - name: 🚀 节点选择",
        "    type: select",
        "    proxies:"
    ])
    for n in node_names: clash_config.append(f"      - \"{n}\"")
    clash_config.append("      - DIRECT")

    clash_config.extend([
        "", "rules:",
        "  - DOMAIN-SUFFIX,google.com,🚀 节点选择",
        "  - DOMAIN-KEYWORD,github,🚀 节点选择",
        "  - DOMAIN-KEYWORD,youtube,🚀 节点选择",
        "  - DOMAIN-SUFFIX,cn,DIRECT",
        "  - GEOIP,LAN,DIRECT",
        "  - GEOIP,CN,DIRECT",
        "  - MATCH,🚀 节点选择"
    ])

    with open("config.yaml", "w", encoding="utf-8") as f:
        f.write("\n".join(clash_config))
    print(f"✅ 已强制对齐字段，生成 {len(node_names)} 个节点，错误已修复。")

if __name__ == "__main__":
    main()
