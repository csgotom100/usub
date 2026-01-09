import json, requests, base64, yaml, urllib.parse, os, re, warnings
from datetime import datetime, timedelta

# 忽略不安全的 HTTPS 请求警告
warnings.filterwarnings("ignore")

def get_beijing_time():
    return (datetime.utcnow() + timedelta(hours=8)).strftime("%m-%d %H:%M")

def get_geo_tag(text, server):
    """打磨地理位置匹配：增加常用地区图标"""
    words = {
        "🇭🇰": ["hk", "香港", "hongkong", "hkg"],
        "🇺🇸": ["us", "美国", "states", "america", "united"],
        "🇯🇵": ["jp", "日本", "tokyo", "japan", "osaka"],
        "🇸🇬": ["sg", "新加坡", "singapore", "sin"],
        "🇹🇼": ["tw", "台湾", "taiwan"],
        "🇰🇷": ["kr", "韩国", "korea", "seoul"],
        "🇫🇷": ["fr", "法国", "france"]
    }
    # 综合搜索：节点标签、服务器地址、SNI
    content = str(text).lower() + str(server).lower()
    for tag, keys in words.items():
        if any(k in content for k in keys):
            return tag
    return "🌐"

def get_node_info(item):
    """深度打磨：支持 VLESS, Hy2, TUIC, AnyTLS"""
    try:
        if not isinstance(item, dict): return None
        raw_server = item.get('server') or item.get('add') or item.get('address')
        if not raw_server or str(raw_server).startswith('127.'): return None
        
        # 1. 服务器地址与端口清洗
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

        if port: # 关键：处理 28000-29000 这种格式，只取第一个数字
            port = str(port).split(',')[0].split('-')[0].split('/')[0].strip()
        if not server or not port or 'None' in str(port): return None

        # 2. 提取密钥（打磨：适配更多协议字段）
        secret = item.get('auth') or item.get('auth_str') or item.get('password') or \
                 item.get('uuid') or item.get('id') or item.get('token')
        if not secret: return None

        # 3. 判定协议类型 (打磨关键点)
        p_raw = str(item.get('type') or item.get('protocol', '')).lower()
        if any(x in p_raw for x in ['hy2', 'hysteria2']) or 'auth' in item:
            p_type = 'hysteria2'
        elif 'tuic' in p_raw:
            p_type = 'tuic'
        elif 'anytls' in p_raw:
            p_type = 'anytls'
        elif 'vless' in p_raw or 'uuid' in item:
            p_type = 'vless'
        else:
            return None # 无法识别的丢弃

        # 4. 提取 TLS/SNI/Reality
        tls_obj = item.get('tls', {}) if isinstance(item.get('tls'), dict) else {}
        sni = item.get('servername') or item.get('sni') or tls_obj.get('server_name') or ""
        
        reality_obj = item.get('reality-opts') or tls_obj.get('reality') or item.get('reality') or {}
        pbk = reality_obj.get('public-key') or reality_obj.get('public_key') or item.get('public-key') or ""
        sid = reality_obj.get('short-id') or reality_obj.get('short_id') or item.get('short-id') or ""
        
        # 提取 xhttp 路径
        xh_obj = item.get('xhttp-opts') or item.get('xhttp') or {}
        xh_path = xh_obj.get('path') or ""

        return {
            "server": server, "port": port, "type": p_type, "secret": secret,
            "sni": sni, "pbk": pbk, "sid": sid, "path": xh_path, 
            "tag": item.get('tag') or item.get('name') or ""
        }
    except: return None

def main():
    raw_nodes_data = []
    # 依然从 sources.txt 读取，保证源的灵活性
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

    # 去重逻辑
    unique_nodes = []
    seen = set()
    for n in raw_nodes_data:
        key = (n['server'], n['port'], n['secret'], n['type'])
        if key not in seen:
            unique_nodes.append(n); seen.add(key)

    # 排序：AnyTLS 永远第一
    unique_nodes.sort(key=lambda x: 0 if x['type'] == 'anytls' else 1)

    uri_links = []
    time_tag = get_beijing_time()
    for i, n in enumerate(unique_nodes, 1):
        # 加上打磨后的地理标志
        geo = get_geo_tag(n['tag'] + n['sni'], n['server'])
        node_name = f"{geo}[{n['type'].upper()}] {i:02d} ({time_tag})"
        name_enc = urllib.parse.quote(node_name)
        
        # 适配 IPv6 URI 格式
        srv_uri = n['server']
        if ':' in srv_uri and not srv_uri.startswith('['):
            srv_uri = f"[{srv_uri}]"
        
        # 格式化不同协议的 URI
        if n['type'] == 'hysteria2':
            uri_links.append(f"hysteria2://{n['secret']}@{srv_uri}:{n['port']}?insecure=1&sni={n['sni']}#{name_enc}")
        elif n['type'] == 'vless':
            params = {"security": "reality" if n['pbk'] else "none", "sni": n['sni'], "pbk": n['pbk'], "sid": n['sid']}
            if n['path']: params.update({"type": "xhttp", "path": n['path']})
            uri_links.append(f"vless://{n['secret']}@{srv_uri}:{n['port']}?{urllib.parse.urlencode({k:v for k,v in params.items() if v})}#{name_enc}")
        elif n['type'] == 'anytls':
            uri_links.append(f"anytls://{n['secret']}@{srv_uri}:{n['port']}?alpn=h3&insecure=1#{name_enc}")
        elif n['type'] == 'tuic':
            uri_links.append(f"tuic://{n['secret']}@{srv_uri}:{n['port']}?sni={n['sni']}&alpn=h3#{name_enc}")

    # 写入文件
    with open("sub.txt", "w", encoding="utf-8") as f: f.write("\n".join(uri_links))
    with open("sub_base64.txt", "w", encoding="utf-8") as f:
        f.write(base64.b64encode("\n".join(uri_links).encode()).decode())
    
    # 关键：生成 config.yaml 供 v2rayN 导入自定义服务器 (这是支持 TUIC 最稳的方式)
    clash_proxies = []
    for i, n in enumerate(unique_nodes, 1):
        geo = get_geo_tag(n['tag'] + n['sni'], n['server'])
        p = {"name": f"{geo}[{n['type'].upper()}] {i:02d}", "server": n['server'].replace('[','').replace(']',''), "port": int(n['port'])}
        if n['type'] == 'vless':
            p.update({"type": "vless", "uuid": n['secret'], "tls": True, "servername": n['sni'], "reality-opts": {"public-key": n['pbk'], "short-id": n['sid']}})
        elif n['type'] == 'hysteria2':
            p.update({"type": "hysteria2", "password": n['secret'], "sni": n['sni'], "skip-cert-verify": True})
        elif n['type'] == 'tuic':
            p.update({"type": "tuic", "uuid": n['secret'], "sni": n['sni'], "alpn": ["h3"]})
        clash_proxies.append(p)
    
    with open("config.yaml", "w", encoding="utf-8") as f:
        yaml.dump({"proxies": clash_proxies}, f, allow_unicode=True, sort_keys=False)

if __name__ == "__main__":
    main()
