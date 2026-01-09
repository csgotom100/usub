import json, requests, base64, yaml, urllib.parse, os, re, warnings
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

def get_beijing_time():
    return (datetime.utcnow() + timedelta(hours=8)).strftime("%m-%d %H:%M")

def get_geo_tag(text, server):
    words = {
        "🇭🇰": ["hk", "香港", "hkg"], "🇺🇸": ["us", "美国", "america"],
        "🇯🇵": ["jp", "日本", "tokyo"], "🇸🇬": ["sg", "新加坡", "singapore"],
        "🇹🇼": ["tw", "台湾", "taiwan"], "🇰🇷": ["kr", "韩国", "korea"]
    }
    content = str(text).lower() + str(server).lower()
    for tag, keys in words.items():
        if any(k in content for k in keys): return tag
    return "🌐"

def get_node_info(item):
    try:
        if not isinstance(item, dict): return None
        srv = item.get('server') or item.get('add') or item.get('address')
        if not srv or str(srv).startswith('127.'): return None
        
        port = str(item.get('port') or item.get('server_port') or "")
        if ':' in str(srv) and not srv.startswith('['):
            srv, port = str(srv).rsplit(':', 1)
        port = re.findall(r'\d+', port)[0] if re.findall(r'\d+', port) else ""
        if not port: return None

        pw = item.get('auth') or item.get('password') or item.get('uuid') or item.get('id')
        if not pw: return None
        
        # 深度提取 SNI 和 Reality 参数
        tls = item.get('tls', {}) if isinstance(item.get('tls'), dict) else {}
        sni = item.get('sni') or item.get('servername') or tls.get('server_name') or ""
        pbk = item.get('public-key') or item.get('public_key') or tls.get('reality', {}).get('public_key') or item.get('reality-opts', {}).get('public-key') or ""
        sid = item.get('short-id') or item.get('short_id') or tls.get('reality', {}).get('short_id') or item.get('reality-opts', {}).get('short-id') or ""

        # 核心：多层级捞取 path (xhttp 命脉)
        path = ""
        for k in ['path', 'xhttp-opts', 'xhttpSettings', 'transport']:
            v = item.get(k)
            if isinstance(v, str) and v.startswith('/'): path = v
            elif isinstance(v, dict) and v.get('path'): path = v.get('path')

        # 协议判定逻辑
        p_raw = str(item.get('type') or item.get('protocol') or "").lower()
        if 'hy2' in p_raw or 'hysteria2' in p_raw or 'auth' in item: p = 'hysteria2'
        elif 'tuic' in p_raw: p = 'tuic'
        elif 'anytls' in p_raw: p = 'anytls'
        else: p = 'vless'

        return {
            "server": srv.strip('[]'), "port": port, "type": p, "pw": pw,
            "sni": sni, "pbk": pbk, "sid": sid, "path": path,
            "name": item.get('tag') or item.get('name') or ""
        }
    except: return None

def main():
    nodes = []
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]

    for url in urls:
        try:
            r = requests.get(url, timeout=15, verify=False)
            content = r.text.strip()
            data = json.loads(content) if content.startswith(('{', '[')) else yaml.safe_load(content)
            
            def walk(obj):
                if isinstance(obj, dict):
                    res = get_node_info(obj)
                    if res: nodes.append(res)
                    for v in obj.values(): walk(v)
                elif isinstance(obj, list):
                    for i in obj: walk(i)
            walk(data)
        except: continue

    # 宽松去重：IP + 端口 + 协议 相同才算重复，保留不同密码或路径的节点
    unique = []
    seen = set()
    for n in nodes:
        key = f"{n['server']}:{n['port']}:{n['type']}"
        if key not in seen:
            unique.append(n); seen.add(key)

    # AnyTLS 依然排第一
    unique.sort(key=lambda x: 0 if x['type'] == 'anytls' else 1)
    uris = []
    time_tag = get_beijing_time()
    
    for i, n in enumerate(unique, 1):
        geo = get_geo_tag(n['name'] + n['sni'] + n['server'], n['server'])
        name = f"{geo}[{n['type'].upper()}] {i:02d} ({time_tag})"
        name_enc = urllib.parse.quote(name)
        srv = f"[{n['server']}]" if ':' in n['server'] else n['server']
        
        if n['type'] == 'vless':
            params = {"security": "reality" if n['pbk'] else "none", "sni": n['sni'] or "itunes.apple.com", "pbk": n['pbk'], "sid": n['sid']}
            if n['path']: params.update({"type": "xhttp", "path": n['path']})
            uris.append(f"vless://{n['pw']}@{srv}:{n['port']}?{urllib.parse.urlencode({k:v for k,v in params.items() if v})}#{name_enc}")
        elif n['type'] == 'hysteria2':
            # 补全默认 SNI 提升导入质量
            sni_val = n['sni'] if n['sni'] else "apple.com"
            uris.append(f"hysteria2://{n['pw']}@{srv}:{n['port']}?insecure=1&sni={sni_val}#{name_enc}")
        elif n['type'] == 'anytls':
            uris.append(f"anytls://{n['pw']}@{srv}:{n['port']}?alpn=h3&insecure=1#{name_enc}")
        elif n['type'] == 'tuic':
            uris.append(f"tuic://{n['pw']}@{srv}:{n['port']}?sni={n['sni'] or 'apple.com'}&alpn=h3#{name_enc}")

    with open("sub.txt", "w", encoding="utf-8") as f: f.write("\n".join(uris))
    with open("sub_base64.txt", "w", encoding="utf-8") as f:
        f.write(base64.b64encode("\n".join(uris).encode()).decode())

if __name__ == "__main__":
    main()
