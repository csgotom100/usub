import requests
import os
import re

def is_valid_proxy(block):
    """基础校验：确保节点包含 server/type/port，并过滤已知错误块"""
    if not all(k in block for k in ["type:", "server:", "port:"]):
        return False
    # 如果块中包含之前的报错提示，说明是脏数据，直接跳过
    if any(msg in block for msg in ["missing", "failed", "error"]):
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
    # 1. 基础核心字段白名单
    base_keys = ["type", "server", "port", "uuid", "password", "auth-str", "sni", "skip-cert-verify", "udp", "network"]
    for k in base_keys:
        if k in data: cleaned.append(f"{k}: {data[k]}")

    node_type = data.get("type", "").lower()

    # 2. Hysteria 协议增强
    if "hysteria" in node_type:
        if "protocol" not in data: cleaned.append("protocol: udp")
        cleaned.append("alpn: [h3]")
        for k in ["up", "down"]:
            if k in data: cleaned.append(f"{k}: {data[k]}")

    # 3. TUIC 协议补全 (针对 image_8d1b69.png 中的 username 错误)
    if node_type == "tuic":
        cleaned.append("alpn: [h3]")
        # TUIC 在某些版本需要 uuid 或 username，这里做兼容处理
        if "uuid" not in data and "password" in data:
            cleaned.append(f"uuid: {data['password']}")
        # 补全 username 字段防止报错
        if "username" not in data:
            cleaned.append(f"username: {data.get('uuid', 'default')}")
        for k in ["congestion-controller", "reduce-rtt"]:
            if k in data: cleaned.append(f"{k}: {data[k]}")

    # 4. Mieru 协议补全 (针对 image_97896a.png 中的 transport 错误)
    if node_type == "mieru":
        # 强制补全 transport，这是 mieru 协议必需项
        cleaned.append(f"transport: {data.get('transport', 'tcp')}")
        if "username" not in data:
            cleaned.append(f"username: {data.get('password', 'default')}")

    # 5. VLESS / Reality 结构修正
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

    print(f"📡 正在从源提取并清洗节点...")
    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                # 暴力切割：基于 YAML 列表特征分割块
                chunks = re.split(r'-\s*name:', r.text)
                for c in chunks:
                    if is_valid_proxy(c):
                        all_raw_chunks.append(c)
        except: continue

    # 按 Server 地址去重
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

    # --- ACL4SSR 神机规则分流逻辑 ---
    clash_config.extend([
        "",
        "rules:",
        "  # 核心服务分流",
        "  - DOMAIN-SUFFIX,google.com,🚀 节点选择",
        "  - DOMAIN-KEYWORD,github,🚀 节点选择",
        "  - DOMAIN-KEYWORD,youtube,🚀 节点选择",
        "  - DOMAIN-KEYWORD,google,🚀 节点选择",
        "  - DOMAIN-SUFFIX,telegram.org,🚀 节点选择",
        "  ",
        "  # 国内常用服务直连 (神机规则精简版)",
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
    
    print(f"✅ 完成！生成的 config.yaml 已修复报错并应用神机规则。")

if __name__ == "__main__":
    main()
