import requests, yaml, base64, os, json, re
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode

def get_beijing_time():
    return (datetime.utcnow() + timedelta(hours=8)).strftime("%m-%d %H:%M")

def get_region_tag(ip):
    """根据IP获取简易地理位置标识 (内置常用网段识别)"""
    try:
        # 这里可以使用简单的IP段判断，或者调用公开API(考虑到Action环境，建议简单判断或默认UN)
        # 为保证速度，这里默认返回类型标识，如需精准归属地可考虑集成微型GeoIP库
        return "" 
    except: return ""

def parse_content(content):
    nodes = []
    # --- 策略 A: JSON 解析 ---
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            outbounds = data.get('outbounds', [])
            for out in outbounds:
                protocol = out.get('protocol') or out.get('type')
                tag = out.get('tag', protocol)
                
                # VLESS
                if protocol == 'vless':
                    settings = out.get('settings', {})
                    vnext = settings.get('vnext', [{}])[0]
                    u = vnext.get('users', [{}])[0]
                    s = out.get('streamSettings', {})
                    r = s.get('realitySettings', {}) or out.get('tls', {}).get('reality', {})
                    xh = s.get('xhttpSettings', {})
                    nodes.append({
                        'name': tag, 'type': 'vless', 'server': vnext.get('address') or out.get('server'),
                        'port': vnext.get('port') or out.get('server_port'), 'uuid': u.get('id') or out.get('uuid'),
                        'flow': u.get('flow', ''), 'network': s.get('network') or 'tcp',
                        'servername': r.get('serverName') or out.get('tls', {}).get('server_name', ''),
                        'reality-opts': {'public-key': r.get('publicKey') or r.get('public_key', ''), 'short-id': r.get('shortId') or r.get('short_id', '')},
                        'xhttp-opts': {'path': xh.get('path', ''), 'mode': xh.get('mode', 'auto')},
                        'client-fingerprint': r.get('fingerprint', 'chrome')
                    })
                
                # Hysteria2
                elif protocol in ['hysteria2', 'hy2']:
                    nodes.append({
                        'name': tag, 'type': 'hysteria2', 'server': out.get('server') or out.get('settings', {}).get('server'),
                        'port': out.get('port') or out.get('server_port'),
                        'password': out.get('settings', {}).get('auth') or out.get('password'),
                        'sni': out.get('tls', {}).get('server_name') or out.get('sni', 'apple.com')
                    })
                
                # TUIC
                elif protocol == 'tuic':
                    settings = out.get('settings', {})
                    vnext = settings.get('vnext', [{}])[0]
                    u = vnext.get('users', [{}])[0]
                    nodes.append({
                        'name': tag, 'type': 'tuic', 'server': vnext.get('address') or out.get('server'),
                        'port': vnext.get('port') or out.get('server_port'),
                        'uuid': u.get('uuid') or u.get('id'), 'password': u.get('password'),
                        'alpn': out.get('streamSettings', {}).get('tlsSettings', {}).get('alpn', ['h3']),
                        'sni': out.get('streamSettings', {}).get('tlsSettings', {}).get('serverName', '')
                    })
    except: pass

    # --- 策略 B: YAML 解析 (针对 AnyTLS/Clash) ---
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
        addr, port = p.get('server'), p.get('port')
        if t == 'vless':
            ro, xh = p.get('reality-opts', {}), p.get('xhttp-opts', {})
            params = {"security": "reality", "sni": p.get('servername') or p.get('sni'), "pbk": ro.get('public-key'), "sid": ro.get('short-id'), "type": p.get('network'), "flow": p.get('flow'), "fp": p.get('client-fingerprint', 'chrome')}
            if p.get('network') == 'xhttp' and xh:
                params["path"] = xh.get('path'); params["mode"] = xh.get('mode', 'auto')
            return f"vless://{p.get('uuid')}@{addr}:{port}?{urlencode({k:v for k,v in params.items() if v})}#{name}"
        elif t in ['hysteria2', 'hy2']:
            pw = p.get('password') or p.get('auth')
            return f"hysteria2://{pw}@{addr}:{port}?insecure=1&sni={p.get('sni','')}#{name}"
        elif t == 'tuic':
            uuid = p.get('uuid') or p.get('password')
            return f"tuic://{uuid}@{addr}:{port}?sni={p.get('sni','')}&alpn={','.join(p.get('alpn', []))}#{name}"
        elif t == 'anytls':
            params = {"alpn": ",".join(p.get('alpn', [])), "insecure": "1"}
            return f"anytls://{p.get('password')}@{addr}:{port}?{urlencode(params)}#{name}"
    except: return None

def main():
    all_nodes = []
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.startswith('http')]

    for url in urls:
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200: all_nodes.extend(parse_content(r.text))
        except: continue

    unique = []
    seen = set()
    for p in all_nodes:
        fp = f"{p.get('type')}:{p.get('server')}:{p.get('port')}:{p.get('uuid') or p.get('password') or p.get('auth')}"
        if fp not in seen:
            seen.add(fp); unique.append(p)

    # 排序：Anytls > VLESS > Hy2 > TUIC
    unique.sort(key=lambda x: 0 if x.get('type')=='anytls' else (1 if x.get('type')=='vless' else 2))

    time_tag = get_beijing_time()
    for i, p in enumerate(unique):
        # 加上简单的协议前缀和编号，并保留时间
        p['name'] = f"[{str(p.get('type','')).upper()}] {i+1:02d}-{time_tag}"

    node_names = [x['name'] for x in unique]
    # Clash 配置 (修复循环引用)
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

if __name__ == "__main__": main()
