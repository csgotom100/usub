import json, requests, base64, yaml, urllib.parse, os, re, warnings
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

def get_beijing_time():
    return (datetime.utcnow() + timedelta(hours=8)).strftime("%m-%d %H:%M")

def get_geo_tag(text, server):
    words = {"🇭🇰": ["hk", "香港"], "🇺🇸": ["us", "美国"], "🇯🇵": ["jp", "日本"], "🇸🇬": ["sg", "新加坡"], "🇹🇼": ["tw", "台湾"], "🇫🇷": ["fr", "法国"], "🇩🇪": ["de", "德国"]}
    content = str(text).lower() + str(server).lower()
    for tag, keys in words.items():
        if any(k in content for k in keys): return tag
    return "🌐"

def get_node_info(item):
    try:
        if not isinstance(item, dict): return None
        
        # 1. 基础连接信息
        srv = item.get('server') or item.get('add') or item.get('address')
        if not srv or str(srv).startswith('127.'): return None
        
        srv = str(srv).strip()
        port = str(item.get('port') or item.get('server_port') or "")
        
        # IPv6 格式修复
        if srv.count(':') > 1 and not srv.startswith('['):
            if srv.endswith(':'): srv = srv + "1"
            if not port and not any(c.isalpha() for c in srv.split(':')[-1]):
                srv, port = srv.rsplit(':', 1)
        port = re.findall(r'\d+', port)[0] if re.findall(r'\d+', port) else ""
        if not port: return None

        # 2. 强力协议判定 (解决 HY2 消失的关键)
        # 将整个节点对象转为字符串，全量搜索 "HYSTERIA2"
        item_str = str(item).upper()
        p_raw = str(item.get('type') or item.get('protocol') or "").upper()
        
        if "HYSTERIA2" in item_str or "HY2" in p_raw:
            p = 'hysteria2'
        elif 'TUIC' in p_raw:
            p = 'tuic'
        elif 'ANYTLS' in p_raw:
            p = 'anytls'
        else:
            p = 'vless'

        # 3. 提取密钥 (针对 HY2, auth 和 password 是核心)
        pw = item.get('auth') or item.get('password') or item.get('uuid') or item.get('id') or item.get('token')
        if not pw and p != 'anytls': return None

        # 4. 参数提取
        tls = item.get('tls', {}) if isinstance(item.get('tls'), dict) else {}
        sni = item.get('servername') or item.get('sni') or tls.get('server_name') or ""
        
        ro = item.get('reality-opts') or tls.get('reality') or {}
        pbk = ro.get('public-key') or ro.get('public_key') or item.get('public-key') or ""
        sid = ro.get('short-id') or ro.get('short_id') or item.get('short-id') or ""

        path = ""
        if p == 'vless':
            tp = item.get('transport') or item.get('streamSettings', {})
            if isinstance(tp, dict) and (tp.get('type') == 'xhttp' or 'xhttpSettings' in tp):
                path = (tp.get('xhttpSettings') or tp).get('path') or ""
            if not path:
                path = item.get('path') or ""

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

    # 去重 & 排序
    unique = []
    seen = set()
    for n in nodes:
        key = f"{n['server']}:{n['port']}:{n['type']}"
        if key not in seen:
            unique.append(n); seen.add(key)

    unique.sort(key=lambda x: 0 if x['type'] == 'anytls' else (1 if x['type'] == 'hysteria2' else 2))

    uris = []
    clash_proxies = []
    time_tag = get_beijing_time()
    
    for i, n in enumerate(unique, 1):
        geo = get_geo_tag(n['name'] + n['sni'] + n['server'], n['server'])
        name = f"{geo}[{n['type'].upper()}] {i:02d} ({time_tag})"
        name_enc = urllib.parse.quote(name)
        srv_uri = f"[{n['server']}]" if ':' in n['server'] else n['server']
        
        if n['type'] == 'vless':
            params = {"security": "reality" if n['pbk'] else "none", "sni": n['sni'] or "apple.com", "pbk": n['pbk'], "sid": n['sid']}
            if n['path']: params.update({"type": "xhttp", "path": n['path']})
            uris.append(f"vless://{n['pw']}@{srv_uri}:{n['port']}?{urllib.parse.urlencode({k:v for k,v in params.items() if v})}#{name_enc}")
        elif n['type'] == 'hysteria2':
            uris.append(f"hysteria2://{n['pw']}@{srv_uri}:{n['port']}?insecure=1&sni={n['sni'] or 'apple.com'}#{name_enc}")
        elif n['type'] == 'anytls':
            uris.append(f"anytls://{n['pw']}@{srv_uri}:{n['port']}?alpn=h3&insecure=1#{name_enc}")
        elif n['type'] == 'tuic':
            uris.append(f"tuic://{n['pw']}@{srv_uri}:{n['port']}?sni={n['sni'] or 'apple.com'}&alpn=h3#{name_enc}")

        if n['type'] in ['vless', 'hysteria2', 'tuic']:
            p = {"name": name, "server": n['server'], "port": int(n['port'])}
            if n['type'] == 'vless':
                p.update({"type": "vless", "uuid": n['pw'], "tls": True, "servername": n['sni'] or "apple.com", "network": "xhttp" if n['path'] else "tcp", "udp": True})
                if n['pbk']: p.update({"reality-opts": {"public-key": n['pbk'], "short-id": n['sid']}})
                if n['path']: p.update({"xhttp-opts": {"path": n['path'], "mode": "auto"}})
            elif n['type'] == 'hysteria2':
                p.update({"type": "hysteria2", "password": n['pw'], "sni": n['sni'] or "apple.com", "skip-cert-verify": True})
            elif n['type'] == 'tuic':
                p.update({"type": "tuic", "uuid": n['pw'], "sni": n['sni'] or "apple.com", "alpn": ["h3"]})
            clash_proxies.append(p)

    # 导出文件
    with open("sub.txt", "w", encoding="utf-8") as f: f.write("\n".join(uris))
    with open("sub_base64.txt", "w", encoding="utf-8") as f:
        f.write(base64.b64encode("\n".join(uris).encode()).decode())
    
    clash_config = {
        "ipv6": True,
        "proxies": clash_proxies,
        "proxy-groups": [
            {"name": "🚀 节点选择", "type": "select", "proxies": ["♻️ 自动选择", "DIRECT"] + [p['name'] for p in clash_proxies]},
            {"name": "♻️ 自动选择", "type": "url-test", "url": "http://www.gstatic.com/generate_204", "interval": 300, "proxies": [p['name'] for p in clash_proxies]}
        ],
        "rules": ["MATCH,🚀 节点选择"]
    }
    with open("config.yaml", "w", encoding="utf-8") as f:
        yaml.dump(clash_config, f, allow_unicode=True, sort_keys=False)

if __name__ == "__main__":
    main()
