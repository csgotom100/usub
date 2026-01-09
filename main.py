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
    """自动识别 YAML 或 JSON 并返回节点列表"""
    # 尝试解析 JSON (Hysteria 2 官方格式)
    try:
        data = json.loads(content)
        if isinstance(data, dict) and 'server' in data and 'auth' in data:
            # 转换 JSON 到 Clash 格式字典
            server_part = data.get('server', '').split(',')[0] # 取第一个地址
            host = server_part.rsplit(':', 1)[0]
            port = int(server_part.rsplit(':', 1)[1])
            
            node = {
                'name': 'Imported_JSON',
                'type': 'hysteria2',
                'server': host,
                'port': port,
                'password': data.get('auth'),
                'sni': data.get('tls', {}).get('sni'),
                'skip-cert-verify': data.get('tls', {}).get('insecure', True)
            }
            return [node]
    except:
        pass

    # 尝试解析 YAML (Clash 格式)
    try:
        data = yaml.safe_load(content)
        if isinstance(data, dict) and 'proxies' in data:
            return data.get('proxies', [])
    except:
        pass
        
    return []

def generate_uri(p):
    try:
        p_type = str(p.get('type', '')).lower()
        name = quote(str(p.get('name', 'node')))
        server = format_addr(p.get('server', ''))
        port = p.get('port')
        
        if p_type == 'vless':
            reality = p.get('reality-opts', {})
            params = {
                "security": "reality",
                "sni": p.get('servername') or p.get('sni', ''),
                "fp": "chrome", "type": "tcp",
                "pbk": reality.get('public-key', ''),
                "sid": reality.get('short-id', '')
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

    # 1. 保存 config.yaml
    with open('config.yaml', 'w', encoding='utf-8') as f:
        yaml.dump({"port": 7890, "allow-lan": True, "mode": "rule", "proxies": final_proxies}, f, allow_unicode=True, sort_keys=False)

    # 2. 保存 sub.txt
    uris = [generate_uri(p) for p in final_proxies if generate_uri(p)]
    with open('sub.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(uris))

    # 3. 保存 sub_base64.txt
    sub_base64 = base64.b64encode("\n".join(uris).encode('utf-8')).decode('utf-8')
    with open('sub_base64.txt', 'w', encoding='utf-8') as f:
        f.write(sub_base64)

if __name__ == "__main__":
    main()
