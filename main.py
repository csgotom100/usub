import requests, yaml, base64, os, json
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode

def get_beijing_time():
    return (datetime.utcnow() + timedelta(hours=8)).strftime("%m-%d %H:%M")

def get_country_code(ip):
    """获取IP归属地标识"""
    try:
        # 使用 ip-api.com 的批量接口或单个接口，这是目前 Action 环境最稳的
        r = requests.get(f"http://ip-api.com/json/{ip}?fields=countryCode", timeout=3)
        code = r.json().get('countryCode', 'UN')
        # 转换一些常见的国旗图标 (可选)
        flags = {"HK": "🇭🇰", "US": "🇺🇸", "JP": "🇯🇵", "SG": "🇸🇬", "TW": "🇹🇼", "CN": "🇨🇳", "KR": "🇰🇷"}
        return f"{flags.get(code, code)} "
    except:
        return "🌐 "

def parse_content(content):
    nodes = []
    # --- 策略 A: 深度 JSON 扫描 ---
    try:
        data = json.loads(content)
        # 兼容模式：如果是个列表，直接遍历；如果是个字典，看 outbounds
        items = data.get('outbounds', []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        
        # 处理单节点 Hysteria2 格式
        if isinstance(data, dict) and 'server' in data and 'auth' in data:
            items.append(data)

        for out in items:
            p = out.get('protocol') or out.get('type')
            tag = out.get('tag', p)
            
            if p == 'vless':
                s = out.get('streamSettings', {})
                v = out.get('settings', {}).get('vnext', [{}])[0]
                u = v.get('users', [{}])[0] if v.get('users') else out.get('settings', {}).get('users', [{}])[0]
                r = s.get('realitySettings') or out.get('tls', {}).get('reality', {})
                xh = s.get('xhttpSettings', {})
                nodes.append({
                    'type': 'vless', 'server': v.get('address') or out.get('server'),
                    'port': v.get('port') or out.get('server_port'), 'uuid': u.get('id') or out.get('uuid'),
                    'flow': u.get('flow', ''), 'network': s.get('network') or 'tcp',
                    'servername': r.get('serverName') or out.get('tls', {}).get('server_name', ''),
                    'reality-opts': {'public-key': r.get('publicKey') or r.get('public_key', ''), 'short-id': r.get('shortId') or r.get('short_id', '')},
                    'xhttp-opts': {'path': xh.get('path', ''), 'mode': xh.get('mode', 'auto')},
                    'client-fingerprint': r.get('fingerprint', 'chrome')
                })
            elif p in ['hysteria2', 'hy2']:
                nodes.append({
                    'type': 'hysteria2', 'server': out.get('server') or out.get('settings', {}).get('server'),
                    'port': out.get('port') or out.get('server_port'),
                    'password': out.get('password') or out.get('settings', {}).get('auth'),
                    'sni': out.get('sni') or out.get('tls', {}).get('server_name') or 'apple.com'
                })
            elif p == 'tuic':
                v = out.get('settings', {}).get('vnext', [{}])[0]
                u = v.get('users', [{}])[0]
                nodes.append({
                    'type': 'tuic', 'server': v.get('address') or out.get('server'),
                    'port': v.get('port') or out.get('server_port'),
                    'uuid': u.get('uuid') or u.get('id'), 'password': u.get('password'),
                    'sni': out.get('streamSettings', {}).get('tlsSettings', {}).get('serverName', ''),
                    'alpn': ['h3']
                })
    except: pass

    # --- 策略 B: YAML 解析 ---
    try:
        y = yaml.safe_load(content)
        if isinstance(y, dict) and 'proxies' in y: nodes.extend(y['proxies'])
    except: pass
    return nodes

def generate_uri(p):
    try:
        t, addr, port = p.get('type').lower(), p.get('server'), p.get('port')
        name = quote(p.get('name', 'node'))
        if t == 'vless':
            ro, xh = p.get('reality-opts', {}), p.get('xhttp-opts', {})
            params = {"security": "reality", "sni": p.get('servername'), "pbk": ro.get('public-key'), "sid": ro.get('short-id'), "type": p.get('network'), "flow": p.get('flow'), "fp": p.get('client-fingerprint')}
            if p.get('network') == 'xhttp': params["path"] = xh.get('path'); params["mode"] = xh.get('mode')
            return f"vless://{p.get('uuid')}@{addr}:{port}?{urlencode({k:v for k,v in params.items() if v})}#{name}"
        elif t in ['hysteria2', 'hy2']:
            return f"hysteria2://{p.get('password')}@{addr}:{port}?insecure=1&sni={p.get('sni', '')}#{name}"
        elif t == 'tuic':
            val = p.get('uuid') or p.get('password')
            return f"tuic://{val}@{addr}:{port}?sni={p.get('sni', '')}&alpn=h3#{name}"
        elif t == 'anytls':
            return f"anytls://{p.get('password')}@{addr}:{port}?alpn=h3&insecure=1#{name}"
    except: return None

def main():
    all_nodes = []
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]

    for url in urls:
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200: all_nodes.extend(parse_content(r.text))
        except: continue

    unique = []
    seen = set()
    for p in all_nodes:
        fp = f"{p.get('server')}:{p.get('port')}"
        if fp not in seen:
            seen.add(fp); unique.append(p)

    time_tag = get_beijing_time()
    for i, p in enumerate(unique):
        # 加上地理标志 (注意：这会增加运行时间，如果节点太多建议只取前20个查询)
        region = get_country_code(p.get('server')) if i < 30 else "🌐 "
        p['name'] = f"{region}[{p.get('type').upper()}] {i+1:02d} ({time_tag})"

    # Clash & Sub 生成 (逻辑同前，修复循环)
    node_names = [x['name'] for x in unique]
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
