import json, requests, base64, yaml, urllib.parse, os, re, warnings
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

def get_beijing_time():
    return (datetime.utcnow() + timedelta(hours=8)).strftime("%m-%d %H:%M")

def main():
    all_proxies = [] # 存储原始的 Dict 对象，用于 Clash
    uris = []        # 存储转换后的 URI，用于 v2rayN
    time_tag = get_beijing_time()

    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]

    for url in urls:
        try:
            r = requests.get(url, timeout=15, verify=False)
            content = r.text.strip()
            # 自动识别是 JSON 还是 YAML
            is_json = content.startswith(('{', '['))
            data = json.loads(content) if is_json else yaml.safe_load(content)

            # 递归寻找代理配置
            def walk(obj):
                if isinstance(obj, dict):
                    # 识别特征：如果有 server/type/name 字段，大概率就是一个节点
                    if 'server' in obj and 'type' in obj:
                        # --- 核心改进：直接克隆原始对象 ---
                        raw_node = obj.copy()
                        
                        # 简单的重命名，加上地理和时间标签，但不破坏内部参数
                        old_name = raw_node.get('name', 'node')
                        new_name = f"[{raw_node['type'].upper()}] {old_name} ({time_tag})"
                        raw_node['name'] = new_name
                        
                        all_proxies.append(raw_node)
                        
                        # 尝试转化为 URI (仅供 sub.txt 使用，即使转化失败也不影响 Clash)
                        try:
                            uri = convert_to_uri(raw_node, new_name)
                            if uri: uris.append(uri)
                        except: pass
                    else:
                        for v in obj.values(): walk(v)
                elif isinstance(obj, list):
                    for i in obj: walk(i)
            
            walk(data)
        except: continue

    # 去重 (基于 server 和 port)
    unique_proxies = []
    seen = set()
    for p in all_proxies:
        key = f"{p.get('server')}:{p.get('port')}:{p.get('type')}"
        if key not in seen:
            unique_proxies.append(p)
            seen.add(key)

    # 1. 保存 sub.txt (URI 链接)
    with open("sub.txt", "w", encoding="utf-8") as f: f.write("\n".join(uris))
    with open("sub_base64.txt", "w", encoding="utf-8") as f:
        f.write(base64.b64encode("\n".join(uris).encode()).decode())
    
    # 2. 保存 config.yaml (直接照搬原始 proxies)
    clash_config = {
        "ipv6": True,
        "allow-lan": True,
        "mode": "rule",
        "proxies": unique_proxies, # 这里直接放原始对象列表
        "proxy-groups": [
            {"name": "🚀 节点选择", "type": "select", "proxies": ["♻️ 自动选择", "DIRECT"] + [p['name'] for p in unique_proxies]},
            {"name": "♻️ 自动选择", "type": "url-test", "url": "http://www.gstatic.com/generate_204", "interval": 300, "proxies": [p['name'] for p in unique_proxies]}
        ],
        "rules": ["MATCH,🚀 节点选择"]
    }
    with open("config.yaml", "w", encoding="utf-8") as f:
        yaml.dump(clash_config, f, allow_unicode=True, sort_keys=False)

def convert_to_uri(n, name):
    """仅用于生成 sub.txt，不影响 Clash 配置"""
    srv = f"[{n['server']}]" if ':' in str(n['server']) else n['server']
    name_enc = urllib.parse.quote(name)
    
    if n['type'] == 'vless':
        params = {"encryption": "none", "security": "none"}
        if n.get('tls'): params["security"] = "tls"
        if n.get('reality-opts'): 
            params["security"] = "reality"
            params["pbk"] = n['reality-opts'].get('public-key')
            params["sid"] = n['reality-opts'].get('short-id')
        params["sni"] = n.get('servername') or n.get('sni', "")
        return f"vless://{n.get('uuid')}@{srv}:{n['port']}?{urllib.parse.urlencode(params)}#{name_enc}"
    
    elif n['type'] == 'hysteria2':
        return f"hysteria2://{n.get('password') or n.get('auth')}@{srv}:{n['port']}?insecure=1#{name_enc}"
    
    return None # 其他协议如 mieru 无法简单转化为 URI，返回 None 即可

if __name__ == "__main__":
    main()
