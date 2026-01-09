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
    """解析源 YAML 并提取原始代理对象"""
    try:
        data = yaml.safe_load(yaml_content)
        if not data or 'proxies' not in data:
            return []
        return data.get('proxies', [])
    except Exception as e:
        print(f"YAML 解析源文件失败: {e}")
        return []

def generate_uri(p):
    """将代理对象转换为 v2rayN 兼容的 URI"""
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
                "sni": p.get('servername', ''),
                "fp": "chrome",
                "type": p.get('network', 'tcp'),
                "pbk": reality.get('public-key', ''),
                "sid": reality.get('short-id', ''),
                "flow": p.get('flow', '')
            }
            param_str = urlencode({k: v for k, v in params.items() if v})
            return f"vless://{uuid}@{server}:{port}?{param_str}#{name}"
            
        elif p_type == 'hysteria':
            auth = p.get('auth-str', '')
            sni = p.get('sni', '')
            return f"hysteria://{server}:{port}?auth={auth}&peer={sni}&insecure=1&alpn=h3#{name}"
    except:
        return None
    return None

def main():
    all_proxies = []
    
    if not os.path.exists('sources.txt'):
        return

    with open('sources.txt', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    current_type = ""
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            current_type = line.upper()
            continue
        
        try:
            resp = requests.get(line, timeout=15)
            if resp.status_code == 200:
                if "YAML" in current_type:
                    proxies = parse_clash_yaml(resp.text)
                    all_proxies.extend(proxies)
        except:
            continue

    # 去重处理 (按名字去重)
    unique_proxies = {p.get('name'): p for p in all_proxies if p.get('name')}.values()
    proxy_list = list(unique_proxies)

    # --- 输出 1: 生成 Clash 配置文件 (config.yaml) ---
    clash_config = {
        "port": 7890,
        "allow-lan": True,
        "mode": "rule",
        "log-level": "info",
        "proxies": proxy_list,
        "proxy-groups": [
            {
                "name": "Proxy",
                "type": "select",
                "proxies": [p.get('name') for p in proxy_list]
            }
        ],
        "rules": ["MATCH,Proxy"]
    }
    with open('config.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(clash_config, f, allow_unicode=True, sort_keys=False)

    # --- 输出 2: 生成 v2rayN 订阅 (sub.txt / sub_base64.txt) ---
    uris = [generate_uri(p) for p in proxy_list if generate_uri(p)]
    with open('sub.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(uris))
    
    sub_base64 = base64.b64encode("\n".join(uris).encode('utf-8')).decode('utf-8')
    with open('sub_base64.txt', 'w', encoding='utf-8') as f:
        f.write(sub_base64)

if __name__ == "__main__":
    main()
