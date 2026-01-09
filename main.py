import requests
import yaml
import base64
from urllib.parse import quote
import os

def parse_clash_yaml(yaml_content):
    """解析 YAML 并按照样板转换为 URI 链接"""
    nodes = []
    try:
        data = yaml.safe_load(yaml_content)
        if not data or 'proxies' not in data:
            return nodes
            
        proxies = data.get('proxies', [])
        for p in proxies:
            p_type = p.get('type')
            name = quote(p.get('name', 'node'))
            server = p.get('server')
            port = p.get('port')
            
            # 1. VLESS (Reality) 提取
            if p_type == 'vless':
                uuid = p.get('uuid')
                sni = p.get('servername', '')
                reality = p.get('reality-opts', {})
                pbk = reality.get('public-key', '')
                sid = reality.get('short-id', '')
                net = p.get('network', 'tcp')
                uri = f"vless://{uuid}@{server}:{port}?security=tls&sni={sni}&fp=chrome&type={net}&pbk={pbk}&sid={sid}#{name}"
                nodes.append(uri)
                
            # 2. Hysteria 提取
            elif p_type == 'hysteria':
                auth = p.get('auth-str', '')
                sni = p.get('sni', '')
                # 将 alpn 列表转为字符串，样板默认为 h3
                alpn = ",".join(p.get('alpn', ['h3']))
                uri = f"hysteria://{server}:{port}?auth={auth}&sni={sni}&alpn={alpn}#{name}"
                nodes.append(uri)
    except Exception as e:
        print(f"YAML 解析出错: {e}")
    return nodes

def main():
    all_extracted_nodes = []
    
    # 检查 sources.txt 是否存在
    if not os.path.exists('sources.txt'):
        print("Error: sources.txt not found!")
        return

    with open('sources.txt', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    current_type = ""
    for line in lines:
        line = line.strip()
        if not line: continue
        if line.startswith("#"):
            current_type = line.upper()
            continue
        
        try:
            print(f"Fetching: {line}")
            resp = requests.get(line, timeout=15)
            if resp.status_code == 200:
                if "YAML" in current_type:
                    nodes = parse_clash_yaml(resp.text)
                    all_extracted_nodes.extend(nodes)
                # 后续 JSON 逻辑会在这里扩展
        except Exception as e:
            print(f"Request failed for {line}: {e}")

    # 汇总去重
    final_nodes = list(dict.fromkeys(all_extracted_nodes))
    
    # 输出 1: sub.txt (明文链接，方便测试)
    with open('sub.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(final_nodes))
    
    # 输出 2: sub_base64.txt (标准订阅格式)
    combined_text = "\n".join(final_nodes)
    sub_base64 = base64.b64encode(combined_text.encode('utf-8')).decode('utf-8')
    with open('sub_base64.txt', 'w', encoding='utf-8') as f:
        f.write(sub_base64)
    
    print(f"Done! Extracted {len(final_nodes)} nodes.")

if __name__ == "__main__":
    main()
