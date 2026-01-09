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
    """根据协议将对象转换为通用的 URI 链接"""
    try:
        p_type = str(p.get('type', '')).lower()
        name = quote(str(p.get('name', 'node')))
        server = format_addr(p.get('server', ''))
        port = p.get('port')
        
        # 1. VLESS Reality 处理
        if p_type == 'vless':
            uuid = p.get('uuid')
            reality = p.get('reality-opts', {})
            params = {
                "security": "reality" if p.get('tls') else "none",
                "sni": p.get('servername') or p.get('sni', ''),
                "fp": p.get('client-fingerprint', 'chrome'),
                "type": p.get('network', 'tcp'),
                "pbk": reality.get('public-key', ''),
                "sid": reality.get('short-id', ''),
                "flow": p.get('flow', '')
            }
            param_str = urlencode({k: v for k, v in params.items() if v})
            return f"vless://{uuid}@{server}:{port}?{param_str}#{name}"
            
        # 2. Hysteria 1 处理
        elif p_type == 'hysteria':
            auth = p.get('auth-str', '')
            sni = p.get('sni', '')
            alpn = ",".join(p.get('alpn', ['h3']))
            insecure = "1" if p.get('skip-cert-verify') else "0"
            return f"hysteria://{server}:{port}?auth={auth}&peer={sni}&insecure={insecure}&alpn={alpn}#{name}"

        # 3. TUIC 处理 (v5 格式)
        elif p_type == 'tuic':
            uuid = p.get('uuid', '')
            passwd = p.get('password', '')
            sni = p.get('sni', '')
            alpn = ",".join(p.get('alpn', ['h3']))
            # TUIC 格式：tuic://uuid:pass@host:port?sni=...&alpn=...
            return f"tuic://{uuid}:{passwd}@{server}:{port}?sni={sni}&alpn={alpn}&congestion_control={p.get('congestion-controller', 'bbr')}#{name}"

        # 4. Mieru (自定义协议，通常转换为通用文本备注或特定格式)
        elif p_type == 'mieru':
            user = p.get('username', '')
            pwd = p.get('password', '')
            transport = p.get('transport', 'tcp')
            return f"mieru://{user}:{pwd}@{server}:{port}?transport={transport}#{name}"

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

    unique_proxies = {p.get('name'): p for p in all_proxies if p.get('name')}.values()
    proxy_list = list(unique_proxies)

    # 生成 config.yaml (Clash 专用)
    clash_config = {
        "port": 7890,
        "allow-lan": True,
        "mode": "rule",
        "log-level": "info",
        "proxies": proxy_list,
        "proxy-groups": [{"name": "Proxy", "type": "select", "proxies": [p.get('name') for p in proxy_list]}],
        "rules": ["MATCH,Proxy"]
    }
    with open('config.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(clash_config, f, allow_unicode=True, sort_keys=False)

    # 生成 sub.txt (明文 URI)
    uris = [generate_uri(p) for p in proxy_list if generate_uri(p)]
    with open('sub.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(uris))
    
    # 生成 sub_base64.txt
    sub_base64 = base64.b64encode("\n".join(uris).encode('utf-8')).decode('utf-8')
    with open('sub_base64.txt', 'w', encoding='utf-8') as f:
        f.write(sub_base64)

if __name__ == "__main__":
    main()
