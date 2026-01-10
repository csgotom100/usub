import requests
import os
import re

def clean_node_block(block):
    """深度清洗：自动补全缺失字段，确保与你提供的 config.yaml 格式完全一致"""
    lines = block.splitlines()
    data = {}
    for line in lines:
        line = line.strip()
        if ':' not in line: continue
        k = line.split(':')[0].strip().lower()
        v = line.split(':', 1)[1].strip()
        if v: data[k] = v

    cleaned = []
    # 1. 基础字段提取
    base_keys = ["type", "server", "port", "uuid", "password", "auth-str", "sni", "skip-cert-verify", "udp", "network"]
    for k in base_keys:
        if k in data: cleaned.append(f"{k}: {data[k]}")

    node_type = data.get("type", "").lower()

    # 2. 针对 mieru 协议补全 transport (对应 Node_09)
    if node_type == "mieru":
        cleaned.append(f"transport: {data.get('transport', 'TCP')}")

    # 3. 针对 tuic 协议补全 username (对应 Node_10, 11)
    if node_type == "tuic":
        cleaned.append("alpn: [h3]")
        if "username" not in data:
            u_val = data.get("uuid", data.get("password", "default_user"))
            cleaned.append(f"username: {u_val}")
        for k in ["congestion-controller", "reduce-rtt"]:
            if k in data: cleaned.append(f"{k}: {data[k]}")

    # 4. 针对 hysteria 协议补全 protocol 和 alpn (对应 Node_01, 12 等)
    if "hysteria" in node_type:
        cleaned.append("protocol: udp")
        cleaned.append("alpn: [h3]")
        for k in ["up", "down"]:
            if k in data: cleaned.append(f"{k}: {data[k]}")

    # 5. VLESS Reality 结构化修正 (对应 Node_03, 07, 08)
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
    
    for i, chunk in enumerate(unique_dict.values()):
        name = f"Node_{len(node_names) + 1:02d}"
        node_names.append(name)
        clash_config.append(f"  - name: \"{name}\"")
        for attr in clean_node_block(chunk):
            clash_config.append(f"    {attr}")

    # 策略组部分
    clash_config.extend([
        "", "proxy-groups:",
        "  - name: 🚀 节点选择",
        "    type: select",
        "    proxies:"
    ])
    for n in node_names:
        clash_config.append(f"      - \"{n}\"")
    clash_config.append("      - DIRECT")

    # 神机分流规则 (对应你 GitHub 链接中的规则)
    clash_config.extend([
        "", "rules:",
        "  # 核心服务分流",
        "  - DOMAIN-SUFFIX,google.com,🚀 节点选择",
        "  - DOMAIN-KEYWORD,github,🚀 节点选择",
        "  - DOMAIN-KEYWORD,youtube,🚀 节点选择",
        "  - DOMAIN-KEYWORD,google,🚀 节点选择",
        "  - DOMAIN-SUFFIX,telegram.org,🚀 节点选择",
        "",
        "  # 国内常用服务直连",
        "  - DOMAIN-SUFFIX,cn,DIRECT",
        "  - DOMAIN-KEYWORD,baidu,DIRECT",
        "  - DOMAIN-KEYWORD,taobao,DIRECT",
        "  - DOMAIN-KEYWORD,jd,DIRECT",
        "  - DOMAIN-KEYWORD,aliyun,DIRECT",
        "  - DOMAIN-KEYWORD,tencent,DIRECT",
        "",
        "  # 局域网与地理位置",
        "  - GEOIP,LAN,DIRECT",
        "  - GEOIP,CN,DIRECT",
        "",
        "  # 兜底规则",
        "  - MATCH,🚀 节点选择"
    ])

    with open("config.yaml", "w", encoding="utf-8") as f:
        f.write("\n".join(clash_config))
    print(f"✅ 成功复刻 GitHub 配置，生成 {len(node_names)} 个节点。")

if __name__ == "__main__":
    main()
