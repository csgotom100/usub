import requests
import os
import re

def is_valid_proxy(block):
    """核心校验：确保节点包含 server/type/port，并初步过滤不完整的节点"""
    if not all(k in block for k in ["type:", "server:", "port:"]):
        return False
    # 过滤掉包含旧报错信息的脏块
    if "key 'username' missing" in block or "transport' missing" in block:
        return False
    return True

def clean_node_block(block):
    """深度清洗：修正 Reality 嵌套，并补全 Hysteria、TUIC 和 Mieru 的必需参数"""
    lines = block.splitlines()
    data = {}
    for line in lines:
        line = line.strip()
        if ':' not in line: continue
        k = line.split(':')[0].strip().lower()
        v = line.split(':', 1)[1].strip()
        if v: data[k] = v

    cleaned = []
    # 基础核心字段白名单
    base_keys = ["type", "server", "port", "uuid", "password", "auth-str", "sni", "skip-cert-verify", "udp", "network"]
    for k in base_keys:
        if k in data: cleaned.append(f"{k}: {data[k]}")

    node_type = data.get("type", "").lower()

    # 1. Hysteria 协议补全
    if "hysteria" in node_type:
        if "protocol" not in data: cleaned.append("protocol: udp")
        cleaned.append("alpn: [h3]")
        for k in ["up", "down"]:
            if k in data: cleaned.append(f"{k}: {data[k]}")

    # 2. TUIC 协议补全
    if node_type == "tuic":
        cleaned.append("alpn: [h3]")
        for k in ["congestion-controller", "reduce-rtt"]:
            if k in data: cleaned.append(f"{k}: {data[k]}")

    # 3. Mieru 协议补全 (修正图片中的 transport missing 错误)
    if node_type == "mieru":
        if "transport" not in data:
            cleaned.append("transport: tcp") # 默认补全为 tcp
        else:
            cleaned.append(f"transport: {data['transport']}")

    # 4. VLESS / Reality 结构修正
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
    if not os.path.exists('sources.txt'):
        print("❌ 错误: 找不到 sources.txt")
        return
        
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]

    all_raw_chunks = []
    headers = {'User-Agent': 'clash-verge/1.0'}

    print(f"📡 正在处理订阅来源...")
    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                chunks = re.split(r'-\s*name:', r.text)
                for c in chunks:
                    if is_valid_proxy(c):
                        all_raw_chunks.append(c)
        except: continue

    # 按 Server 去重
    unique_dict = {}
    for chunk in all_raw_chunks:
        s_match = re.search(r'server:\s*([^\s]+)', chunk)
        if s_match:
            unique_dict[s_match.group(1)] = chunk
    
    unique_nodes = list(unique_dict.values())
    if not unique_nodes:
        print("⚠️ 未发现有效节点")
        return

    # --- 组装配置文件 ---
    clash_config = [
        "port: 7890",
        "allow-lan: true",
        "mode: rule",
        "log-level: info",
        "proxies:"
    ]
    
    node_names = []
    for i, chunk in enumerate(unique_nodes):
        name = f"Node_{len(node_names) + 1:02d}"
        node_names.append(name)
        clash_config.append(f"  - name: \"{name}\"")
        for attr in clean_node_block(chunk):
            clash_config.append(f"    {attr}")

    # --- 策略组 (神机规则配套) ---
    clash_config.extend([
        "",
        "proxy-groups:",
        "  - name: 🚀 节点选择",
        "    type: select",
        "    proxies:",
    ])
    for n in node_names:
        clash_config.append(f"      - \"{n}\"")
    clash_config.append("      - DIRECT")

    # --- 神机规则分流逻辑 ---
    clash_config.extend([
        "",
        "rules:",
        "  # 核心海外服务",
        "  - DOMAIN-SUFFIX,google.com,🚀 节点选择",
        "  - DOMAIN-KEYWORD,github,🚀 节点选择",
        "  - DOMAIN-KEYWORD,youtube,🚀 节点选择",
        "  - DOMAIN-KEYWORD,google,🚀 节点选择",
        "  - DOMAIN-SUFFIX,telegram.org,🚀 节点选择",
        "  ",
        "  # 国内服务直连",
        "  - DOMAIN-SUFFIX,cn,DIRECT",
        "  - DOMAIN-KEYWORD,baidu,DIRECT",
        "  - DOMAIN-KEYWORD,taobao,DIRECT",
        "  - DOMAIN-KEYWORD,jd,DIRECT",
        "  - DOMAIN-KEYWORD,aliyun,DIRECT",
        "  - DOMAIN-KEYWORD,tencent,DIRECT",
        "  ",
        "  # 局域网与地理位置",
        "  - GEOIP,LAN,DIRECT",
        "  - GEOIP,CN,DIRECT",
        "  ",
        "  # 兜底规则",
        "  - MATCH,🚀 节点选择"
    ])

    with open("config.yaml", "w", encoding="utf-8") as f:
        f.write("\n".join(clash_config))
    
    print(f"✅ 完成！已生成含有 {len(node_names)} 个节点并应用神机规则。")

if __name__ == "__main__":
    main()
