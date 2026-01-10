import json, requests, base64, yaml, urllib.parse, os, re, warnings
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

def get_beijing_time():
    return (datetime.utcnow() + timedelta(hours=8)).strftime("%m-%d %H:%M")

def get_geo_tag(text, server):
    words = {"🇭🇰": ["hk", "香港"], "🇺🇸": ["us", "美国"], "🇯🇵": ["jp", "日本"], "🇸🇬": ["sg", "新加坡"], "🇹🇼": ["tw", "台湾"]}
    content = str(text).lower() + str(server).lower()
    for tag, keys in words.items():
        if any(k in content for k in keys): return tag
    return "🌐"

def get_node_info(item):
    try:
        if not isinstance(item, dict): return None
        raw_server = item.get('server') or item.get('add') or item.get('address')
        if not raw_server: return None
        
        srv = str(raw_server).strip()
        port_field = str(item.get('port') or item.get('server_port') or "")
        
        # 1. 强化 IPv6/IPv4 分离逻辑
        if srv.startswith('['): 
            match = re.match(r'\[(.+)\]:(\d+)', srv)
            if match:
                srv, port = match.group(1), match.group(2)
            else:
                srv, port = srv.strip('[]'), port_field
        elif srv.count(':') > 1:
            port = port_field
        elif ':' in srv:
            parts = srv.rsplit(':', 1)
            srv, port = parts[0], parts[1]
        else:
            port = port_field

        port = "".join(re.findall(r'\d+', str(port)))
        if not port: return None 

        # 2. 协议判定逻辑 (修复 HY2 消失问题)
        item_raw = str(item).lower()
        p_type = str(item.get('type') or "").lower()
        
        # 排除 Mieru
        if p_type == 'mieru' or 'mieru' in item_raw: return None 
        
        pw = item.get('auth') or item.get('password') or item.get('uuid') or item.get('id')
        
        # 重新加入 Hysteria2 的特征识别
        if 'hysteria2' in p_type or ('auth' in item and 'bandwidth' in item) or 'hy2' in item_raw:
            p = 'hysteria2'
        elif 'tuic' in p_type or 'tuic' in item_raw:
            p = 'tuic'
        elif 'anytls' in item_raw:
            p = 'anytls'
        else:
            p = 'vless'
        
        if not pw and p != 'anytls': return None

        # 3. 提取 Reality/TLS 参数
        tls = item.get('tls', {}) if isinstance(item.get('tls'), dict) else {}
        sni = item.get('servername') or item.get('sni') or tls.get('sni') or item.get('peer') or ""
        ro = item.get('reality-opts') or tls.get('reality') or item.get('reality_settings') or {}
        pbk = ro.get('public-key') or ro.get('public_key') or item.get('public-key') or ""
        sid = ro.get('short-id') or ro.get('short_id') or item.get('short-id') or ""

        return {
            "server": srv.strip('[]'), "port": port, "type": p, "pw": pw,
            "sni": sni, "pbk": pbk, "sid": sid, "name": item.get('tag') or item.get('name') or ""
        }
    except:
        return None

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
                    else:
                        for v in obj.values(): walk(v)
                elif isinstance(obj, list):
                    for i in obj: walk(i)
            walk(data)
        except: continue

    # 去重
    unique = []
    seen = set()
    for n in nodes:
        key = f"{n['server']}:{n['port']}:{n['type']}"
        if key not in seen:
            unique.append(n); seen.add(key)

    # 排序：AnyTLS 第一，HY2 第二，其他往后
    unique.sort(key=lambda x: 0 if x['type'] == 'anytls' else (1 if x['type'] == 'hysteria2' else 2))

    uris = []
    time_tag = get_beijing_time()
    for i, n in enumerate(unique, 1):
        geo = get_geo_tag(n['name'] + n['sni'] + n['server'], n['server'])
        name = f"{geo}[{n['type'].upper()}] {i:02d} ({time_tag})"
        name_enc = urllib.parse.quote(name)
        srv_uri = f"[{n['server']}]" if ':' in n['server'] else n['server']
        
        if n['type'] == 'vless':
            v_params = {"encryption": "none", "security": "reality" if n['pbk'] else "none", "sni": n['sni'] or "itunes.apple.com", "fp": "chrome", "type": "tcp"}
            if n['pbk']: v_params.update({"pbk": n['pbk'], "sid": n['sid']})
            uris.append(f"vless://{n['pw']}@{srv_uri}:{n['port']}?{urllib.parse.urlencode(v_params)}#{name_enc}")
        elif n['type'] == 'hysteria2':
            h_params = {"insecure": "1", "allowInsecure": "1", "sni": n['sni'] or "www.microsoft.com"}
            uris.append(f"hysteria2://{n['pw']}@{srv_uri}:{n['port']}?{urllib.parse.urlencode(h_params)}#{name_enc}")
        elif n['type'] == 'anytls':
            uris.append(f"anytls://{n['pw']}@{srv_uri}:{n['port']}?alpn=h3&insecure=1#{name_enc}")
        elif n['type'] == 'tuic':
            uris.append(f"tuic://{n['pw']}@{srv_uri}:{n['port']}?sni={n['sni'] or 'apple.com'}&alpn=h3#{name_enc}")

    with open("sub.txt", "w", encoding="utf-8") as f: f.write("\n".join(uris))
    with open("sub_base64.txt", "w", encoding="utf-8") as f:
        f.write(base64.b64encode("\n".join(uris).encode()).decode())

if __name__ == "__main__":
    main()
