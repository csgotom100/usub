import json, requests, base64, yaml, urllib.parse, os, re, warnings
from datetime import datetime, timedelta

# 忽略不安全的 HTTPS 请求警告
warnings.filterwarnings("ignore")

def get_beijing_time():
    return (datetime.utcnow() + timedelta(hours=8)).strftime("%m-%d %H:%M")

def get_geo_tag(text, server):
    """地理标志：匹配标签、服务器地址或SNI"""
    words = {
        "🇭🇰": ["hk", "香港", "hongkong", "hkg"],
        "🇺🇸": ["us", "美国", "states", "america"],
        "🇯🇵": ["jp", "日本", "tokyo", "japan"],
        "🇸🇬": ["sg", "新加坡", "singapore"],
        "🇹🇼": ["tw", "台湾", "taiwan"],
        "🇰🇷": ["kr", "韩国", "korea"],
        "🇫🇷": ["fr", "法国", "france"],
        "🇩🇪": ["de", "德国", "germany"]
    }
    content = str(text).lower() + str(server).lower()
    for tag, keys in words.items():
        if any(k in content for k in keys): return tag
    return "🌐"

def get_node_info(item):
    """深度解析：VLESS(xhttp/Reality), Hy2, TUIC, AnyTLS"""
    try:
        if not isinstance(item, dict): return None
        raw_server = item.get('server') or item.get('add') or item.get('address')
        if not raw_server or str(raw_server).startswith('127.'): return None
        
        # 1. 提取服务器和端口
        server_str = str(raw_server).strip()
        server, port = "", ""
        if ']:' in server_str: 
            server, port = server_str.split(']:')[0] + ']', server_str.split(']:')[1]
        elif server_str.startswith('[') and ']' in server_str:
            server, port = server_str, (item.get('port') or item.get('server_port'))
        elif server_str.count(':') == 1:
            server, port = server_str.split(':')
        else:
            server, port = server_str, (item.get('port') or item.get('server_port') or item.get('port_num'))

        if port:
            port = str(port).split(',')[0].split('-')[0].split('/')[0].strip()
        if not server or not port or 'None' in str(port): return None

        # 2. 提取密钥/协议
        secret = item.get('auth') or item.get('auth_str') or item.get('password') or item.get('uuid') or item.get('id')
        if not secret: return None

        p_raw = str(item.get('type') or item.get('protocol', '')).lower()
        
        # 3. 详细参数提取 (含 xhttp)
        tls_obj = item.get('tls', {}) if isinstance(item.get('tls'), dict) else {}
        sni = item.get('servername') or item.get('sni') or tls_obj.get('server_name') or ""
        
        # Reality 处理
        reality_obj = item.get('reality-opts') or tls_obj.get('reality') or item.get('reality') or {}
        pbk = reality_obj.get('public-key') or reality_obj.get('public_key') or item.get('public_key') or ""
        sid = reality_obj.get('short-id') or reality_obj.get('short_id') or item.get('short_id') or ""
        
        # --- 核心：提取 xhttp 配置 ---
        transport = item.get('transport') or item.get('streamSettings', {})
        if isinstance(transport, str): transport = {} # 防止格式错误
        
        network = item.get('network') or transport.get('network') or "tcp"
        xh_obj = item.get('xhttp-opts') or item.get('xhttp') or transport.get('xhttpSettings') or {}
        path = xh_obj.get('path') or item.get('path') or ""
        host = xh_obj.get('host') or item.get('host') or ""

        # 4. 判定协议类型
        if any(x in p_raw for x in ['hy2', 'hysteria2']) or 'auth' in item:
            p_type = 'hysteria2'
        elif 'tuic' in p_raw:
            p_type = 'tuic'
        elif 'anytls' in p_raw:
            p_type = 'anytls'
        else:
            p_type = 'vless'

        return {
            "server": server, "port": port, "type": p_type, "secret": secret,
            "sni": sni, "pbk": pbk, "sid": sid, "network": network, "path": path, "host": host,
            "tag": item.get('tag') or item.get('name') or ""
        }
    except: return None

