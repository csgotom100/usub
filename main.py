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
        if not raw_server or str(raw_server).startswith('127.'): return None
        
        srv = str(raw_server).strip()
        port = str(item.get('port') or "")

        # 1. 智能处理 IP:PORT
        if ':' in srv:
            if srv.startswith('['):
                parts = srv.split(']:')
                srv = parts[0].replace('[', '')
                port = parts[1] if len(parts) > 1 else port
            else:
                # 兼容 1.1.1.1:27921,28000 这种格式
                srv_parts = srv.split(':', 1)
                srv = srv_parts[0]
                port = srv_parts[1] if not port else port
        
        # 端口只取第一组数字
        port = re.findall(r'\d+', str(port))[0] if re.findall(r'\d+', str(port)) else "443"
        
        # 2. 识别协议与密钥
        item_raw = str(item).lower()
        pw = item.get('auth') or item.get('password') or item.get('uuid') or item.get('id')
        
        if 'auth' in item and 'bandwidth' in item or 'hysteria2' in item_raw:
            p = 'hysteria2'
        elif 'tuic' in item_raw:
            p = 'tuic'
        elif 'anytls' in item_raw:
            p = 'anytls'
        else:
            p = 'vless'

        if not pw and p != 'anytls': return None

        # 3. 深度提取 TLS/Reality 参数 (这是不通的关键)
        tls = item.get('tls', {}) if isinstance(item.get('tls'), dict) else {}
        sni = item.get('servername') or item.get('sni') or tls.get('sni') or tls.get('server_name') or ""
        
        # 提取 PBK 和 SID
        ro = item.get('reality-opts') or tls.get('reality') or item.get('reality_settings') or {}
        pbk = ro.get('public-key') or ro.get('public_key') or item.get('public-key') or ""
        sid = ro.get('short-id') or ro.get('short_id') or item.get('short-id') or ""

        return {
            "server": srv.strip('[]'), "port": port, "type": p, "pw": pw,
            "sni": sni, "pbk": pbk, "sid": sid, "name": item.get('tag') or item.get('name') or ""
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
                    if not res:
                        for v in obj.values(): walk(v)
                elif isinstance(obj, list):
                    for i in obj: walk(i)
            walk(data)
        except: continue

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
        # 修正 IPv6 符号
        srv_uri = f"[{n['server']}]" if ':' in n['server'] else n['server']
        
        # --- 核心修复：URI 参数对齐 ---
        if n['type'] == 'vless':
            v_params = {
                "encryption": "none",
                "security": "reality" if n['pbk'] else "none",
                "sni": n['sni'] or "itunes.apple.com",
                "fp": "chrome",
                "type": "tcp",
                "headerType": "none"
            }
            if n['pbk']: v_params.update({"pbk": n['pbk'], "sid": n['sid']})
            uris.append(f"vless://{n['pw']}@{srv_uri}:{n['port']}?{urllib.parse.urlencode(v_params)}#{name_enc}")
            
        elif n['type'] == 'hysteria2':
            h_params = {
                "insecure": "1",
                "allowInsecure": "1",
                "sni": n['sni'] or "www.microsoft.com"
            }
            uris.append(f"hysteria2://{n['pw']}@{srv_uri}:{n['port']}?{urllib.parse.urlencode(h_params)}#{name_enc}")
            
        elif n['type'] == 'tuic':
            uris.append(f"tuic://{n['pw']}@{srv_uri}:{n['port']}?sni={n['sni'] or 'apple.com'}&alpn=h3#{name_enc}")
        elif n['type'] == 'anytls':
            uris.append(f"anytls://{n['pw']}@{srv_uri}:{n['port']}?alpn=h3&insecure=1#{name_enc}")

        # Clash Proxies (同步更新)
        if n['type'] in ['vless', 'hysteria2', 'tuic']:
            p = {"name": name, "server": n['server'], "port": int(n['port'])}
            if n['type'] == 'vless':
                p.update({"type": "vless", "uuid": n['pw'], "tls": True, "servername": n['sni'] or "itunes.apple.com", "network": "tcp", "udp": True})
                if n['pbk']: p.update({"reality-opts": {"public-key": n['pbk'], "short-id": n['sid']}, "client-fingerprint": "chrome"})
            elif n['type'] == 'hysteria2':
                p.update({"type": "hysteria2", "password": n['pw'], "sni": n['sni'] or "www.microsoft.com", "skip-cert-verify": True})
            elif n['type'] == 'tuic':
                p.update({"type": "tuic", "uuid": n['pw'], "sni": n['sni'] or "apple.com", "alpn": ["h3"]})
            clash_proxies.append(p)

    # 保存
    with open("sub.txt", "w", encoding="utf-8") as f: f.write("\n".join(uris))
    with open("sub_base64.txt", "w", encoding="utf-8") as f:
        f.write(base64.b64encode("\n".join(uris).encode()).decode())
    
    clash_config = {"ipv6": True, "proxies": clash_proxies, "proxy-groups": [{"name": "🚀 节点选择", "type": "select", "proxies": ["♻️ 自动选择", "DIRECT"] + [p['name'] for p in clash_proxies]}], "rules": ["MATCH,🚀 节点选择"]}
    with open("config.yaml", "w", encoding="utf-8") as f:
        yaml.dump(clash_config, f, allow_unicode=True, sort_keys=False)

if __name__ == "__main__":
    main()
