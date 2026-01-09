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
    try:
        data = json.loads(content)
        # sing-box 格式
        if isinstance(data, dict) and 'outbounds' in data:
            for out in data['outbounds']:
                if out.get('type') == 'vless':
                    tls = out.get('tls', {})
                    reality = tls.get('reality', {})
                    nodes.append({
                        'name': out.get('tag', 'vless_node'),
                        'type': 'vless',
                        'server': out.get('server'),
                        'port': out.get('server_port'),
                        'uuid': out.get('uuid'),
                        'servername': tls.get('server_name', ''),
                        'reality-opts': {'public-key': reality.get('public_key', ''), 'short-id': reality.get('short_id', '')},
                        'client-fingerprint': tls.get('utls', {}).get('fingerprint', 'chrome')
                    })
        # Hy2 格式
        elif isinstance(data, dict) and 'server' in data:
            server_main = data.get('server', '').split(',')[0]
            nodes.append({
                'name': 'hy2_node', 'type': 'hysteria2', 
                'server': server_main.rsplit(':', 1)[0], 'port': int(server_main.rsplit(':', 1)[1]),
                'password': data.get('auth'), 'sni': data.get('tls', {}).get('sni', 'apple.com')
            })
    except: pass
    try:
        data = yaml.safe_load(content)
        if isinstance(data, dict) and 'proxies' in data:
            nodes.extend(data.get('proxies', []))
    except: pass
    return nodes

def generate_uri(p):
    try:
        p_type = str(p.get('type', '')).lower()
        name = quote(str(p.get('name', 'node')))
        server = format_addr(p.get('server', ''))
        port = p.get('port')
        if p_type == 'vless':
            ropts = p.get('reality-opts', {})
            params = {"security": "reality", "sni": p.get('servername', p.get('sni', '')), "pbk": ropts.get('public-key', ''), "sid": ropts.get('short-id', '')}
            return f"vless://{p.get('uuid')}@{server}:{port}?{urlencode({k: v for k, v in params.items() if v})}#{name}"
        elif p_type == 'hysteria2' or p_type == 'hy2':
            passwd = p.get('password', p.get('auth', ''))
            return f"hysteria2://{passwd}@{server}:{port}?sni={p.get('sni', '')}&insecure=1#{name}"
        elif p_type == 'anytls':
            params = {"alpn": ",".join(p.get('alpn', [])), "insecure": "1"}
            return f"anytls://{p.get('password')}@{server}:{port}?{urlencode(params)}#{name}"
    except: return None
    return None

def main():
    all_proxies = []
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip() and line.startswith("http")]

    for url in urls:
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                all_proxies.extend(parse_content(resp.text))
        except: continue

    # 1. 深度去重
    unique_nodes = []
    seen_configs = set()
    for p in all_proxies:
        temp_p = p.copy()
        temp_p.pop('name', None)
        fingerprint = json.dumps(temp_p, sort_keys=True)
        if fingerprint not in seen_configs:
            seen_configs.add(fingerprint)
            unique_nodes.append(p)

    # 2. 统一重命名 (彻底解决 duplicate name)
    final_proxies = []
    protocol_counts = {}
    time_tag = get_beijing_time()
    for p in unique_nodes:
        p_type = str(p.get('type', 'UNK')).upper()
        count = protocol_counts.get(p_type, 0) + 1
        protocol_counts[p_type] = count
        p['name'] = f"[{p_type}] {count:02d} ({time_tag})"
        final_proxies.append(p)

    node_names = [p['name'] for p in final_proxies]

    # 3. 修正后的神机规则 (彻底解决 loop is detected)
    clash_config = {
        "port": 7890,
        "allow-lan": True,
        "mode": "rule",
        "proxies": final_proxies,
        "proxy-groups": [
            # 主入口，不包含“全球直连”，打破循环
            {"name": "🚀 节点选择", "type": "select", "proxies": ["♻️ 自动选择"] + node_names + ["DIRECT"]},
            {"name": "♻️ 自动选择", "type": "url-test", "url": "http://www.gstatic.com/generate_204", "interval": 300, "proxies": node_names},
            {"name": "📲 电报信息", "type": "select", "proxies": ["🚀 节点选择", "DIRECT"]},
            {"name": "🌍 国外媒体", "type": "select", "proxies": ["🚀 节点选择", "DIRECT"]},
            # 这里的全球直连只包含 DIRECT 和节点选择，不让节点选择再反过来包含它
            {"name": "🎯 全球直连", "type": "select", "proxies": ["DIRECT", "🚀 节点选择"]}
        ],
        "rules": [
            "DOMAIN-SUFFIX,telegram.org,📲 电报信息",
            "DOMAIN-SUFFIX,tg.me,📲 电报信息",
            "DOMAIN-SUFFIX,netflix.com,🌍 国外媒体",
            "DOMAIN-SUFFIX,youtube.com,🌍 国外媒体",
            "GEOIP,CN,🎯 全球直连",
            "MATCH,🚀 节点选择"
        ]
    }

    with open('config.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(clash_config, f, allow_unicode=True, sort_keys=False)

    uris = [generate_uri(p) for p in final_proxies if generate_uri(p)]
    with open('sub.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(uris))
    with open('sub_base64.txt', 'w', encoding='utf-8') as f:
        f.write(base64.b64encode("\n".join(uris).encode('utf-8')).decode('utf-8'))

if __name__ == "__main__":
    main()
