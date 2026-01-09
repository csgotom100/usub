import requests, yaml, base64, os, json
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode

def get_beijing_time():
    return (datetime.utcnow() + timedelta(hours=8)).strftime("%m-%d %H:%M")

def parse_content(content):
    nodes = []
    # 策略 A: 深度解析 JSON (针对 Xray/Sing-box)
    try:
        data = json.loads(content)
        if isinstance(data, dict) and 'outbounds' in data:
            for out in data['outbounds']:
                if out.get('protocol') == 'vless':
                    v = out.get('settings', {}).get('vnext', [{}])[0]
                    u = v.get('users', [{}])[0]
                    s = out.get('streamSettings', {})
                    r = s.get('realitySettings', {})
                    xh = s.get('xhttpSettings', {})
                    
                    nodes.append({
                        'name': out.get('tag', 'vless'),
                        'type': 'vless',
                        'server': v.get('address'),
                        'port': v.get('port'),
                        'uuid': u.get('id'), # 提取超长ID
                        'flow': u.get('flow', ''), # 提取流控 xtls-rprx-vision
                        'network': s.get('network', 'tcp'),
                        'servername': r.get('serverName', ''),
                        'reality-opts': {'public-key': r.get('publicKey', ''), 'short-id': r.get('shortId', '')},
                        'xhttp-opts': {'path': xh.get('path', ''), 'mode': xh.get('mode', 'auto')},
                        'client-fingerprint': r.get('fingerprint', 'chrome')
                    })
    except: pass

    # 策略 B: 解析 YAML (针对 AnyTLS/Clash)
    try:
        y = yaml.safe_load(content)
        if isinstance(y, dict) and 'proxies' in y:
            nodes.extend(y['proxies'])
    except: pass
    return nodes

def generate_uri(p):
    try:
        n, addr, port = quote(p.get('name', 'node')), p.get('server'), p.get('port')
        if p.get('type') == 'vless':
            ro, xh = p.get('reality-opts', {}), p.get('xhttp-opts', {})
            # 这里的参数名必须严格对应 v2rayN 的识别逻辑
            params = {
                "security": "reality",
                "sni": p.get('servername') or p.get('sni'),
                "pbk": ro.get('public-key'),
                "sid": ro.get('short-id'),
                "type": p.get('network'),
                "flow": p.get('flow'), # 确保流控写入 URI
                "fp": p.get('client-fingerprint', 'chrome')
            }
            if p.get('network') == 'xhttp' and xh:
                params["path"] = xh.get('path')
                params["mode"] = xh.get('mode', 'auto')
            
            # 过滤空值并合并
            query = urlencode({k: v for k, v in params.items() if v})
            return f"vless://{p.get('uuid')}@{addr}:{port}?{query}#{n}"
        elif p.get('type') in ['hysteria2', 'hy2']:
            auth = p.get('password') or p.get('auth')
            return f"hysteria2://{auth}@{addr}:{port}?insecure=1&sni={p.get('sni','')}#{n}"
        elif p.get('type') == 'anytls':
            params = {"alpn": ",".join(p.get('alpn', [])), "insecure": "1"}
            return f"anytls://{p.get('password')}@{addr}:{port}?{urlencode(params)}#{n}"
    except: return None

def main():
    all_p = []
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]
    
    for url in urls:
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200: all_p.extend(parse_content(r.text))
        except: continue

    unique = []
    seen = set()
    for p in all_p:
        fp = f"{p.get('server')}:{p.get('port')}:{p.get('uuid') or p.get('password')}"
        if fp not in seen:
            seen.add(fp); unique.append(p)

    time_tag = get_beijing_time()
    for i, p in enumerate(unique):
        p['name'] = f"[{str(p.get('type','')).upper()}] {i+1:02d} ({time_tag})"

    node_names = [x['name'] for x in unique]
    
    # 彻底解决 Clash 循环报错逻辑
    clash_conf = {
        "proxies": unique,
        "proxy-groups": [
            {"name": "🚀 节点选择", "type": "select", "proxies": ["♻️ 自动选择", "DIRECT"] + node_names},
            {"name": "♻️ 自动选择", "type": "url-test", "url": "http://www.gstatic.com/generate_204", "interval": 300, "proxies": node_names},
            {"name": "🎯 全球直连", "type": "select", "proxies": ["DIRECT", "🚀 节点选择"]}
        ],
        "rules": ["GEOIP,CN,🎯 全球直连", "MATCH,🚀 节点选择"]
    }

    with open('config.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(clash_conf, f, allow_unicode=True, sort_keys=False)
    
    uris = [generate_uri(p) for p in unique if generate_uri(p)]
    with open('sub.txt', 'w', encoding='utf-8') as f: f.write("\n".join(uris))
    with open('sub_base64.txt', 'w', encoding='utf-8') as f:
        f.write(base64.b64encode("\n".join(uris).encode()).decode())

if __name__ == "__main__": main()
