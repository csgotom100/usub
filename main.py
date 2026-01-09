import requests, yaml, base64, os, json
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode

def get_beijing_time():
    return (datetime.utcnow() + timedelta(hours=8)).strftime("%m-%d %H:%M")

def parse_content(content):
    nodes = []
    # --- 策略 A: 深度解析 JSON (不设限提取) ---
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            # 1. 解析 Xray 标准/非标准 Outbounds
            outbounds = data.get('outbounds', [])
            for out in outbounds:
                protocol = out.get('protocol') or out.get('type')
                tag = out.get('tag', protocol)
                
                # VLESS 提取逻辑
                if protocol == 'vless':
                    settings = out.get('settings', {})
                    vnext = settings.get('vnext', [{}])[0]
                    user = vnext.get('users', [{}])[0]
                    stream = out.get('streamSettings', {})
                    reality = stream.get('realitySettings', {}) or out.get('tls', {}).get('reality', {})
                    xh = stream.get('xhttpSettings', {})
                    
                    nodes.append({
                        'name': tag,
                        'type': 'vless',
                        'server': vnext.get('address') or out.get('server'),
                        'port': vnext.get('port') or out.get('server_port'),
                        'uuid': user.get('id') or out.get('uuid'),
                        'flow': user.get('flow', ''),
                        'network': stream.get('network') or out.get('transport', {}).get('type', 'tcp'),
                        'servername': reality.get('serverName') or out.get('tls', {}).get('server_name', ''),
                        'reality-opts': {'public-key': reality.get('publicKey') or reality.get('public_key', ''), 'short-id': reality.get('shortId') or reality.get('short_id', '')},
                        'xhttp-opts': {'path': xh.get('path', ''), 'mode': xh.get('mode', 'auto')},
                        'client-fingerprint': reality.get('fingerprint', 'chrome')
                    })
                
                # Hysteria2 提取逻辑
                elif protocol in ['hysteria2', 'hy2']:
                    nodes.append({
                        'name': tag,
                        'type': 'hysteria2',
                        'server': out.get('server') or out.get('settings', {}).get('server'),
                        'port': out.get('port') or out.get('server_port'),
                        'password': out.get('settings', {}).get('auth') or out.get('password'),
                        'sni': out.get('tls', {}).get('server_name') or out.get('sni', 'apple.com')
                    })

            # 2. 额外处理 Hysteria2 官方单节点格式
            if 'server' in data and 'auth' in data and 'outbounds' not in data:
                s_raw = data['server'].split(',')[0]
                nodes.append({
                    'type': 'hysteria2',
                    'server': s_raw.rsplit(':', 1)[0],
                    'port': int(s_raw.rsplit(':', 1)[1]),
                    'password': data['auth'],
                    'sni': data.get('tls', {}).get('sni', 'apple.com')
                })
    except: pass

    # --- 策略 B: 解析 YAML (AnyTLS/Clash) ---
    try:
        y_data = yaml.safe_load(content)
        if isinstance(y_data, dict) and 'proxies' in y_data:
            nodes.extend(y_data['proxies'])
    except: pass
    
    return nodes

def generate_uri(p):
    try:
        t = str(p.get('type', '')).lower()
        name = quote(str(p.get('name', 'node')))
        addr = p.get('server')
        port = p.get('port')
        if t == 'vless':
            ro, xh = p.get('reality-opts', {}), p.get('xhttp-opts', {})
            params = {
                "security": "reality", "sni": p.get('servername') or p.get('sni'),
                "pbk": ro.get('public-key'), "sid": ro.get('short-id'),
                "type": p.get('network'), "flow": p.get('flow'), "fp": p.get('client-fingerprint', 'chrome')
            }
            if p.get('network') == 'xhttp' and xh:
                params["path"] = xh.get('path')
                params["mode"] = xh.get('mode', 'auto')
            return f"vless://{p.get('uuid')}@{addr}:{port}?{urlencode({k:v for k,v in params.items() if v})}#{name}"
        elif t in ['hysteria2', 'hy2']:
            pw = p.get('password') or p.get('auth')
            return f"hysteria2://{pw}@{addr}:{port}?insecure=1&sni={p.get('sni','')}#{name}"
        elif t == 'anytls':
            params = {"alpn": ",".join(p.get('alpn', [])), "insecure": "1"}
            return f"anytls://{p.get('password')}@{addr}:{port}?{urlencode(params)}#{name}"
    except: return None
    return None

def main():
    all_nodes = []
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.startswith('http')]

    for url in urls:
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                all_nodes.extend(parse_content(r.text))
        except: continue

    # 深度去重
    unique = []
    seen = set()
    for p in all_nodes:
        # 指纹：协议+IP+端口+核心凭据
        fp = f"{p.get('type')}:{p.get('server')}:{p.get('port')}:{p.get('uuid') or p.get('password')}"
        if fp not in seen:
            seen.add(fp); unique.append(p)

    # 排序：Anytls 优先，接着 VLESS，最后其他
    unique.sort(key=lambda x: 0 if x.get('type')=='anytls' else 1)

    time_tag = get_beijing_time()
    for i, p in enumerate(unique):
        p['name'] = f"[{str(p.get('type','')).upper()}] {i+1:02d} ({time_tag})"

    # Clash 配置 (修复循环引用)
    node_names = [x['name'] for x in unique]
    conf = {
        "proxies": unique,
        "proxy-groups": [
            {"name": "🚀 节点选择", "type": "select", "proxies": ["♻️ 自动选择", "DIRECT"] + node_names},
            {"name": "♻️ 自动选择", "type": "url-test", "url": "http://www.gstatic.com/generate_204", "interval": 300, "proxies": node_names},
            {"name": "🎯 全球直连", "type": "select", "proxies": ["DIRECT", "🚀 节点选择"]}
        ],
        "rules": ["GEOIP,CN,🎯 全球直连", "MATCH,🚀 节点选择"]
    }
    
    with open('config.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(conf, f, allow_unicode=True, sort_keys=False)
    
    uris = [generate_uri(p) for p in unique if generate_uri(p)]
    with open('sub.txt', 'w', encoding='utf-8') as f: f.write("\n".join(uris))
    with open('sub_base64.txt', 'w', encoding='utf-8') as f:
        f.write(base64.b64encode("\n".join(uris).encode()).decode())

if __name__ == "__main__":
    main()
