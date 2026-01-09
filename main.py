import requests
import yaml
import base64
import os
import json
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode

# --- 工具函数 ---
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
    # 尝试 JSON (sing-box 或 Hy2)
    try:
        data = json.loads(content)
        if isinstance(data, dict) and 'outbounds' in data:
            for out in data['outbounds']:
                if out.get('type') == 'vless':
                    tls = out.get('tls', {})
                    reality = tls.get('reality', {})
                    nodes.append({
                        'name': out.get('tag', 'singbox_vless'),
                        'type': 'vless',
                        'server': out.get('server'),
                        'port': out.get('server_port'),
                        'uuid': out.get('uuid'),
                        'tls': tls.get('enabled', False),
                        'servername': tls.get('server_name', ''),
                        'reality-opts': {'public-key': reality.get('public_key', ''), 'short-id': reality.get('short_id', '')},
                        'client-fingerprint': tls.get('utls', {}).get('fingerprint', 'chrome')
                    })
        elif isinstance(data, dict) and 'server' in data:
            server_main = data.get('server', '').split(',')[0]
            nodes.append({
                'name': 'Hy2_JSON', 'type': 'hysteria2', 
                'server': server_main.rsplit(':', 1)[0], 'port': int(server_main.rsplit(':', 1)[1]),
                'password': data.get('auth'), 'sni': data.get('tls', {}).get('sni', 'apple.com')
            })
    except: pass
    # 尝试 YAML
    try:
        data = yaml.safe_load(content)
        if isinstance(data, dict) and 'proxies' in data:
            nodes.extend(data.get('proxies', []))
    except: pass
    return nodes

def generate_uri(p):
    # (保持之前的 generate_uri 逻辑不变...)
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
            return f"hysteria2://{p.get('password', p.get('auth', ''))}@{server}:{port}?sni={p.get('sni', '')}&insecure=1#{name}"
    except: return None
    return None

# --- 主逻辑 ---
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

    # 深度去重
    unique_nodes = []
    seen_configs = set()
    for p in all_proxies:
        temp_p = p.copy()
        temp_p.pop('name', None)
        fingerprint = json.dumps(temp_p, sort_keys=True)
        if fingerprint not in seen_configs:
            seen_configs.add(fingerprint)
            unique_nodes.append(p)

    # 重命名与时间戳
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

    # --- 神机规则模板注入 ---
    clash_config = {
        "port": 7890,
        "allow-lan": True,
        "mode": "rule",
        "log-level": "info",
        "dns": {
            "enabled": True, "nameserver": ["119.29.29.29", "223.5.5.5"], "fallback": ["8.8.8.8"]
        },
        "proxies": final_proxies,
        "proxy-groups": [
            {"name": "🚀 节点选择", "type": "select", "proxies": ["♻️ 自动选择", "🎯 全球直连"] + node_names},
            {"name": "♻️ 自动选择", "type": "url-test", "url": "http://www.gstatic.com/generate_204", "interval": 300, "proxies": node_names},
            {"name": "📲 电报信息", "type": "select", "proxies": ["🚀 节点选择", "🎯 全球直连"] + node_names},
            {"name": "🌍 国外媒体", "type": "select", "proxies": ["🚀 节点选择", "🎯 全球直连"] + node_names},
            {"name": "🎯 全球直连", "type": "select", "proxies": ["DIRECT", "🚀 节点选择"]}
        ],
        "rules": [
            "DOMAIN-SUFFIX,telegram.org,📲 电报信息",
            "DOMAIN-SUFFIX,tg.me,📲 电报信息",
            "DOMAIN-KEYWORD,telegram,📲 电报信息",
            "DOMAIN-SUFFIX,netflix.com,🌍 国外媒体",
            "DOMAIN-SUFFIX,youtube.com,🌍 国外媒体",
            "DOMAIN-SUFFIX,googlevideo.com,🌍 国外媒体",
            "GEOIP,CN,🎯 全球直连",
            "MATCH,🚀 节点选择"
        ]
    }

    with open('config.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(clash_config, f, allow_unicode=True, sort_keys=False)

    # 保存 sub.txt
    uris = [generate_uri(p) for p in final_proxies if generate_uri(p)]
    with open('sub.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(uris))
    with open('sub_base64.txt', 'w', encoding='utf-8') as f:
        f.write(base64.b64encode("\n".join(uris).encode('utf-8')).decode('utf-8'))

if __name__ == "__main__":
    main()
