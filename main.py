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
        
        # 1. 提取 Server 和 Port (核心修复区)
        raw_server = item.get('server') or item.get('add') or item.get('address')
        if not raw_server or str(raw_server).startswith('127.'): return None
        
        srv = str(raw_server).strip()
        # 初始尝试获取 port 字段
        port = str(item.get('port') or item.get('server_port') or "")

        # 逻辑：如果 srv 里包含冒号，则 srv 里的端口优先级最高
        if ':' in srv:
            if srv.startswith('['): # IPv6
                parts = srv.split(']:')
                srv = parts[0].replace('[', '')
                if len(parts) > 1: port = parts[1].split(',')[0] # 取逗号前的第一个端口
            else: # IPv4
                parts = srv.split(':')
                srv = parts[0]
                if len(parts) > 1: port = parts[1].split(',')[0]

        # 清洗端口：只保留纯数字
        port = "".join(re.findall(r'\d+', str(port)))
        
        # --- 致命修复：如果没拿到端口，千万不能默认给 443，必须返回 None 触发递归继续找 ---
        if not port: return None 

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

        # 3. 深度提取 Reality 参数
        tls = item.get('tls', {}) if isinstance(item.get('tls'), dict) else {}
        sni = item.get('servername') or item.get('sni') or tls.get('sni') or tls.get('server_name') or ""
        
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
                    # 如果当前层级能提取到完整信息（包含端口），就存入 nodes
                    res = get_node_info(obj)
                    if res: 
                        nodes.append(res)
                    else:
                        # 如果当前层级没提全，继续往里钻（处理 port 在更深层级的情况）
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
    time_tag = get_beijing_time()
    
    for i, n in enumerate(unique, 1):
        geo = get_geo_tag(n['name'] + n['sni'] + n['server'], n['server'])
        name = f"{geo}[{n['type'].upper()}] {i:02d} ({time_tag})"
        name_enc = urllib.parse.quote(name)
        srv_uri = f"[{n['server']}]" if ':' in n['server'] else n['server']
        
        if n['type'] == 'vless':
            v_params = {
                "encryption": "none",
                "security": "reality" if n['pbk'] else "none",
                "sni": n['sni'] or "itunes.apple.com",
                "fp": "chrome", "type": "tcp", "headerType": "none"
            }
            if n['pbk']: v_params.update({"pbk": n['pbk'], "sid": n['sid']})
            uris.append(f"vless://{n['pw']}@{srv_uri}:{n['port']}?{urllib.parse.urlencode(v_params)}#{name_enc}")
            
        elif n['type'] == 'hysteria2':
            h_params = {"insecure": "1", "allowInsecure": "1", "sni": n['sni'] or "www.microsoft.com"}
            uris.append(f"hysteria2://{n['pw']}@{srv_uri}:{n['port']}?{urllib.parse.urlencode(h_params)}#{name_enc}")
            
        elif n['type'] == 'anytls':
            uris.append(f"anytls://{n['pw']}@{srv_uri}:{n['port']}?alpn=h3&insecure=1#{name_enc}")

    with open("sub.txt", "w", encoding="utf-8") as f: f.write("\n".join(uris))
    with open("sub_base64.txt", "w", encoding="utf-8") as f:
        f.write(base64.b64encode("\n".join(uris).encode()).decode())

if __name__ == "__main__":
    main()
