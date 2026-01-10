import json, requests, base64, yaml, urllib.parse, os, re, warnings
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

def get_beijing_time():
    return (datetime.utcnow() + timedelta(hours=8)).strftime("%m-%d %H:%M")

def get_geo_tag(text, server):
    words = {"🇭🇰": ["hk", "香港"], "🇺🇸": ["us", "美国"], "🇯🇵": ["jp", "日本"], "🇸🇬": ["sg", "新加坡"], "🇹🇼": ["tw", "台湾"]}
    content = str(text).lower() + str(server).lower()
    for tag, keys in words.items():
        if any(k in content for k in keys): return tag
    return "🌐"

def get_node_info(item):
    try:
        if not isinstance(item, dict): return None
        
        # 1. 核心修复：处理 "IP:PORT,PORT-PORT" 这种复杂格式
        raw_server = item.get('server') or item.get('add') or item.get('address')
        if not raw_server or str(raw_server).startswith('127.'): return None
        
        srv = str(raw_server).strip()
        port = str(item.get('port') or "")

        # 如果 server 字段里包含冒号（即 IP:Port 格式）
        if ':' in srv:
            # 针对 IPv6 的特殊处理
            if srv.startswith('['):
                srv_part, port_part = srv.split(']:', 1)
                srv = srv_part.replace('[', '')
                port = port_part
            else:
                # 针对你提供的 157.254.223.43:27921,28000-29000
                # 取第一个冒号后的内容作为端口，冒号前的作为 IP
                srv, port = srv.split(':', 1)
        
        # 端口清洗：只取第一个数字作为主端口（例如 27921）
        port = re.findall(r'\d+', str(port))[0] if re.findall(r'\d+', str(port)) else "443"

        # 2. 协议判定
        item_raw = str(item).lower()
        # 只要包含 auth 和 bandwidth，或者明确写了 hysteria，就是 HY2
        if 'auth' in item and 'bandwidth' in item or 'hysteria2' in item_raw:
            p = 'hysteria2'
        elif 'tuic' in item_raw:
            p = 'tuic'
        elif 'anytls' in item_raw:
            p = 'anytls'
        else:
            p = 'vless'

        # 3. 提取密码
        pw = item.get('auth') or item.get('password') or item.get('uuid') or item.get('id')
        if not pw and p != 'anytls': return None

        # 4. 提取 TLS/SNI
        tls = item.get('tls', {}) if isinstance(item.get('tls'), dict) else {}
        sni = item.get('servername') or item.get('sni') or tls.get('sni') or tls.get('server_name') or ""
        
        return {
            "server": srv.strip('[]'), "port": port, "type": p, "pw": pw,
            "sni": sni, "name": item.get('tag') or item.get('name') or ""
        }
    except Exception as e:
        return None

def main():
    nodes = []
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]

    for url in urls:
        try:
            r = requests.get(url, timeout=15, verify=False)
            content = r.text.strip()
            data = json.loads(content) if content.startswith(('{', '[')) else yaml.safe_load(content)
            
            # 这里是处理你这种单个 JSON 对象的关键
            def walk(obj):
                if isinstance(obj, dict):
                    res = get_node_info(obj)
                    if res: nodes.append(res)
                    # 只有当它不是我们要找的节点时，才继续往深层走
                    if not res:
                        for v in obj.values(): walk(v)
                elif isinstance(obj, list):
                    for i in obj: walk(i)
            
            walk(data)
        except: continue

    # 去重
    unique = []
    seen = set()
    for n in nodes:
        key = f"{n['server']}:{n['port']}:{n['type']}"
        if key not in seen:
            unique.append(n); seen.add(key)

    unique.sort(key=lambda x: 0 if x['type'] == 'anytls' else (1 if x['type'] == 'hysteria2' else 2))

    uris = []
    clash_proxies = []
    time_tag = get_beijing_time()
    
    for i, n in enumerate(unique, 1):
        geo = get_geo_tag(n['name'] + n['sni'] + n['server'], n['server'])
        name = f"{geo}[{n['type'].upper()}] {i:02d} ({time_tag})"
        name_enc = urllib.parse.quote(name)
        srv_uri = f"[{n['server']}]" if ':' in n['server'] else n['server']
        
        if n['type'] == 'hysteria2':
            uris.append(f"hysteria2://{n['pw']}@{srv_uri}:{n['port']}?insecure=1&sni={n['sni'] or 'apple.com'}#{name_enc}")
        elif n['type'] == 'vless':
            uris.append(f"vless://{n['pw']}@{srv_uri}:{n['port']}?security=none&sni={n['sni'] or 'apple.com'}#{name_enc}")
        elif n['type'] == 'tuic':
            uris.append(f"tuic://{n['pw']}@{srv_uri}:{n['port']}?sni={n['sni'] or 'apple.com'}&alpn=h3#{name_enc}")
        elif n['type'] == 'anytls':
            uris.append(f"anytls://{n['pw']}@{srv_uri}:{n['port']}?alpn=h3&insecure=1#{name_enc}")

        if n['type'] in ['vless', 'hysteria2', 'tuic']:
            p = {"name": name, "server": n['server'], "port": int(n['port'])}
            if n['type'] == 'hysteria2':
                p.update({"type": "hysteria2", "password": n['pw'], "sni": n['sni'] or "apple.com", "skip-cert-verify": True})
            elif n['type'] == 'vless':
                p.update({"type": "vless", "uuid": n['pw'], "tls": False, "servername": n['sni'] or "apple.com"})
            elif n['type'] == 'tuic':
                p.update({"type": "tuic", "uuid": n['pw'], "sni": n['sni'] or "apple.com", "alpn": ["h3"]})
            clash_proxies.append(p)

    with open("sub.txt", "w", encoding="utf-8") as f: f.write("\n".join(uris))
    with open("sub_base64.txt", "w", encoding="utf-8") as f:
        f.write(base64.b64encode("\n".join(uris).encode()).decode())
    
    clash_config = {"ipv6": True, "proxies": clash_proxies, "proxy-groups": [{"name": "🚀 节点选择", "type": "select", "proxies": ["♻️ 自动选择", "DIRECT"] + [p['name'] for p in clash_proxies]}], "rules": ["MATCH,🚀 节点选择"]}
    with open("config.yaml", "w", encoding="utf-8") as f:
        yaml.dump(clash_config, f, allow_unicode=True, sort_keys=False)

if __name__ == "__main__":
    main()
