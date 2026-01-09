import requests, yaml, base64, os, json, re
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode

def get_beijing_time():
    return (datetime.utcnow() + timedelta(hours=8)).strftime("%m-%d %H:%M")

def get_geo_tag(text, server):
    """关键词匹配地理位置，增加常用地区"""
    words = {
        "🇭🇰": ["hk", "香港", "hong", "hkg"],
        "🇺🇸": ["us", "美国", "states", "america", "united", "newyork", "la", "sgv"],
        "🇯🇵": ["jp", "日本", "tokyo", "japan", "osaka", "nrt"],
        "🇸🇬": ["sg", "新加坡", "sing", "sin"],
        "🇹🇼": ["tw", "台湾", "taiwan"],
        "🇰🇷": ["kr", "韩国", "korea", "seoul"],
        "🇩🇪": ["de", "德国", "germany", "frankfurt"]
    }
    content = (text + server).lower()
    for tag, keys in words.items():
        if any(k in content for k in keys):
            return tag
    return "🌐"

def parse_content(content):
    nodes = []
    # --- 策略 A: 深度递归扫描 JSON ---
    try:
        data = json.loads(content)
        def find_nodes(obj):
            if isinstance(obj, dict):
                p = str(obj.get('protocol') or obj.get('type')).lower()
                # 识别所有已知协议
                if p in ['vless', 'hysteria2', 'hy2', 'tuic', 'anytls'] or ('server' in obj and ('auth' in obj or 'password' in obj)):
                    # 关键修复：克隆对象防止污染
                    node = obj.copy()
                    if p in ['hysteria2', 'hy2'] or ('auth' in obj and 'server' in obj):
                        node['type'] = 'hysteria2'
                    nodes.append(node)
                for v in obj.values():
                    if isinstance(v, (dict, list)): find_nodes(v)
            elif isinstance(obj, list):
                for i in obj: find_nodes(i)
        find_nodes(data)
    except: pass

    # --- 策略 B: YAML 解析 ---
    try:
        y = yaml.safe_load(content)
        if isinstance(y, dict) and 'proxies' in y:
            nodes.extend(y['proxies'])
    except: pass
    return nodes

def generate_uri(p):
    """为 sub.txt 生成 URI，支持 AnyTLS"""
    try:
        t = str(p.get('type') or p.get('protocol')).lower()
        addr, port = p.get('server'), p.get('port')
        name = quote(p.get('name', ''))
        
        if t == 'vless':
            ro, xh = p.get('reality-opts', {}), p.get('xhttp-opts', {})
            params = {"security": "reality", "sni": p.get('servername') or p.get('sni'), "pbk": ro.get('public-key'), "sid": ro.get('short-id'), "type": p.get('network'), "flow": p.get('flow')}
            if p.get('network') == 'xhttp':
                params["path"] = xh.get('path'); params["mode"] = xh.get('mode', 'auto')
            return f"vless://{p.get('uuid')}@{addr}:{port}?{urlencode({k:v for k,v in params.items() if v})}#{name}"
        
        elif t == 'hysteria2':
            pw = p.get('password') or p.get('auth') or p.get('settings', {}).get('auth')
            return f"hysteria2://{pw}@{addr}:{port}?insecure=1&sni={p.get('sni', 'apple.com')}#{name}"
        
        elif t == 'anytls':
            # 明确找回 AnyTLS 链接
            pw = p.get('password') or p.get('auth')
            return f"anytls://{pw}@{addr}:{port}?alpn=h3&insecure=1#{name}"
            
        elif t == 'tuic':
            val = p.get('uuid') or p.get('password') or p.get('auth')
            return f"tuic://{val}@{addr}:{port}?sni={p.get('sni','')}&alpn=h3#{name}"
            
    except: return None
    return None

def main():
    raw_nodes = []
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]
    
    for url in urls:
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200: raw_nodes.extend(parse_content(r.text))
        except: continue

    unique = []
    seen = set()
    for n in raw_nodes:
        # 指纹识别去重
        srv = n.get('server')
        if not srv: continue
        fp = f"{srv}:{n.get('port')}"
        if fp not in seen:
            seen.add(fp); unique.append(n)

    # 排序：AnyTLS 排第一，VLESS 第二
    unique.sort(key=lambda x: 0 if str(x.get('type') or x.get('protocol')).lower() == 'anytls' else 1)

    time_tag = get_beijing_time()
    for i, p in enumerate(unique):
        # 加上地理标志
        p_type = str(p.get('type') or p.get('protocol')).upper()
        # 从 tag, name, server 中提取地理位置
        search_text = str(p.get('tag','')) + str(p.get('name',''))
        geo = get_geo_tag(search_text, p.get('server', ''))
        p['name'] = f"{geo}[{p_type}] {i+1:02d} ({time_tag})"

    # Clash 生成 (保留单向引用，防止 loop 报错)
    node_names = [x['name'] for x in unique]
    conf = {
        "proxies": unique,
        "proxy-groups": [
            {"name": "🚀 节点选择", "type": "select", "proxies": ["♻️ 自动选择", "DIRECT"] + node_names},
            {"name": "♻️ 自动选择", "type": "url-test", "url": "http://www.gstatic.com/generate_204", "interval": 300, "proxies": node_names},
            {"name": "🎯 全球直连", "type": "select", "proxies": ["DIRECT", "🚀 节点选择"]}
        ],
        "rules": ["MATCH,🚀 节点选择"]
    }
    with open('config.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(conf, f, allow_unicode=True, sort_keys=False)
    
    # URI 生成 (用于 sub.txt)
    uris = [generate_uri(p) for p in unique if generate_uri(p)]
    with open('sub.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(uris))
    with open('sub_base64.txt', 'w', encoding='utf-8') as f:
        f.write(base64.b64encode("\n".join(uris).encode()).decode())

if __name__ == "__main__":
    main()
