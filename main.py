import requests
import yaml
import base64
import os
from urllib.parse import quote, urlencode

def format_addr(addr):
    """处理 IPv6 地址，确保带中括号"""
    addr_str = str(addr).strip()
    if ":" in addr_str and "[" not in addr_str:
        return f"[{addr_str}]"
    return addr_str

def parse_clash_yaml(yaml_content):
    """提取 Clash 配置文件中的代理节点"""
    try:
        data = yaml.safe_load(yaml_content)
        if isinstance(data, dict) and 'proxies' in data:
            return data.get('proxies', [])
    except Exception as e:
        print(f"解析错误: {e}")
    return []

def generate_uri(p):
    """将节点对象转换为 v2rayN 兼容的 URI"""
    try:
        p_type = str(p.get('type', '')).lower()
        name = quote(str(p.get('name', 'node')))
        server = format_addr(p.get('server', ''))
        port = p.get('port')
        
        # VLESS (Reality)
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
        
        # AnyTLS (针对你的源优化)
        elif p_type == 'anytls':
            params = {
                "alpn": ",".join(p.get('alpn', [])),
                "insecure": "1"
            }
            return f"anytls://{p.get('password')}@{server}:{port}?{urlencode(params)}#{name}"
            
        # Hysteria 2
        elif p_type == 'hysteria2' or p_type == 'hy2':
            return f"hysteria2://{p.get('password', p.get('auth', ''))}@{server}:{port}?sni={p.get('sni', '')}&insecure=1#{name}"
        
        # TUIC
        elif p_type == 'tuic':
            return f"tuic://{p.get('uuid')}:{p.get('password')}@{server}:{port}?sni={p.get('sni', '')}&insecure=1&alpn=h3#{name}"

        # Mieru
        elif p_type == 'mieru':
            return f"mieru://{p.get('username')}:{p.get('password')}@{server}:{port}?transport=tcp#{name}"
    except:
        return None
    return None

def main():
    all_proxies = []
    if not os.path.exists('sources.txt'):
        print("Error: sources.txt not found")
        return

    # 读取源链接
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip() and line.startswith("http")]

    for url in urls:
        try:
            print(f"Fetching: {url}")
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                proxies = parse_clash_yaml(resp.text)
                all_proxies.extend(proxies)
        except Exception as e:
            print(f"Failed to fetch {url}: {e}")

    # 处理重名节点
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

    # 1. 生成 config.yaml (Clash 专用)
    clash_config = {
        "port": 7890,
        "allow-lan": True,
        "mode": "rule",
        "proxies": final_proxies,
        "proxy-groups": [{"name": "Proxy", "type": "select", "proxies": [p['name'] for p in final_proxies]}],
        "rules": ["MATCH,Proxy"]
    }
    with open('config.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(clash_config, f, allow_unicode=True, sort_keys=False)

    # 2. 生成 sub.txt
    uris = [generate_uri(p) for p in final_proxies if generate_uri(p)]
    with open('sub.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(uris))

    # 3. 生成 sub_base64.txt
    sub_base64 = base64.b64encode("\n".join(uris).encode('utf-8')).decode('utf-8')
    with open('sub_base64.txt', 'w', encoding='utf-8') as f:
        f.write(sub_base64)
    
    print(f"Success: Processed {len(final_proxies)} nodes.")

if __name__ == "__main__":
    main()
