import requests
import yaml
import base64
import os
from urllib.parse import quote, urlencode

def format_addr(addr):
    """处理 IPv6 地址"""
    addr_str = str(addr).strip()
    if ":" in addr_str and "[" not in addr_str:
        return f"[{addr_str}]"
    return addr_str

def parse_clash_yaml(yaml_content):
    """解析源 YAML 并提取代理对象"""
    try:
        data = yaml.safe_load(yaml_content)
        if not data or 'proxies' not in data:
            return []
        return data.get('proxies', [])
    except Exception as e:
        print(f"YAML 解析失败: {e}")
        return []

def generate_uri(p):
    """转换为 v2rayN 兼容 URI"""
    try:
        p_type = str(p.get('type', '')).lower()
        name = quote(str(p.get('name', 'node')))
        server = format_addr(p.get('server', ''))
        port = p.get('port')
        
        if p_type == 'vless':
            uuid = p.get('uuid')
            reality = p.get('reality-opts', {})
            params = {
                "security": "reality",
                "sni": p.get('servername') or p.get('sni', ''),
                "fp": "chrome",
                "type": p.get('network', 'tcp'),
                "pbk": reality.get('public-key', ''),
                "sid": reality.get('short-id', ''),
            }
            return f"vless://{uuid}@{server}:{port}?{urlencode({k: v for k, v in params.items() if v})}#{name}"
        elif p_type == 'hysteria2' or p_type == 'hy2':
            return f"hysteria2://{p.get('password', p.get('auth', ''))}@{server}:{port}?sni={p.get('sni', '')}&insecure=1#{name}"
        elif p_type == 'tuic':
            return f"tuic://{p.get('uuid')}:{p.get('password')}@{server}:{port}?sni={p.get('sni', '')}&insecure=1&alpn=h3#{name}"
        elif p_type == 'anytls':
            return f"anytls://{p.get('password', '')}@{server}:{port}?sni={p.get('sni', '')}#{name}"
    except:
        return None
    return None

def main():
    all_proxies = []
    if not os.path.exists('sources.txt'): return

    with open('sources.txt', 'r', encoding='utf-8') as f:
        lines = f.readlines()

    current_type = "YAML"
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            current_type = line.upper() if line.startswith("#") else current_type
            continue
        try:
            resp = requests.get(line, timeout=15)
            if resp.status_code == 200 and "YAML" in current_type:
                all_proxies.extend(parse_clash_yaml(resp.text))
        except: continue

    # --- 核心修复：严格去重逻辑 ---
    final_proxies = []
    seen_names = set()
    
    for p in all_proxies:
        original_name = str(p.get('name', 'unnamed'))
        name = original_name
        counter = 1
        
        # 如果名字重复，自动增加后缀 (例如: node, node_1, node_2)
        while name in seen_names:
            name = f"{original_name}_{counter}"
            counter += 1
            
        p['name'] = name # 更新节点对象里的名字
        seen_names.add(name)
        final_proxies.append(p)

    # 1. 生成 config.yaml (现在不会再有 duplicate name 报错了)
    clash_config = {
        "port": 7890, "allow-lan": True, "mode": "rule",
        "proxies": final_proxies,
        "proxy-groups": [{"name": "Proxy", "type": "select", "proxies": [p['name'] for p in final_proxies]}],
        "rules": ["MATCH,Proxy"]
    }
    with open('config.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(clash_config, f, allow_unicode=True, sort_keys=False)

    # 2. 生成订阅
    uris = [generate_uri(p) for p in final_proxies if generate_uri(p)]
    with open('sub.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(uris))
    with open('sub_base64.txt', 'w', encoding='utf-8') as f:
        f.write(base64.b64encode("\n".join(uris).encode('utf-8')).decode('utf-8'))

if __name__ == "__main__":
    main()
