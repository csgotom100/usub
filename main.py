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

def get_node_info_for_sub(item):
    """最优的 sub.txt 解析逻辑"""
    try:
        if not isinstance(item, dict): return None
        raw_server = item.get('server') or item.get('add') or item.get('address')
        if not raw_server: return None
        
        srv = str(raw_server).strip()
        port_field = str(item.get('port') or item.get('server_port') or "")
        
        # IPv6 提取
        if srv.startswith('['): 
            match = re.match(r'\[(.+)\]:(\d+)', srv)
            if match: srv, port = match.group(1), match.group(2)
            else: srv, port = srv.strip('[]'), port_field
        elif srv.count(':') > 1:
            port = port_field
        elif ':' in srv:
            parts = srv.rsplit(':', 1)
            srv, port = parts[0], parts[1]
        else:
            port = port_field

        port = "".join(re.findall(r'\d+', str(port)))
        if not port: return None 

        item_raw = str(item).lower()
        p_type = str(item.get('type') or "").lower()
        if p_type == 'mieru' or 'mieru' in item_raw: return None
        
        pw = item.get('auth') or item.get('password') or item.get('uuid') or item.get('id')
        
        # 协议识别
        if 'hysteria2' in p_type or ('auth' in item and 'bandwidth' in item) or 'hy2' in item_raw:
            p = 'hysteria2'
        elif 'tuic' in p_type or 'tuic' in item_raw:
            p = 'tuic'
        elif 'anytls' in item_raw:
            p = 'anytls'
        else:
            p = 'vless'
        
        if not pw and p != 'anytls': return None

        tls = item.get('tls', {}) if isinstance(item.get('tls'), dict) else {}
        sni = item.get('servername') or item.get('sni') or tls.get('sni') or item.get('peer') or ""
        ro = item.get('reality-opts') or tls.get('reality') or item.get('reality_settings') or {}
        pbk = ro.get('public-key') or ro.get('public_key') or item.get('public-key') or ""
        sid = ro.get('short-id') or ro.get('short_id') or item.get('short-id') or ""

        return {
            "server": srv.strip('[]'), "port": port, "type": p, "pw": pw,
            "sni": sni, "pbk": pbk, "sid": sid, "name": item.get('tag') or item.get('name') or ""
        }
    except: return None

def main():
    uris = []
    clash_proxies = [] 
    seen_clash = set()
    seen_sub = set()
    time_tag = get_beijing_time()

    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]

    for url in urls:
        try:
            r = requests.get(url, timeout=15, verify=False)
            content = r.text.strip()
            # 识别数据源类型
            is_json_source = content.startswith(('{', '['))
            data = json.loads(content) if is_json_source else yaml.safe_load(content)
            
            def walk(obj):
                if isinstance(obj, dict):
                    if 'server' in obj and 'type' in obj:
                        # --- 1. Clash 永远照搬 ---
                        ckey = f"{obj['server']}:{obj.get('port')}:{obj['type']}"
                        if ckey not in seen_clash:
                            raw_node = obj.copy()
                            raw_node['name'] = f"{raw_node.get('name', 'node')}_{time_tag}"
                            clash_proxies.append(raw_node)
                            seen_clash.add(ckey)
                        
                        # --- 2. sub.txt 定向输出 ---
                        res = get_node_info_for_sub(obj)
                        if res:
                            # 核心逻辑：如果是 HY2，且不是来自 JSON 源，则跳过转换，避免失误
                            if res['type'] == 'hysteria2' and not is_json_source:
                                return

                            skey = f"{res['server']}:{res['port']}:{res['type']}"
                            if skey not in seen_sub:
                                geo = get_geo_tag(res['name'] + res['sni'] + res['server'], res['server'])
                                name = f"{geo}[{res['type'].upper()}] {len(seen_sub)+1:02d} ({time_tag})"
                                name_enc = urllib.parse.quote(name)
                                srv_uri = f"[{res['server']}]" if ':' in res['server'] else res['server']
                                
                                if res['type'] == 'vless':
                                    params = {"encryption": "none", "security": "reality" if res['pbk'] else "none", "sni": res['sni'] or "itunes.apple.com", "fp": "chrome", "type": "tcp"}
                                    if res['pbk']: params.update({"pbk": res['pbk'], "sid": res['sid']})
                                    uris.append(f"vless://{res['pw']}@{srv_uri}:{res['port']}?{urllib.parse.urlencode(params)}#{name_enc}")
                                elif res['type'] == 'hysteria2':
                                    h_params = {"insecure": "1", "sni": res['sni'] or "www.microsoft.com"}
                                    uris.append(f"hysteria2://{res['pw']}@{srv_uri}:{res['port']}?{urllib.parse.urlencode(h_params)}#{name_enc}")
                                elif res['type'] == 'anytls':
                                    uris.append(f"anytls://{res['pw']}@{srv_uri}:{res['port']}?alpn=h3&insecure=1#{name_enc}")
                                
                                seen_sub.add(skey)
                    else:
                        for v in obj.values(): walk(v)
                elif isinstance(obj, list):
                    for i in obj: walk(i)
            walk(data)
        except: continue

    # 保存 sub.txt 和 Clash 配置
    with open("sub.txt", "w", encoding="utf-8") as f: f.write("\n".join(uris))
    with open("sub_base64.txt", "w", encoding="utf-8") as f:
        f.write(base64.b64encode("\n".join(uris).encode()).decode())
    
    clash_config = {
        "ipv6": True, "allow-lan": True, "mode": "rule",
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
