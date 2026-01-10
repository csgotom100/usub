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

def parse_node_address(srv_str, fallback_port):
    host, port = "", 0
    try:
        srv_str = str(srv_str).strip()
        if srv_str.startswith('['):
            match = re.search(r'\[(.+?)\]:?(\d+)?', srv_str)
            if match:
                host, port_str = match.group(1), match.group(2)
                port = int(port_str) if port_str else 0
        elif ':' in srv_str:
            parts = srv_str.rsplit(':', 1)
            host = parts[0]
            port_str = "".join(re.findall(r'\d+', parts[1].split(',')[0]))
            port = int(port_str) if port_str else 0
        else: host = srv_str
        if port <= 0:
            port_str = "".join(re.findall(r'\d+', str(fallback_port)))
            port = int(port_str) if port_str else 443
    except: port = 443
    return host, port

def main():
    raw_nodes = []
    time_tag = get_beijing_time()
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]

    for url in urls:
        try:
            r = requests.get(url, timeout=15, verify=False)
            content = r.text.strip()
            is_json = content.startswith(('{', '['))
            data = json.loads(content) if is_json else yaml.safe_load(content)
            
            def walk(obj, source_is_json):
                if isinstance(obj, dict):
                    if 'server' in obj: raw_nodes.append({"data": obj.copy(), "is_json": source_is_json})
                    else:
                        for v in obj.values(): walk(v, source_is_json)
                elif isinstance(obj, list):
                    for i in obj: walk(i, source_is_json)
            walk(data, is_json)
        except: continue

    final_clash_proxies, final_v2ray_uris, final_rocket_uris = [], [], []
    seen_keys = set()
    node_count = 1

    for item in raw_nodes:
        obj, is_json_source = item["data"], item["is_json"]
        srv_raw = str(obj.get('server') or obj.get('add') or "")
        host, main_port = parse_node_address(srv_raw, obj.get('port') or obj.get('server_port') or 443)
        pw = str(obj.get('auth') or obj.get('password') or obj.get('uuid') or obj.get('id') or "")
        
        if not host or not pw: continue
        unique_key = f"{host}_{main_port}_{pw}".lower()
        if unique_key in seen_keys: continue
        seen_keys.add(unique_key)

        # 协议探测
        p_type = str(obj.get('type', '')).lower() or ('hysteria2' if 'bandwidth' in obj else 'vless')
        
        # 传输层与 TLS 探测
        stream_settings = obj.get('stream-settings') or obj.get('streamSettings') or {}
        net = str(obj.get('network') or stream_settings.get('network') or "").lower()
        
        tls_data = obj.get('tls', {}) if isinstance(obj.get('tls'), dict) else {}
        sni = obj.get('sni') or obj.get('servername') or (tls_data.get('sni') if isinstance(tls_data, dict) else "")
        
        # Reality 处理
        ro = obj.get('reality-opts') or tls_data.get('reality') or obj.get('reality_settings') or {}
        pbk = ro.get('public-key') or ro.get('public_key') or obj.get('public-key') or ""
        sid = ro.get('short-id') or ro.get('short_id') or obj.get('short-id') or ""

        geo = get_geo_tag(host + str(obj.get('name', '')), host)
        node_name = f"{geo}_{node_count:02d}_{time_tag}"

        # --- Clash 配置：保持原始结构 ---
        clash_node = obj.copy()
        clash_node.update({"name": node_name, "port": main_port, "server": host})
        # 仅修复已知的 Clash bool/map 冲突
        if isinstance(clash_node.get('tls'), dict):
            clash_node['tls'] = True
            if sni: clash_node['sni'] = sni
        final_clash_proxies.append(clash_node)

        # --- 订阅生成 (剔除 mieru) ---
        if 'mieru' in p_type:
            node_count += 1
            continue

        srv_uri = f"[{host}]" if ':' in host else host
        name_enc = urllib.parse.quote(node_name)

        if p_type == 'hysteria2':
            v2_p = {"insecure": "1", "sni": sni or "apple.com"}
            hop_ports = srv_raw.split(',', 1)[1] if ',' in srv_raw else ""
            if hop_ports: v2_p["mport"] = hop_ports
            final_v2ray_uris.append(f"hysteria2://{pw}@{srv_uri}:{main_port}?{urllib.parse.urlencode(v2_p)}#{name_enc}")
            final_rocket_uris.append(f"hysteria2://{pw}@{srv_uri}:{main_port}?sni={v2_p['sni']}&insecure=1#{name_enc}")
        
        else: # 处理 VLESS 家族 (含 xhttp, anytls)
            v_p = {"encryption": "none", "fp": "chrome", "type": net or "tcp"}
            
            # 安全性判定
            if pbk: v_p.update({"security": "reality", "pbk": pbk, "sid": sid, "sni": sni})
            elif sni: v_p.update({"security": "tls", "sni": sni})
            else: v_p["security"] = "none"

            # xhttp 专项补全
            xh_opts = obj.get('xhttp-opts') or stream_settings.get('xhttpSettings') or obj.get('transport', {}).get('xhttp', {})
            if xh_opts:
                v_p['type'] = 'xhttp'
                for k in ['path', 'mode', 'host']:
                    if xh_opts.get(k): v_p[k] = xh_opts.get(k)
            
            # AnyTLS 专项补全 (如果发现是 anytls，保持 type 并尝试提取 path)
            if 'anytls' in str(obj).lower() or p_type == 'anytls':
                v_p['type'] = 'anytls'

            uri = f"vless://{pw}@{srv_uri}:{main_port}?{urllib.parse.urlencode(v_p)}#{name_enc}"
            final_v2ray_uris.append(uri)
            final_rocket_uris.append(uri)

        node_count += 1

    # --- 输出 ---
    with open("sub_v2ray.txt", "w", encoding="utf-8") as f: f.write("\n".join(final_v2ray_uris))
    with open("sub_rocket.txt", "w", encoding="utf-8") as f: f.write("\n".join(final_rocket_uris))
    with open("config.yaml", "w", encoding="utf-8") as f:
        yaml.dump({"ipv6": True, "allow-lan": True, "proxies": final_clash_proxies, "proxy-groups": [{"name": "🚀 节点选择", "type": "select", "proxies": ["DIRECT"] + [p['name'] for p in final_clash_proxies]}], "rules": ["MATCH,🚀 节点选择"]}, f, allow_unicode=True, sort_keys=False)

if __name__ == "__main__": main()
