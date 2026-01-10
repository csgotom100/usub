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
        # 1. 基础地址提取
        srv = item.get('server') or item.get('add') or item.get('address')
        if not srv or str(srv).startswith('127.'): return None
        
        srv = str(srv).strip()
        port = str(item.get('port') or item.get('server_port') or "")
        
        # --- IPv6 健壮解析与补全 ---
        if srv.count(':') > 1 and not srv.startswith('['):
            if srv.endswith(':'): srv = srv + "1" # 修复末尾带冒号的残缺地址
            # 尝试从 server 字符串分离端口
            if not port and not any(c.isalpha() for c in srv.split(':')[-1]):
                srv, port = srv.rsplit(':', 1)

        port = re.findall(r'\d+', port)[0] if re.findall(r'\d+', port) else ""
        if not port: return None

        # 2. 协议判定 (逻辑重组，防止 HY2 被漏掉)
        p_raw = str(item.get('type') or item.get('protocol') or "").lower()
        
        # 提取密钥：HY2 优先看 auth/password，VLESS 优先看 uuid/id
        pw = item.get('auth') or item.get('password') or item.get('uuid') or item.get('id') or item.get('token')
        
        if any(x in p_raw for x in ['hy2', 'hysteria2']):
            p = 'hysteria2'
        elif 'tuic' in p_raw:
            p = 'tuic'
        elif 'anytls' in p_raw:
            p = 'anytls'
        elif 'vless' in p_raw:
            p = 'vless'
        # 兜底识别：根据特有字段识别协议
        elif 'auth' in item and ('up' in item or 'down' in item): 
            p = 'hysteria2'
        elif 'uuid' in item or 'id' in item:
            p = 'vless'
        else:
            return None # 无法识别协议的丢弃

        if not pw and p != 'anytls': return None
        
        # 3. 参数提取
        tls = item.get('tls', {}) if isinstance(item.get('tls'), dict) else {}
        sni = item.get('servername') or item.get('sni') or tls.get('server_name') or item.get('peer') or ""
        
        ro = item.get('reality-opts') or tls.get('reality') or {}
        if not isinstance(ro, dict): ro = {}
        pbk = ro.get('public-key') or ro.get('public_key') or item.get('public-key') or ""
        sid = ro.get('short-id') or ro.get('short_id') or item.get('short-id') or ""

        # xhttp 适配
        path = ""
        tp = item.get('transport') or item.get('streamSettings', {})
        if isinstance(tp, dict):
            if tp.get('type') == 'xhttp' or 'xhttpSettings' in tp:
                xh = tp.get('xhttpSettings') or tp
                path = xh.get('path') or ""
        if not path:
            xh_opts = item.get('xhttp-opts') or item.get('xhttp') or {}
            if isinstance(xh_opts, dict): path = xh_opts.get('path') or ""
        if not path and isinstance(item.get('path'), str): path = item.get('path')

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

    # 4. 去重：防止 IPv4 和 IPv6 因为名称不同产生冗余，只看核心连接信息
    unique = []
    seen = set()
    for n in nodes:
        key = f"{n['server']}:{n['port']}:{n['type']}"
        if key not in seen:
            unique.append(n); seen.add(key)

    # 5. 排序：AnyTLS 第一，HY2 第二，其他往后
    def get_sort_score(node_type):
        scores = {"anytls": 0, "hysteria2": 1, "tuic": 2, "vless": 3}
        return scores.get(node_type, 9)
    unique.sort(key=lambda x: get_sort_score(x['type']))

    uris = []
    clash_proxies = []
    time_tag = get_beijing_time()
    
    for i, n in enumerate(unique, 1):
        geo = get_geo_tag(n['name'] + n['sni'] + n['server'], n['server'])
        name = f"{geo}[{n['type'].upper()}] {i:02d} ({time_tag})"
        name_enc = urllib.parse.quote(name)
        srv_uri = f"[{n['server']}]" if ':' in n['server'] else n['server']
        
        # sub.txt 格式
        if n['type'] == 'vless':
            params = {"security": "reality" if n['pbk'] else "none", "sni": n['sni'] or "apple.com", "pbk": n['pbk'], "sid": n['sid']}
            if n['path']: params.update({"type": "xhttp", "path": n['path'], "mode": "auto"})
            uris.append(f"vless://{n['pw']}@{srv_uri}:{n['port']}?{urllib.parse.urlencode({k:v for k,v in params.items() if v})}#{name_enc}")
        elif n['type'] == 'hysteria2':
            uris.append(f"hysteria2://{n['pw']}@{srv_uri}:{n['port']}?insecure=1&sni={n['sni'] or 'apple.com'}#{name_enc}")
        elif n['type'] == 'anytls':
            uris.append(f"anytls://{n['pw']}@{srv_uri}:{n['port']}?alpn=h3&insecure=1#{name_enc}")
        elif n['type'] == 'tuic':
            uris.append(f"tuic://{n['pw']}@{srv_uri}:{n['port']}?sni={n['sni'] or 'apple.com'}&alpn=h3#{name_enc}")

        # Clash 格式 (注入关键的 ipv6: true 开关)
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

    with open("sub.txt", "w", encoding="utf-8") as f: f.write("\n".join(uris))
    with open("sub_base64.txt", "w", encoding="utf-8") as f:
        f.write(base64.b64encode("\n".join(uris).encode()).decode())
    
    clash_config = {
        "ipv6": True, # 确保 Clash 内核启用 IPv6
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
