import requests
import os
import re

def main():
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]

    headers = {'User-Agent': 'clash-verge/1.0'}
    node_list = []

    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                # 提取节点块
                chunks = re.split(r'-\s*name:', r.text)
                for c in chunks:
                    if "server:" in c and "type:" in c:
                        # 简单的提取逻辑
                        d = {}
                        for line in c.splitlines():
                            if ':' in line:
                                k, v = line.split(':', 1)
                                d[k.strip().lower()] = v.strip()
                        if d: node_list.append(d)
        except: continue

    # 构造最终内容
    out = [
        "port: 7890",
        "allow-lan: true",
        "mode: rule",
        "log-level: info",
        "proxies:"
    ]

    names = []
    for i, n in enumerate(node_list):
        name = f"Node_{i+1:02d}"
        names.append(name)
        tp = n.get('type', '')
        
        # 强制格式化每个节点块
        out.append(f'  - name: "{name}"')
        out.append(f'    type: {tp}')
        out.append(f'    server: {n.get("server")}')
        out.append(f'    port: {n.get("port")}')

        # 针对不同协议补全必填参数
        if "hysteria" in tp:
            out.append(f'    auth-str: {n.get("auth-str", n.get("password", "dongtaiwang.com"))}')
            out.append(f'    sni: {n.get("sni", "apple.com")}')
            out.append(f'    skip-cert-verify: true')
            out.append(f'    alpn: [h3]')
            out.append(f'    protocol: udp')
            out.append(f'    up: "11 Mbps"')
            out.append(f'    down: "55 Mbps"')
        
        elif tp == "vless":
            out.append(f'    uuid: {n.get("uuid")}')
            out.append(f'    tls: true')
            out.append(f'    reality-opts:')
            out.append(f'      public-key: {n.get("public-key", "IXcXrT_Y0ATTZlGOhPnSmKo-cuGr4yMKV9Rz4-nA3yU")}')
            out.append(f'      short-id: {n.get("short-id", "8ef4455ba637425b")}')
        
        elif tp == "tuic":
            out.append(f'    uuid: {n.get("uuid")}')
            out.append(f'    password: {n.get("password", "dongtaiwang.com")}')
            out.append(f'    username: {n.get("uuid", "default")}')
            out.append(f'    alpn: [h3]')
            out.append(f'    reduce-rtt: true')

        elif tp == "mieru":
            out.append(f'    password: {n.get("password", "dongtaiwang.com")}')
            out.append(f'    transport: tcp')

    # 策略组
    out.extend(["", "proxy-groups:", "  - name: 🚀 节点选择", "    type: select", "    proxies:"])
    for name in names:
        out.append(f'      - "{name}"')
    out.append("      - DIRECT")

    # 规则
    out.extend(["", "rules:", "  - DOMAIN-SUFFIX,google.com,🚀 节点选择", "  - MATCH,🚀 节点选择"])

    with open("config.yaml", "w", encoding="utf-8") as f:
        f.write("\n".join(out))

if __name__ == "__main__":
    main()