def main():
    raw_nodes_data = []
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]

    for url in urls:
        try:
            r = requests.get(url, timeout=15, verify=False)
            if r.status_code != 200: continue
            content = r.text.strip()
            data = json.loads(content) if (content.startswith('{') or content.startswith('[')) else yaml.safe_load(content)
            
            def extract_dicts(obj):
                res = []
                if isinstance(obj, dict):
                    res.append(obj)
                    for v in obj.values(): res.extend(extract_dicts(v))
                elif isinstance(obj, list):
                    for i in obj: res.extend(extract_dicts(i))
                return res
            
            for d in extract_dicts(data):
                node = get_node_info(d)
                if node: raw_nodes_data.append(node)
        except: continue

    # 去重
    unique_nodes = []
    seen = set()
    for n in raw_nodes_data:
        key = (n['server'], n['port'], n['secret'], n['type'])
        if key not in seen:
            unique_nodes.append(n); seen.add(key)

    unique_nodes.sort(key=lambda x: 0 if x['type'] == 'anytls' else 1)
    
    uri_links = []
    time_tag = get_beijing_time()
    for i, n in enumerate(unique_nodes, 1):
        geo = get_geo_tag(n['tag'] + n['sni'], n['server'])
        node_name = f"{geo}[{n['type'].upper()}] {i:02d} ({time_tag})"
        name_enc = urllib.parse.quote(node_name)
        srv_uri = f"[{n['server']}]" if ':' in n['server'] and not n['server'].startswith('[') else n['server']
        
        if n['type'] == 'vless':
            params = {
                "security": "reality" if n['pbk'] else "none",
                "sni": n['sni'], "pbk": n['pbk'], "sid": n['sid'],
                "type": n['network'], "path": n['path'], "host": n['host']
            }
            uri_links.append(f"vless://{n['secret']}@{srv_uri}:{n['port']}?{urllib.parse.urlencode({k:v for k,v in params.items() if v})}#{name_enc}")
        elif n['type'] == 'hysteria2':
            uri_links.append(f"hysteria2://{n['secret']}@{srv_uri}:{n['port']}?insecure=1&sni={n['sni']}#{name_enc}")
        elif n['type'] == 'anytls':
            uri_links.append(f"anytls://{n['secret']}@{srv_uri}:{n['port']}?alpn=h3&insecure=1#{name_enc}")
        elif n['type'] == 'tuic':
            uri_links.append(f"tuic://{n['secret']}@{srv_uri}:{n['port']}?sni={n['sni']}&alpn=h3#{name_enc}")

    with open("sub.txt", "w", encoding="utf-8") as f: f.write("\n".join(uri_links))
    with open("sub_base64.txt", "w", encoding="utf-8") as f:
        f.write(base64.b64encode("\n".join(uri_links).encode()).decode())
    
    # 供 v2rayN 导入自定义服务器 (支持 TUIC)
    clash_proxies = []
    for i, n in enumerate(unique_nodes, 1):
        geo = get_geo_tag(n['tag'] + n['sni'], n['server'])
        p = {"name": f"{geo}[{n['type'].upper()}] {i:02d}", "server": n['server'].replace('[','').replace(']',''), "port": int(n['port'])}
        if n['type'] == 'vless':
            p.update({"type": "vless", "uuid": n['secret'], "tls": True, "servername": n['sni'], "network": n['network'], "reality-opts": {"public-key": n['pbk'], "short-id": n['sid']}})
            if n['network'] == 'xhttp': p.update({"xhttp-opts": {"path": n['path']}})
        elif n['type'] == 'hysteria2':
            p.update({"type": "hysteria2", "password": n['secret'], "sni": n['sni'], "skip-cert-verify": True})
        elif n['type'] == 'tuic':
            p.update({"type": "tuic", "uuid": n['secret'], "sni": n['sni'], "alpn": ["h3"]})
        clash_proxies.append(p)
