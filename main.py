import requests, yaml, base64, os, json, re
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode

def get_beijing_time():
    return (datetime.utcnow() + timedelta(hours=8)).strftime("%m-%d %H:%M")

def get_geo_tag(text, server):
    words = {"🇭🇰": ["hk", "香港"], "🇺🇸": ["us", "美国"], "🇯🇵": ["jp", "日本"], "🇸🇬": ["sg", "新加坡"], "🇹🇼": ["tw", "台湾"]}
    content = (text + server).lower()
    for tag, keys in words.items():
        if any(k in content for k in keys): return tag
    return "🌐"

def parse_content(content):
    nodes = []
    try:
        data = json.loads(content)
        def find_nodes(obj):
            if isinstance(obj, dict):
                p = str(obj.get('protocol') or obj.get('type')).lower()
                if p in ['vless', 'hysteria2', 'hy2', 'tuic', 'anytls'] or ('server' in obj and ('auth' in obj or 'password' in obj)):
                    node = obj.copy()
                    if p in ['hysteria2', 'hy2'] or ('auth' in obj and 'server' in obj): node['type'] = 'hysteria2'
                    nodes.append(node)
                for v in obj.values():
                    if isinstance(v, (dict, list)): find_nodes(v)
            elif isinstance(obj, list):
                for i in obj: find_nodes(i)
        find_nodes(data)
    except: pass
    try:
        y = yaml.safe_load(content)
        if isinstance(y, dict) and 'proxies' in y: nodes.extend(y['proxies'])
    except: pass
    return nodes

def generate_uri(p):
    try:
        t = str(p.get('type') or p.get('protocol')).lower()
        addr = p.get('server')
        # 端口强制清洗：只提取第一个连续数字
        port_raw = str(p.get('port', ''))
        port_match = re.search(r'\d+', port_raw)
        if not port_match: return None
        port = port_match.group()
        
        name = quote(p.get('name', 'node'))
        if t == 'vless':
            ro = p.get('reality-opts', {})
            xh = p.get('xhttp-opts', {})
            params = {"security": "reality", "sni": p.get('servername') or p.get('sni'), "pbk": ro.get('public-key'), "sid": ro.get('short-id'), "type": p.get('network') or "tcp", "flow": p.get('flow')}
            if p.get('network') == 'xhttp': params.update({"path": xh.get('path'), "mode": xh.get('mode', 'auto')})
            if not params["pbk"]: return None # 剔除无效Reality
            return f"vless://{p.get('uuid')}@{addr}:{port}?{urlencode({k:v for k,v in params.items() if v})}#{name}"
        elif t == 'hysteria2':
            pw = p.get('password') or p.get('auth') or p.get('settings', {}).get('auth')
            return f"hysteria2://{pw}@{addr}:{port}?insecure=1&sni={p.get('sni', 'apple.com')}#{name}"
        elif t == 'anytls':
            return f"anytls://{p.get('password') or p.get('auth')}@{addr}:{port}?alpn=h3&insecure=1#{name}"
        elif t == 'tuic':
            val = p.get('uuid') or p.get('password') or p.get('auth')
            return f"tuic://{val}@{addr}:{port}?sni={p.get('sni','')}&alpn=h3#{name}"
    except: return None

def main():
    raw_nodes = []
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]
    for url in urls:
        try:
            r = requests.get(url, timeout=10); r.encoding = 'utf-8'
            if r.status_code == 200: raw_nodes.extend(parse_content(r.text))
        except: continue

    unique = []
    seen = set()
    for n in raw_nodes:
        srv = n.get('server')
        if not srv: continue
        fp = f"{srv}:{n.get('port')}"
        if fp not in seen:
            seen.add(fp); unique.append(n)

    unique.sort(key=lambda x: 0 if str(x.get('type') or x.get('protocol')).lower() == 'anytls' else 1)
    time_tag = get_beijing_time()
    for i, p in enumerate(unique):
        p_type = str(p.get('type') or p.get('protocol')).upper()
        geo = get_geo_tag(str(p.get('tag','')) + str(p.get('name','')), p.get('server', ''))
        p['name'] = f"{geo}[{p_type}] {i+1:02d} ({time_tag})"

    node_names = [x['name'] for x in unique]
    conf = {"proxies": unique, "proxy-groups": [{"name": "🚀 节点选择", "type": "select", "proxies": ["♻️ 自动选择", "DIRECT"] + node_names}, {"name": "♻️ 自动选择", "type": "url-test", "url": "http://www.gstatic.com/generate_204", "interval": 300, "proxies": node_names}, {"name": "🎯 全球直连", "type": "select", "proxies": ["DIRECT", "🚀 节点选择"]}], "rules": ["MATCH,🚀 节点选择"]}
    with open('config.yaml', 'w', encoding='utf-8') as f: yaml.dump(conf, f, allow_unicode=True, sort_keys=False)
    
    uris = [generate_uri(p) for p in unique if generate_uri(p)]
    with open('sub.txt', 'w', encoding='utf-8') as f: f.write("\n".join(uris))
    with open('sub_base64.txt', 'w', encoding='utf-8') as f: f.write(base64.b64encode("\n".join(uris).encode()).decode())

if __name__ == "__main__": main()
