import json, requests, base64, yaml, urllib.parse, os, re, warnings
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

def get_beijing_time():
    return (datetime.utcnow() + timedelta(hours=8)).strftime("%m-%d %H:%M")

# --- 核心提取逻辑：保持最新的 IPv6 修复版 ---
def get_node_info(item):
    try:
        if not isinstance(item, dict): return None
        raw_server = item.get('server') or item.get('add') or item.get('address')
        if not raw_server or str(raw_server).startswith('127.'): return None
        
        srv = str(raw_server).strip()
        port = str(item.get('port') or item.get('server_port') or "")

        if ':' in srv:
            if srv.startswith('['):
                parts = srv.split(']:')
                srv = parts[0].replace('[', '')
                if len(parts) > 1: port = parts[1].split(',')[0]
            elif srv.count(':') == 1:
                s, p = srv.split(':', 1)
                srv, port = s, p.split(',')[0]
            else:
                parts = srv.rsplit(':', 1)
                if parts[1].isdigit() and 1 <= len(parts[1]) <= 5:
                    srv, port = parts[0], parts[1]
        
        port = "".join(re.findall(r'\d+', str(port)))
        if not port: return None 

        pw = item.get('auth') or item.get('password') or item.get('uuid') or item.get('id')
        p = 'vless'
        if 'tuic' in str(item).lower(): p = 'tuic'
        elif 'anytls' in str(item).lower(): p = 'anytls'
        
        tls = item.get('tls', {}) if isinstance(item.get('tls'), dict) else {}
        sni = item.get('servername') or item.get('sni') or tls.get('sni') or ""
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
        print(f"DEBUG: 正在扫描源 -> {url}") # 在日志中打印来源
        try:
            r = requests.get(url, timeout=15, verify=False)
            content = r.text.strip()
            data = json.loads(content) if content.startswith(('{', '[')) else yaml.safe_load(content)
            
            def walk(obj):
                if isinstance(obj, dict):
                    res = get_node_info(obj)
                    if res:
                        # 重点：记录该节点来自哪个 URL
                        if res['server'] == "157.254.223.48":
                            print(f"!!! 找到目标节点 157.254.223.48，来源: {url}")
                        nodes.append(res)
                    else:
                        for v in obj.values(): walk(v)
                elif isinstance(obj, list):
                    for i in obj: walk(i)
            walk(data)
        except Exception as e:
            print(f"DEBUG: 跳过错误源 {url}: {e}")
            continue

    # 去重与生成逻辑保持不变...
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
        srv_uri = f"[{n['server']}]" if ':' in n['server'] else n['server']
        if n['type'] == 'vless':
            v_params = {"encryption": "none", "security": "reality" if n['pbk'] else "none", "sni": n['sni'] or "itunes.apple.com", "fp": "chrome", "type": "tcp"}
            if n['pbk']: v_params.update({"pbk": n['pbk'], "sid": n['sid']})
            uris.append(f"vless://{n['pw']}@{srv_uri}:{n['port']}?{urllib.parse.urlencode(v_params)}#Node_{i}")
        elif n['type'] == 'anytls':
            uris.append(f"anytls://{n['pw']}@{srv_uri}:{n['port']}?alpn=h3&insecure=1#Node_{i}")

    with open("sub.txt", "w", encoding="utf-8") as f: f.write("\n".join(uris))
    print(f"DEBUG: 任务完成，共生成 {len(uris)} 个节点")

if __name__ == "__main__":
    main()
