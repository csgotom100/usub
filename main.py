import requests
import os
import re

def clean_node_block(block):
    """清洗节点属性，只保留合法的 Proxy 配置项，并过滤空值"""
    cleaned_lines = []
    # 允许保留的 Clash 代理协议关键字
    allow_list = [
        "type", "server", "port", "uuid", "password", "sni", "alpn", 
        "skip-cert-verify", "protocol", "up", "down", "network", 
        "flow", "client-fingerprint", "reality-opts", "public-key", 
        "short-id", "smux", "enabled", "max-connections", "auth-str",
        "udp", "congestion-controller", "reduce-rtt", "transport"
    ]
    
    for line in block.splitlines():
        line = line.strip()
        if ':' not in line: continue
        
        # 拆分 key 和 value
        key = line.split(':')[0].strip().lower()
        value = line.split(':', 1)[1].strip()
        
        # 1. 检查 Key 是否在白名单内
        # 2. 确保 Value 不为空（或者是个列表 [h3]）
        if key in allow_list and value != "":
            cleaned_lines.append(line)
            
    return cleaned_lines

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
                # 按 - name: 切割
                chunks = re.split(r'-\s*name:', r.text)
                for c in chunks:
                    # 必须同时包含 server 和 type 才是真正的节点块
                    if "server:" in c and "type:" in c:
                        all_raw_chunks.append(c)
        except: continue

    # 按 Server 去重
    unique_dict = {}
    for chunk in all_raw_chunks:
        s_match = re.search(r'server:\s*([^\s]+)', chunk)
        if s_match: unique_dict[s_match.group(1)] = chunk
    
    unique_nodes = list(unique_dict.values())
    
    # 构造 YAML
    clash_config = [
        "port: 7890",
        "allow-lan: true",
        "mode: rule",
        "log-level: info",
        "proxies:"
    ]
    
    node_names = []
    for i, chunk in enumerate(unique_nodes):
        cleaned_attributes = clean_node_block(chunk)
        
        # 如果清洗后连 type 或 server 都不见了，说明是脏数据，跳过
        attr_str = "".join(cleaned_attributes)
        if "type" not in attr_str or "server" not in attr_str:
            continue

        name = f"Node_{len(node_names) + 1:02d}"
        node_names.append(name)
        
        clash_config.append(f"  - name: \"{name}\"")
        for attr in cleaned_attributes:
            clash_config.append(f"    {attr}")

    # 策略组
    clash_config.extend(["", "proxy-groups:", "  - name: 🚀 节点选择", "    type: select", "    proxies:"])
    clash_config.extend([f"      - \"{n}\"" for n in node_names])
    clash_config.extend(["      - DIRECT", "", "rules:", "  - MATCH,🚀 节点选择"])

    with open("config.yaml", "w", encoding="utf-8") as f:
        f.write("\n".join(clash_config))
    print(f"🎉 成功！已生成 {len(node_names)} 个纯净节点。")

if __name__ == "__main__":
    main()
