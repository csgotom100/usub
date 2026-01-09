import requests
import yaml
import base64
import os
import json
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode

def format_addr(addr):
    addr_str = str(addr).strip()
    if ":" in addr_str and "[" not in addr_str:
        return f"[{addr_str}]"
    return addr_str

def get_beijing_time():
    beijing_now = datetime.utcnow() + timedelta(hours=8)
    return beijing_now.strftime("%m-%d %H:%M")

def parse_content(content):
    nodes = []
    # --- 1. 尝试解析 JSON (Xray / Sing-box / Hy2) ---
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            # 针对 Xray/Sing-box 的 outbounds 结构
            if 'outbounds' in data:
                for out in data['outbounds']:
                    protocol = out.get('protocol') or out.get('type')
                    if protocol == 'vless':
                        # A. 尝试 Xray 路径: settings -> vnext
                        settings = out.get('settings', {})
                        vnext = settings.get('vnext', [{}])[0]
                        user = vnext.get('users', [{}])[0]
                        
                        # B. 尝试 Sing-box 路径 (直接在根部)
                        server = vnext.get('address') or out.get('server')
                        port = vnext.get('port') or out.get('server_port')
                        uuid = user.get('id') or out.get('uuid')

                        if not server or not port: continue

                        stream = out.get('streamSettings', {})
                        reality_x = stream.get('realitySettings', {})
                        reality_s = out.get('tls', {}).get('reality', {})
                        
                        nodes.append({
                            'name': out.get('tag', 'vless_node'),
                            'type': 'vless',
                            'server': server,
                            'port': port,
                            'uuid': uuid,
                            'network': stream.get('network') or out.get('transport', {}).get('type', 'tcp'),
                            'tls': True,
                            'servername': reality_x.get('serverName') or out.get('tls', {}).get('server_name', ''),
                            'reality-opts': {
                                'public-key': reality_x.get('publicKey') or reality_s.get('public_key', ''),
                                'short-id': reality_x.get('shortId') or reality_s.get('short_id', '')
                            },
                            'client-fingerprint': reality_x.get('fingerprint') or out.get('tls', {}).get('utls', {}).get('fingerprint', 'chrome')
                        })

            # 针对 Hysteria 2 官方 JSON
            if 'server' in data and 'auth' in data:
                s_raw = data['server'].split(',')[0]
                nodes.append({
                    'type': 'hysteria2',
                    'server': s_raw.rsplit(':', 1)[0],
                    'port': int(s_raw.rsplit(':', 1)[1]),
                    'password': data['auth'],
                    'sni': data.get('tls', {}).get('sni', 'apple.com')
                })
    except: pass

    # --- 2. 尝试解析 YAML (Clash) ---
    try:
        data = yaml.safe_load(content)
        if isinstance(data, dict) and 'proxies' in data:
            nodes.extend(data['proxies'])
    except: pass
    
    return nodes

def generate_uri(p):
    try:
        t = str(p.get('type', '')).lower()
        name = quote(str(p.get('name', 'node')))
        addr = format_addr(p.get('server', ''))
        port = p.get('port')
        if t == 'vless':
            ro = p.get('reality-opts', {})
            params = {
                "security": "reality",
                "sni": p.get('servername') or p.get('sni', ''),
                "pbk": ro.get('public-key', ''),
                "sid": ro.get('short-id', ''),
                "type": p.get('network', 'tcp'),
                "fp": p.get('client-fingerprint', 'chrome')
            }
            return f"vless://{p.get('uuid')}@{addr}:{port}?{urlencode({k: v for k, v in params.items() if v})}#{name}"
        elif t in ['hysteria2', 'hy2']:
            return f"hysteria2://{p.get('password', p.get('auth', ''))}@{addr}:{port}?sni={p.get('sni', '')}&insecure=1#{name}"
    except: return None

def main():
    all_p = []
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.startswith('http')]

    for url in urls:
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                all_p.extend(parse_content(r.text))
        except: continue

    # 深度去重
    unique = []
    seen = set()
    for p in all_p:
        # 指纹：IP + 端口 + (UUID或密码)
        fp = f"{p.get('server')}:{p.get('port')}:{p.get('uuid') or p.get('password')}"
        if fp not in seen:
            seen.add(fp)
            unique.append(p)

    # 重命名
    time_tag = get_beijing_time()
    for i, p in enumerate(unique):
        p_type = str(p.get('type', 'UNK')).upper()
        p['name'] = f"[{p_type}] {i+1:02d} ({time_tag})"

    # 输出 Clash 配置
    conf = {
        "port": 7890,
        "allow-lan": True,
        "mode": "rule",
        "proxies": unique,
        "proxy-groups": [
            {"name": "🚀 节点选择", "type": "select", "proxies": ["♻️ 自动选择"] + [p['name'] for p in unique] + ["DIRECT"]},
            {"name": "♻️ 自动选择", "type": "url-test", "url": "http://www.gstatic.com/generate_204", "interval": 300, "proxies": [p['name'] for p in unique]},
            {"name": "🎯 全球直连", "type": "select", "proxies": ["DIRECT", "🚀 节点选择"]}
        ],
        "rules": ["GEOIP,CN,🎯 全球直连", "MATCH,🚀 节点选择"]
    }
    
    with open('config.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(conf, f, allow_unicode=True, sort_keys=False)
    
    # 输出订阅文本
    uris = [generate_uri(p) for p in unique if generate_uri(p)]
    with open('sub.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(uris))
    with open('sub_base64.txt', 'w', encoding='utf-8') as f:
        f.write(base64.b64encode("\n".join(uris).encode('utf-8')).decode('utf-8'))

if __name__ == "__main__":
    main()
