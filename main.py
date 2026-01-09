import requests
import yaml
import base64
import json
from urllib.parse import quote

def parse_clash_yaml(yaml_content):
    nodes = []
    try:
        data = yaml.safe_load(yaml_content)
        proxies = data.get('proxies', [])
        for p in proxies:
            p_type = p.get('type')
            name = quote(p.get('name', 'node'))
            server = p.get('server')
            port = p.get('port')
            
            if p_type == 'vless':
                uuid = p.get('uuid')
                sni = p.get('servername')
                reality = p.get('reality-opts', {})
                pbk = reality.get('public-key', '')
                sid = reality.get('short-id', '')
                net = p.get('network', 'tcp')
                nodes.append(f"vless://{uuid}@{server}:{port}?security=tls&sni={sni}&fp=chrome&type={net}&pbk={pbk}&sid={sid}#{name}")
            
            elif p_type == 'hysteria':
                auth = p.get('auth-str', '')
                sni = p.get('sni', '')
                nodes.append(f"hysteria://{server}:{port}?auth={auth}&sni={sni}&alpn=h3#{name}")
    except Exception as e:
        print(f"YAML解析跳过: {e}")
    return nodes

def main():
    all_links = []
    with open('sources.txt', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    current_category = ""
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            current_category = line
            continue
        try:
            resp = requests.get(line, timeout=15)
            if resp.status_code == 200:
                if "YAML" in current_category.upper():
                    all_links.extend(parse_clash_yaml(resp.text))
        except:
            continue

    # 去重并保存
    unique_links = list(dict.fromkeys(all_links))
    # 生成 Base64 订阅
    sub_content = base64.b64encode("\n".join(unique_links).encode('utf-8')).decode('utf-8')
    with open('subscribe.txt', 'w', encoding='utf-8') as f:
        f.write(sub_content)

if __name__ == "__main__":
    main()
