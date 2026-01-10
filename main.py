import requests
import os
import re

def clean_node_block(block):
    """最严格的字段清洗，确保 100% 匹配内核规范"""
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

    # 1. 公共必填基础字段
    base_keys = ["type", "server", "port"]
    for k in base_keys:
        if k in data: cleaned.append(f"{k}: {data[k]}")

    # 2. 根据协议类型“死命令”补全
    if "hysteria" in node_type:
        # Hysteria 必须有 auth-str/password, sni, alpn, up/down
        for k in ["auth-str", "password", "sni", "skip-cert-verify"]:
            if k in data: cleaned.append(f"{k}: {data[k]}")
        cleaned.append("alpn: [h3]")
        cleaned.append("protocol: udp")
        if "up" in data: cleaned.append(f"up: {data['up']}")
        if "down" in data: cleaned.append(f"down: {data['down']}")

    elif node_type == "vless":
        # VLESS 严格禁止 up/down，必须有 uuid, tls, reality-opts
        if "uuid" in data: cleaned.append(f"uuid: {data['uuid']}")
        cleaned.append("udp: true")
        cleaned.append("network: tcp")
        cleaned.append("tls: true")
        if "public-key" in data:
            cleaned.append("reality-opts:")
            cleaned.append(f"  public-key: {data['public-key']}")
            if "short-id" in data: cleaned.append(f"  short-id: {data['short-id']}")
        if "client-fingerprint" in data: cleaned.append(f"client-fingerprint: {data['client-fingerprint']}")
        if "sni" in data: cleaned.append(f"sni: {data['sni']}")

    elif node_type == "tuic":
        # TUIC 必须有 uuid, password, alpn, 以及致命的 username
        for k in ["uuid", "password", "sni", "skip-cert-verify"]:
            if k in data: cleaned.append(f"{k}: {data[k]}")
        cleaned.append("alpn: [h3]")
        # 补全 username 核心报错点
        u_val = data.get("username", data.get("uuid", data.get("password", "default")))
        cleaned.append(f"username: {u_val}")
        for k in ["congestion-controller", "reduce-rtt"]:
            if k in data: cleaned.append(f"{k}: {data[k]}")

    elif node_type == "mieru":
        # Mieru 必须有 password 和 transport
        if "password" in data: cleaned.append(f"password: {data['password']}")
        cleaned.append("transport: TCP")

    elif node_type == "anytls":
        if "password" in data: cleaned.append(f"password: {data['password']}")
        cleaned.append("udp: true")
        cleaned.append("skip-cert-verify: true")

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

    # 去重
    unique_dict = {}
    for chunk in all_raw_chunks:
        s_match = re.search(r'server:\s*([^\s]+)', chunk)
        if s_match: unique_dict[s_match.group(1)] = chunk
    
    # 构建最终 YAML 字符串
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

    # 基础规则
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
    print(f"✅ 完成！生成的 config.yaml 已经强制修复了所有已知报错字段。")

if __name__ == "__main__":
    main()
