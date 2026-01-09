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
    """识别 YAML, Hy2 JSON 或 sing-box JSON 并返回节点列表"""
    nodes = []
    
    # --- 尝试解析 JSON ---
    try:
        data = json.loads(content)
        
        # 1. sing-box 格式处理
        if isinstance(data, dict) and 'outbounds' in data:
            for out in data['outbounds']:
                if out.get('type') == 'vless':
                    tls = out.get('tls', {})
                    reality = tls.get('reality', {})
                    node = {
                        'name': out.get('tag', 'singbox_vless'),
                        'type': 'vless',
                        'server': out.get('server'),
                        'port': out.get('server_port'),
                        'uuid': out.get('uuid'),
                        'flow': out.get('flow', ''),
                        'tls': tls.get('enabled', False),
                        'servername': tls.get('server_name', ''),
                        'reality-opts': {
                            'public-key': reality.get('public_key', ''),
                            'short-id': reality.get('short_id', '')
                        },
                        'client-fingerprint': tls.get('utls', {}).get('fingerprint', 'chrome')
                    }
                    nodes.append(node)
            if nodes: return nodes

        # 2. Hysteria 2 官方格式处理
        if isinstance(data, dict) and 'server' in data and 'auth' in data:
            server_main = data.get('server', '').split(',')[0]
            host = server_main.rsplit(':', 1)[0]
            port = int(server_main.rsplit(':', 1)[1])
            node = {
                'name': 'Hy2_JSON',
                'type': 'hysteria2',
                'server': host,
                'port': port,
                'password': data.get('auth'),
                'sni': data.get('tls', {}).get('sni', 'apple.com'),
                'skip-cert-verify': data.get('tls', {}).get('insecure', True)
            }
            return [node]
    except:
        pass

    # --- 尝试解析 YAML (Clash) ---
    try:
        data = yaml.safe_load(content)
        if isinstance(data, dict) and 'proxies' in data:
            return data.get('proxies', [])
    except:
        pass
        
    return nodes

def generate_uri(p):
    """转换为订阅链接 URI"""
    try:
        p_type = str(p.get('type', '')).lower()
        name = quote(str(p.get('name', 'node')))
        server = format_addr(p.get('server', ''))
        port = p.get('port')
        
        if p_type == 'vless':
            reality = p.get('reality-opts', {})
            params = {
                "security": "reality",
                "sni": p.get('servername', p.get('sni', '')),
                "fp": p.get('client-fingerprint', 'chrome'),
                "type": "tcp",
                "pbk": reality.get('public-key', ''),
                "sid": reality.get('short-id', ''),
                "flow": p.get('flow', '')
            }
            return f"vless://{p.get('uuid')}@{server}:{port}?{urlencode({k: v for k, v in params.items() if v})}#{name}"
        
        elif p_type == 'anytls':
            params = {"alpn": ",".join(p.get('alpn', [])), "insecure": "1"}
            return f"anytls://{p.get('password')}@{server}:{port}?{urlencode(params)}#{name}"
            
        elif p_type == 'hysteria2' or p_type == 'hy2':
            passwd = p.get('password', p.get('auth', ''))
            return f"hysteria2://{passwd}@{server}:{port}?sni={p.get('sni', '')}&insecure=1#{name}"
        
        elif p_type == 'tuic':
            return f"tuic://{p.get('uuid')}:{p.get('password')}@{server}:{port}?sni={p.get('sni', '')}&insecure=1&alpn=h3#{name}"
    except:
        return None
    return None

def main():
    all_proxies = []
    if not os.path.exists('sources.txt'): return

    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip() and line.startswith("http")]

    for url in urls:
        try:
            print(f"Fetching: {url}")
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                nodes = parse_content(resp.text)
                all_proxies.extend(nodes)
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

    # 保存 config.yaml
    with open('config.yaml', 'w', encoding='utf-8') as f:
        yaml.dump({"port": 7890, "allow-lan": True, "mode": "rule", "proxies": final_proxies}, f, allow_unicode=True, sort_keys=False)

    # 保存 sub.txt & base64
    uris = [generate_uri(p) for p in final_proxies if generate_uri(p)]
    with open('sub.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(uris))
    with open('sub_base64.txt', 'w', encoding='utf-8') as f:
        f.write(base64.b64encode("\n".join(uris).encode('utf-8')).decode('utf-8'))

if __name__ == "__main__":
    main()
