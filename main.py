import requests
import yaml
import base64
from urllib.parse import quote

def parse_clash_yaml(yaml_content):
    """严格按照你的样板解析 YAML"""
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
            
            # 1. 处理 VLESS (Reality)
            if p_type == 'vless':
                uuid = p.get('uuid')
                sni = p.get('servername', '')
                reality = p.get('reality-opts', {})
                pbk = reality.get('public-key', '')
                sid = reality.get('short-id', '')
                net = p.get('network', 'tcp')
                uri = f"vless://{uuid}@{server}:{port}?security=tls&sni={sni}&fp=chrome&type={net}&pbk={pbk}&sid={sid}#{name}"
                nodes.append(uri)
                
            # 2. 处理 Hysteria
            elif p_type == 'hysteria':
                auth = p.get('auth-str', '')
                sni = p.get('sni', '')
                uri = f"hysteria://{server}:{port}?auth={auth}&sni={sni}&alpn=h3#{name}"
                nodes.append(uri)
    except Exception as e:
        print(f"解析出错: {e}")
    return nodes

def main():
    all_extracted_nodes = []
    
    # 读取配置文件
    try:
        with open('sources.txt', 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print("错误：请先在仓库中创建 sources.txt")
        return

    current_type = ""
    for line in lines:
        line = line.strip()
        if not line: continue
        if line.startswith("#"):
            current_type = line.upper()
            continue
        
        try:
            print(f"正在抓取: {line}")
            resp = requests.get(line, timeout=15)
            if resp.status_code == 200:
                if "YAML" in current_type:
                    nodes = parse_clash_yaml(resp.text)
                    all_extracted_nodes.extend(nodes)
        except Exception as e:
            print(f"访问失败 {line}: {e}")

    # 去重
    final_nodes = list(dict.fromkeys(all_extracted_nodes))
    
    # 输出 1: sub.txt (明文链接格式，每行一个)
    with open('sub.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(final_nodes))
    
    # 输出 2: sub_base64.txt (Base64 加密格式)
    combined_text = "\n".join(final_nodes)
    sub_base64 = base64.b64encode(combined_text.encode('utf-8')).decode('utf-8')
    with open('sub_base64.txt', 'w', encoding='utf-8') as f:
        f.write(sub_base64)
    
    print(f"测试完成！共提取到 {len(final_nodes)} 个节点。")

if __name__ == "__main__":
    main()
