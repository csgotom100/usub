import requests
import os
import re

def clean_node_block(block):
    """极致兼容性清理：修复协议错位字段并补全必填项"""
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

    # 1. 基础核心字段 (通用)
    base_keys = ["type", "server", "port", "uuid", "password", "auth-str", "sni", "skip-cert-verify", "udp", "network"]
    for k in base_keys:
        if k in data: cleaned.append(f"{k}: {data[k]}")

    # 2. 针对 Hysteria 的强制补全 (修复 Node_01 等报错)
    if "hysteria" in node_type:
        cleaned.append("protocol: udp") # 显式声明协议
        cleaned.append("alpn: [h3]")     # 显式补全 ALPN
        if "up" in data: cleaned.append(f"up: {data['up']}")
        if "down" in data: cleaned.append(f"down: {data['down']}")

    # 3. 针对 TUIC 的强制补全 (Node_10, 11)
    if node_type == "tuic":
        cleaned.append("alpn: [h3]")
        for k in ["congestion-controller", "reduce-rtt"]:
            if k in data: cleaned.append(f"{k}: {data[k]}")

    # 4. 针对 VLESS Reality 的结构修正 (去掉错误的 up/down)
    if node_type == "vless":
        cleaned.append("tls: true")
        if "public-key" in data:
            cleaned.append("reality-opts:")
            cleaned.append(f"  public-key: {data['public-key']}")
            if "short-id" in data: cleaned.append(f"  short-id: {data['short-id']}")
        if "client-fingerprint" in data:
            cleaned.append(f"client-fingerprint: {data['client-fingerprint']}")

    return cleaned

def main():
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]

    all_raw_chunks = []
    headers = {'User-Agent': 'clash-verge/1.0'}

    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=10)
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

    # 策略组
    clash_config.extend([
        "", "proxy-groups:",
        "  - name: 🚀 节点选择",
        "    type: select",
        "    proxies:"
    ])
    for n in node_names:
        clash_config.append(f"      - \"{n}\"")
    clash_config.append("      - DIRECT")

    # 分流规则
    clash_config.extend([
        "", "rules:",
        "  - DOMAIN-SUFFIX,google.com,🚀 节点选择",
        "  - DOMAIN-KEYWORD,github,🚀 节点选择",
        "  - DOMAIN-KEYWORD,youtube,🚀 节点选择",
        "  - DOMAIN-KEYWORD,google,🚀 节点选择",
        "  - DOMAIN-SUFFIX,telegram.org,🚀 节点选择",
        "  - DOMAIN-SUFFIX,cn,DIRECT",
        "  - DOMAIN-KEYWORD,baidu,DIRECT",
        "  - GEOIP,LAN,DIRECT",
        "  - GEOIP,CN,DIRECT",
        "  - MATCH,🚀 节点选择"
    ])

    with open("config.yaml", "w", encoding="utf-8") as f:
        f.write("\n".join(clash_config))
    print(f"✅ 修正版配置已生成！(已修复 Hysteria ALPN 和 VLESS 脏字段)")

if __name__ == "__main__":
    main()
