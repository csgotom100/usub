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
    """解析源 YAML 并提取所有代理对象"""
    try:
        # 使用 SafeLoader 加载，确保安全
        data = yaml.safe_load(yaml_content)
        if not data or 'proxies' not in data:
            return []
        return data.get('proxies', [])
    except Exception as e:
        print(f"YAML 解析失败: {e}")
        return []

def generate_uri(p):
    """将对象转换为 URI 链接，增加对 anytls 的支持"""
    try:
        p_type = str(p.get('type', '')).lower()
        name = quote(str(p.get('name', 'node')))
        server = format_addr(p.get('server', ''))
        port = p.get('port')
        
        # 1. VLESS Reality
        if p_type == 'vless':
            uuid = p.get('uuid')
            reality = p.get('reality-opts', {})
            params = {
                "security": "reality",
                "sni": p.get('servername') or p.get('sni', ''),
                "fp": p.get('client-fingerprint', 'chrome'),
                "type": p.get('network', 'tcp'),
                "pbk": reality.get('public-key', ''),
                "sid": reality.get('short-id', ''),
            }
            param_str = urlencode({k: v for k, v in params.items() if v})
            return f"vless://{uuid}@{server}:{port}?{param_str}#{name}"
            
        # 2. Hysteria 2
        elif p_type == 'hysteria2' or p_type == 'hy2':
            passwd = p.get('password', p.get('auth', ''))
            sni = p.get('sni', '')
            return f"hysteria2://{passwd}@{server}:{port}?sni={sni}&insecure=1#{name}"

        # 3. TUIC
        elif p_type == 'tuic':
            uuid = p.get('uuid', '')
            passwd = p.get('password', '')
            return f"tuic://{uuid}:{passwd}@{server}:{port}?sni={p.get('sni', '')}&insecure=1&alpn=h3#{name}"

        # 4. AnyTLS (新增支持)
        # 注意：anytls 并没有标准的 URI，这里生成一个伪 URI 供记录，主要依赖 config.yaml
        elif p_type == 'anytls':
            passwd = p.get('password', '')
            sni = p.get('sni', '')
            return f"anytls://{passwd}@{server}:{port}?sni={sni}#{name}"

        # 5. Mieru
        elif p_type == 'mieru':
            user = p.get('username', '')
            pwd = p.get('password', '')
            return f"mieru://{user}:{pwd}@{server}:{port}?transport=tcp#{name}"

    except:
        return None
    return None

def main():
    all_proxies = []
    if not os.path.exists('sources.txt'):
        print("未找到 sources.txt")
        return

    with open('sources.txt', 'r', encoding='utf-8') as f:
        sources = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    
    # 重新读取以处理分类标注
    with open('sources.txt', 'r', encoding='utf-8') as f:
        lines = f.readlines()

    current_type = "YAML" # 默认假设是 YAML
    for line in lines:
        line = line.strip()
        if not line: continue
        if line.startswith("#"):
            current_type = line.upper()
            continue
        
        try:
            print(f"正在抓取源: {line}")
            resp = requests.get(line, timeout=15)
            if resp.status_code == 200:
                # 只要当前分类标注含有 YAML，就执行 YAML 解析
                if "YAML" in current_type:
                    proxies = parse_clash_yaml(resp.text)
                    print(f"成功提取 {len(proxies)} 个节点")
                    all_proxies.extend(proxies)
        except Exception as e:
            print(f"请求失败 {line}: {e}")

    # 去重（基于节点名称和服务器地址）
    unique_proxies = {}
    for p in all_proxies:
        key = f"{p.get('name')}-{p.get('server')}"
        if key not in unique_proxies:
            unique_proxies[key] = p

    proxy_list = list(unique_proxies.values())

    # --- 输出 1: config.yaml (Clash 专用，包含 AnyTLS) ---
    clash_config = {
        "port": 7890,
        "allow-lan": True,
        "mode": "rule",
        "proxies": proxy_list,
        "proxy-groups": [{"name": "Proxy", "type": "select", "proxies": [p.get('name') for p in proxy_list]}],
        "rules": ["MATCH,Proxy"]
    }
    with open('config.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(clash_config, f, allow_unicode=True, sort_keys=False)

    # --- 输出 2: sub.txt & sub_base64.txt ---
    uris = [generate_uri(p) for p in proxy_list if generate_uri(p)]
    with open('sub.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(uris))
    
    sub_base64 = base64.b64encode("\n".join(uris).encode('utf-8')).decode('utf-8')
    with open('sub_base64.txt', 'w', encoding='utf-8') as f:
        f.write(sub_base64)
    
    print(f"处理完成！总去重节点数: {len(proxy_list)}")

if __name__ == "__main__":
    main()
