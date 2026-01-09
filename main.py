import requests, yaml, base64, os, json, re
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode

def get_beijing_time():
    return (datetime.utcnow() + timedelta(hours=8)).strftime("%m-%d %H:%M")

def extract_geo_from_text(text):
    """从原始文本或标签中用正则提取地理位置关键词"""
    keywords = {
        "HK": ["香港", "HK", "Hong Kong", "HongKong"],
        "US": ["美国", "US", "United States", "America"],
        "JP": ["日本", "JP", "Japan", "Tokyo"],
        "SG": ["新加坡", "SG", "Singapore"],
        "TW": ["台湾", "TW", "Taiwan"],
        "KR": ["韩国", "KR", "Korea", "Seoul"],
        "DE": ["德国", "Germany", "DE"],
        "UK": ["英国", "UK", "Britain"],
    }
    flags = {"HK": "🇭🇰", "US": "🇺🇸", "JP": "🇯🇵", "SG": "🇸🇬", "TW": "🇹🇼", "KR": "🇰🇷", "DE": "🇩🇪", "UK": "🇬🇧"}
    
    for code, words in keywords.items():
        if any(word.lower() in text.lower() for word in words):
            return flags.get(code, code)
    return "🌐"

def parse_content(content):
    nodes = []
    # --- 策略 A: 深度扫描 JSON ---
    try:
        data = json.loads(content)
        # 获取所有可能的对象（顶级或 outbounds）
        items = []
        if isinstance(data, dict):
            if "outbounds" in data: items.extend(data["outbounds"])
            items.append(data) # 顶级也算
        elif isinstance(data, list):
            items.extend(data)

        for out in items:
            if not isinstance(out, dict): continue
            p = out.get('protocol') or out.get('type')
            tag = out.get('tag') or out.get('name') or ""
            geo = extract_geo_from_text(tag + content[:500]) # 从标签或内容头部抓地理信息

            # VLESS 逻辑
            if p == 'vless':
                v_list = out.get('settings', {}).get('vnext', [{}])
                v = v_list[0] if v_list else {}
                u_list = v.get('users', [{}]) or out.get('settings', {}).get('users', [{}])
                u = u_list[0] if u_list else {}
                s = out.get('streamSettings', {})
                r = s.get('realitySettings') or out.get('tls', {}).get('reality', {})
                xh = s.get('xhttpSettings', {})
                nodes.append({
                    'name': tag, 'geo': geo, 'type': 'vless',
                    'server': v.get('address') or out.get('server'),
                    'port': v.get('port') or out.get('server_port'),
                    'uuid': u.get('id') or out.get('uuid'),
                    'flow': u.get('flow', ''), 'network': s.get('network') or 'tcp',
                    'servername': r.get('serverName') or out.get('tls', {}).get('server_name', ''),
                    'reality-opts': {'public-key': r.get('publicKey') or r.get('public_key', ''), 'short-id': r.get('shortId') or r.get('short_id', '')},
                    'xhttp-opts': {'path': xh.get('path', ''), 'mode': xh.get('mode', 'auto')},
                    'client-fingerprint': r.get('fingerprint', 'chrome')
                })

            # Hysteria2 逻辑 (兼容更多变种)
            elif p in ['hysteria2', 'hy2'] or ('server' in out and ('auth' in out or 'password' in out)):
                srv = out.get('server') or out.get('settings', {}).get('server', '')
                if not srv: continue
                # 处理 8.8.8.8:443 格式
                host = srv.split(',')[0] if ',' in srv else srv
                ip = host.rsplit(':', 1)[0] if ':' in host else host
                port = int(host.rsplit(':', 1)[1]) if ':' in host else out.get('port', 443)
                
                nodes.append({
                    'name': tag, 'geo': geo, 'type': 'hysteria2',
                    'server': ip, 'port': port,
                    'password': out.get('auth') or out.get('password') or out.get('settings', {}).get('auth'),
                    'sni': out.get('sni') or out.get('tls', {}).get('server_name') or 'apple.com'
                })

            # TUIC 逻辑
            elif p == 'tuic':
                v = out.get('settings', {}).get('vnext', [{}])[0]
                u = v.get('users', [{}])[0]
                nodes.append({
                    'name': tag, 'geo': geo, 'type': 'tuic',
                    'server': v.get('address') or out.get('server'),
                    'port': v.get('port') or out.get('server_port'),
                    'uuid': u.get('uuid') or u.get('id'),
                    'password': u.get('password'), 'sni': out.get('sni', ''), 'alpn': ['h3']
                })
    except: pass

    # --- 策略 B: YAML 解析 ---
    try:
        y = yaml.safe_load(content)
        if isinstance(y, dict) and 'proxies' in y:
            for p in y['proxies']:
                p['geo'] = extract_geo_from_text(p.get('name', ''))
                nodes.append(p)
    except: pass
    return nodes

def generate_uri(p):
    try:
        t, addr, port, name = p.get('type').lower(), p.get('server'), p.get('port'), quote(p.get('name', ''))
        if t == 'vless':
            ro, xh = p.get('reality-opts', {}), p.get('xhttp-opts', {})
            params = {"security": "reality", "sni": p.get('servername'), "pbk": ro.get('public-key'), "sid": ro.get('short-id'), "type": p.get('network'), "flow": p.get('flow')}
            if p.get('network') == 'xhttp': params["path"] = xh.get('path'); params["mode"] = xh.get('mode')
            return f"vless://{p.get('uuid')}@{addr}:{port}?{urlencode({k:v for k,v in params.items() if v})}#{name}"
        elif t in ['hysteria2', 'hy2']:
            return f"hysteria2://{p.get('password')}@{addr}:{port}?insecure=1&sni={p.get('sni', '')}#{name}"
        elif t == 'tuic':
            val = p.get('uuid') or p.get('password')
            return f"tuic://{val}@{addr}:{port}?sni={p.get('sni', '')}&alpn=h3#{name}"
    except: return None

def main():
    all_nodes = []
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]

    for url in urls:
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200: all_nodes.extend(parse_content(r.text))
        except: continue

    unique = []
    seen = set()
    for p in all_nodes:
        fp = f"{p.get('server')}:{p.get('port')}"
        if fp not in seen:
            seen.add(fp); unique.append(p)

    time_tag = get_beijing_time()
    for i, p in enumerate(unique):
        # 组装最终名字：[旗帜] [协议] 编号 (时间)
        p['name'] = f"{p.get('geo', '🌐')}[{p.get('type').upper()}] {i+1:02d} ({time_tag})"

    # Clash & Sub 生成
    node_names = [x['name'] for x in unique]
    clash_conf = {
        "proxies": unique,
        "proxy-groups": [
            {"name": "🚀 节点选择", "type": "select", "proxies": ["♻️ 自动选择", "DIRECT"] + node_names},
            {"name": "♻️ 自动选择", "type": "url-test", "url": "http://www.gstatic.com/generate_204", "interval": 300, "proxies": node_names},
            {"name": "🎯 全球直连", "type": "select", "proxies": ["DIRECT", "🚀 节点选择"]}
        ],
        "rules": ["GEOIP,CN,🎯 全球直连", "MATCH,🚀 节点选择"]
    }
    with open('config.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(clash_conf, f, allow_unicode=True, sort_keys=False)
    
    uris = [generate_uri(p) for p in unique if generate_uri(p)]
    with open('sub.txt', 'w', encoding='utf-8') as f: f.write("\n".join(uris))
    with open('sub_base64.txt', 'w', encoding='utf-8') as f:
        f.write(base64.b64encode("\n".join(uris).encode()).decode())

if __name__ == "__main__": main()
