import requests
import yaml
import base64
import os
from urllib.parse import quote, urlencode

def format_addr(addr):
    addr_str = str(addr).strip()
    if ":" in addr_str and "[" not in addr_str:
        return f"[{addr_str}]"
    return addr_str

def parse_clash_yaml(yaml_content):
    try:
        data = yaml.safe_load(yaml_content)
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
                "fp": "chrome",
                "type": p.get('network', 'tcp'),
                "pbk": reality.get('public-key', ''),
                "sid": reality.get('short-id', ''),
            }
            return f"vless://{p.get('uuid')}@{server}:{port}?{urlencode({k: v for k, v in params.items() if v})}#{name}"
        
        elif p_type == 'anytls':
            # 针对 AnyTLS 节点的特殊 URI 构造
            params = {
                "alpn": ",".join(p.get('alpn', [])),
                "insecure": "1"
            }
            return f"anytls://{p.get('password')}@{server}:{port}?{urlencode(params)}#{name}"
            
        elif p_type == 'hysteria2' or p_type == 'hy2':
            return f"hysteria2://{p.get('password', p.get('auth', ''))}@{server}:{port}?sni={p.get('sni', '')}&insecure=1#{name}"
        
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
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                all_proxies.extend(parse_clash_yaml(resp.text))
        except: continue

    # 严格去重与命名
    final_proxies = []
    seen_names = set()
    for p in all_proxies:
        origin_name = str(p.get('name', 'node'))
        name = origin_name
        idx = 1
        while name in seen_names:
            name = f"{origin_name}_{idx}"
            idx += 1
        p['name'] = name
        seen_names.add(name)
        final_proxies.append(p)

    # 保存文件
    with open('config.yaml', 'w', encoding='utf-8') as f:
        yaml.dump({"port": 7890, "proxies": final_proxies}, f, allow_unicode=True, sort_keys=False)

    uris = [generate_uri(p) for p in final_proxies if generate_uri(p)]
    with open('sub.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(uris))

    sub_base64 = base64.b64encode("\n".join(uris).encode('utf-8')).decode('utf-8')
    with open('sub_base64.txt', 'w', encoding='utf-8') as f:
        f.write(sub_base64)

if __name__ == "__main__":
    main()
