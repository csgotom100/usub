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
        srv = item.get('server') or item.get('add') or item.get('address')
        if not srv or str(srv).startswith('127.'): return None
        
        # --- 核心修复：更健壮的 IPv6 分离逻辑 ---
        srv = str(srv).strip()
        port = str(item.get('port') or item.get('server_port') or "")
        
        # 如果 server 包含多个冒号且没有带中括号，或者是你遇到的残缺格式
        if srv.count(':') > 1 and not srv.startswith('['):
            if srv.endswith(':'): # 修复 2001:xxx: 这种残缺格式
                srv = srv + "1"
            # 如果端口不在 port 字段而在 server 字段里
            if not port and not any(c.isalpha() for c in srv.split(':')[-1]):
                srv, port = srv.rsplit(':', 1)

        port = re.findall(r'\d+', port)[0] if re.findall(r'\d+', port) else ""
        if not port: return None

        pw = item.get('auth') or item.get('password') or item.get('uuid') or item.get('id')
        if not pw: return None
        
        tls = item.get('tls', {}) if isinstance(item.get('tls'), dict) else {}
        sni = item.get('servername') or item.get('sni') or tls.get('server_name') or ""
        pbk = item.get('public-key') or item.get('public_key') or tls.get('reality', {}).get('public_key') or item.get('reality-opts', {}).get('public-key') or ""
        sid = item.get('short-id') or item.get('short_id') or tls.get('reality', {}).get('short_id') or item.get('reality-opts', {}).get('short-id') or ""

        path = ""
        for k in ['path', 'xhttp-opts', 'xhttpSettings', 'transport']:
            v = item.get(k)
            if isinstance(v, str) and v.startswith('/'): path = v
            elif isinstance(v, dict) and v.get('path'): path = v.get('path')
        
        flow = item.get('flow') or ""

        p_raw = str(item.get('type') or item.get('protocol') or "").lower()
        if 'hy2' in p_raw or 'hysteria2' in p_raw or 'auth' in item: p = 'hysteria2'
        elif 'tuic' in p_raw: p = 'tuic'
        elif 'anytls' in p_raw: p = 'anytls'
        else: p = 'vless'

        return {
            "server": srv.strip('[]'), "port": port, "type": p, "pw": pw,
            "sni": sni, "pbk": pbk, "sid": sid, "path": path, "flow": flow,
            "name": item.get('tag') or item.get('name') or ""
        }
    except: return None

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
            def walk(obj):
                if isinstance(obj, dict):
                    res = get_node_info(obj)
                    if res: nodes.append(res)
                    for v in obj.values(): walk(v)
                elif isinstance(obj, list):
                    for i in obj: walk(i)
            walk(data)
        except: continue

    unique = []
    seen = set()
    for n in nodes:
        key = f"{n['server']}:{n['port']}:{n['type']}:{n['path']}"
        if key not in seen:
            unique.append(n); seen.add(key)

    unique.sort(key=lambda x: 0 if x['type'] == 'anytls' else 1)
    uris = []
    clash_proxies = []
    time_tag = get_beijing_time()
    
    for i, n in enumerate(unique, 1):
        geo = get_geo_tag(n['name'] + n['sni'] + n['server'], n['server'])
        name = f"{geo}[{n['type'].upper()}] {i:02d} ({time_tag})"
        name_enc = urllib.parse.quote(name)
        srv_uri = f"[{n['server']}]" if ':' in n['server'] else n['server']
        
        if n['type'] == 'vless':
            params = {"security": "reality" if n['pbk'] else "none", "sni": n['sni'] or "apple.com", "pbk": n['pbk'], "sid": n['sid'], "flow": n['flow']}
            if n['path']: params.update({"type": "xhttp", "path": n['path']})
            uris.append(f"vless://{n['pw']}@{srv_uri}:{n['port']}?{urllib.parse.urlencode({k:v for k,v in params.items() if v})}#{name_enc}")
        elif n['type'] == 'hysteria2':
            uris.append(f"hysteria2://{n['pw']}@{srv_uri}:{n['port']}?insecure=1&sni={n['sni'] or 'apple.com'}#{name_enc}")
        elif n['type'] == 'anytls':
            uris.append(f"anytls://{n['pw']}@{srv_uri}:{n['port']}?alpn=h3&insecure=1#{name_enc}")
        elif n['type'] == 'tuic':
            uris.append(f"tuic://{n['pw']}@{srv_uri}:{n['port']}?sni={n['sni'] or 'apple.com'}&alpn=h3#{name_enc}")

        if n['type'] in ['vless', 'hysteria2', 'tuic']:
            p = {"name": name, "server": n['server'], "port": int(n['port'])}
            if n['type'] == 'vless':
                p.update({"type": "vless", "uuid": n['pw'], "tls": True, "servername": n['sni'] or "apple.com", "network": "xhttp" if n['path'] else "tcp", "udp": True})
                if n['pbk']: p.update({"reality-opts": {"public-key": n['pbk'], "short-id": n['sid']}})
                if n['path']: p.update({"xhttp-opts": {"path": n['path'], "mode": "auto"}})
            elif n['type'] == 'hysteria2':
                p.update({"type": "hysteria2", "password": n['pw'], "sni": n['sni'] or "apple.com", "skip-cert-verify": True})
            elif n['type'] == 'tuic':
                p.update({"type": "tuic", "uuid": n['pw'], "sni": n['sni'] or "apple.com", "alpn": ["h3"]})
            clash_proxies.append(p)

    with open("sub.txt", "w", encoding="utf-8") as f: f.write("\n".join(uris))
    with open("sub_base64.txt", "w", encoding="utf-8") as f:
        f.write(base64.b64encode("\n".join(uris).encode()).decode())
    
    # --- 核心修复：Clash 配置增加 ipv6 开关 ---
    clash_config = {
        "ipv6": True, # 强制开启 IPv6 支持
        "proxies": clash_proxies,
        "proxy-groups": [
            {"name": "🚀 节点选择", "type": "select", "proxies": ["♻️ 自动选择", "DIRECT"] + [p['name'] for p in clash_proxies]},
            {"name": "♻️ 自动选择", "type": "url-test", "url": "http://www.gstatic.com/generate_204", "interval": 300, "proxies": [p['name'] for p in clash_proxies]}
        ],
        "rules": ["MATCH,🚀 节点选择"]
    }
    with open("config.yaml", "w", encoding="utf-8") as f:
        yaml.dump(clash_config, f, allow_unicode=True, sort_keys=False)

if __name__ == "__main__":
    main()
