import requests
import os
import re

def is_valid_proxy(block):
    """基础校验：确保节点包含核心三要素，防止 Clash 加载失败"""
    if not all(k in block for k in ["type:", "server:", "port:"]):
        return False
    # 针对 TUIC 协议的特殊检查
    if "type: tuic" in block:
        if "uuid:" not in block and "username:" not in block:
            return False
    return True

def clean_node_block(block):
    """极致清洗：处理 Reality 嵌套结构并补全 Hysteria 必备字段"""
    lines = block.splitlines()
    data = {}
    for line in lines:
        line = line.strip()
        if ':' not in line: continue
        k = line.split(':')[0].strip().lower()
        v = line.split(':', 1)[1].strip()
        if v: data[k] = v

    cleaned = []
    # 1. 基础核心字段 (白名单模式)
    base_keys = ["type", "server", "port", "uuid", "password", "auth-str", "sni", "skip-cert-verify", "udp", "network"]
    for k in base_keys:
        if k in data: cleaned.append(f"{k}: {data[k]}")

    # 2. Hysteria / TUIC 特色字段处理
    if "hysteria" in data.get("type", ""):
        if "protocol" not in data: cleaned.append("protocol: udp")
        cleaned.append("alpn: [h3]")  # 强制补全 ALPN 保证连通性
        for k in ["up", "down"]:
            if k in data: cleaned.append(f"{k}: {data[k]}")

    if data.get("type") == "tuic":
        cleaned.append("alpn: [h3]")
        for k in ["congestion-controller", "reduce-rtt"]:
            if k in data: cleaned.append(f"{k}: {data[k]}")

    # 3. VLESS / Reality 结构修正 (将散乱的属性归位到 reality-opts)
    if data.get("type") == "vless":
        cleaned.append("tls: true")
        if "public-key" in data:
            cleaned.append("reality-opts:")
            cleaned.append(f"  public-key: {data['public-key']}")
            if "short-id" in data: cleaned.append(f"  short-id: {data['short-id']}")
        if "client-fingerprint" in data:
            cleaned.append(f"client-fingerprint: {data['client-fingerprint']}")

    return cleaned

def main():
    # 确保读取 sources.txt 中的订阅链接
    if not os.path.exists('sources.txt'):
        print("❌ 错误: 找不到 sources.txt")
        return
        
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]

    all_raw_chunks = []
    headers = {'User-Agent': 'clash-verge/1.0'}

    print(f"🚀 正在从 {len(urls)} 个来源抓取节点...")
    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                # 暴力切割法：通过 - name: 定位每一个可能的节点块
                chunks = re.split(r'-\s*name:', r.text)
                for c in chunks:
                    if is_valid_proxy(c):
                        all_raw_chunks.append(c)
        except: continue

    # 按 Server 地址去重，防止相同节点多次出现
    unique_dict = {}
    for chunk in all_raw_chunks:
        s_match = re.search(r'server:\s*([^\s]+)', chunk)
        if s_match:
            unique_dict[s_match.group(1)] = chunk
    
    unique_nodes = list(unique_dict.values())
    if not unique_nodes:
        print("❌ 未抓取到任何有效节点")
        return

    # --- 构建 Clash 配置文件主体 ---
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

    # --- 策略组设置 (神机规则逻辑) ---
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

    # --- 神机规则分流逻辑 (智能分流) ---
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
        "  # 国内常用服务直连",
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
        "  # 兜底规则 (其余全部按节点选择)",
        "  - MATCH,🚀 节点选择"
    ])

    # 写入 config.yaml
    with open("config.yaml", "w", encoding="utf-8") as f:
        f.write("\n".join(clash_config))
        
    # 同时生成一个简单的 v2ray 格式列表备份
    with open("sub_v2ray.txt", "w", encoding="utf-8") as f:
        f.write("\n\n".join(unique_nodes))
    
    print(f"🎉 任务圆满完成！已生成 {len(node_names)} 个节点并应用神机规则。")

if __name__ == "__main__":
    main()
