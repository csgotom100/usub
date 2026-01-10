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
    """
    最强解析逻辑：精准分离 Host 和 Port，支持 IPv6 和多端口
    """
    host, port = "", 0
    try:
        srv_str = str(srv_str).strip()
        # 处理 [IPv6]:Port 格式
        if srv_str.startswith('['):
            match = re.search(r'\[(.+?)\]:?(\d+)?', srv_str)
            if match:
                host = match.group(1)
                port_str = match.group(2)
                port = int(port_str) if port_str else 0
        # 处理 IPv4:Port 格式
        elif ':' in srv_str:
            parts = srv_str.rsplit(':', 1)
            host = parts[0]
            # 过滤掉逗号后的跳跃端口部分再取数字
            port_str = "".join(re.findall(r'\d+', parts[1].split(',')[0]))
            port = int(port_str) if port_str else 0
        else:
            host = srv_str

        # 如果通过 server 字符串没拿到有效端口，回退到原始字段
        if port <= 0:
            port_val = str(fallback_port)
            port_str = "".join(re.findall(r'\d+', port_val))
            port = int(port_str) if port_str else 443
    except:
        port = 443
    
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
                    if 'server' in obj:
                        raw_nodes.append({"data": obj.copy(), "is_json": source_is_json})
                    else:
                        for v in obj.values(): walk(v, source_is_json)
                elif isinstance(obj, list):
                    for i in obj: walk(i, source_is_json)
            walk(data, is_json)
        except: continue

    final_clash_proxies = []
    final_v2ray_uris = []
    final_rocket_uris = []
    seen_keys = set()
    node_count = 1

    for item in raw_nodes:
        obj = item["data"]
        is_json_source = item["is_json"]
        
        # 1. 提取基础信息
        srv_raw = str(obj.get('server') or obj.get('add') or "")
        fallback_port = obj.get('port') or obj.get('server_port') or 443
        host, main_port = parse_node_address(srv_raw, fallback_port)
        
        # 2. 校验端口合法性：如果端口依然非法，跳过该节点防止 Clash 崩溃
        if main_port <= 0 or main_port > 65535:
            continue

        pw = str(obj.get('auth') or obj.get('password') or obj.get('uuid') or obj.get('id') or "")
        
        # 3. 去重
        unique_key = f"{host}_{main_port}_{pw}".lower()
        if unique_key in seen_keys or not host or not pw: continue
        seen_keys.add(unique_key)

        # --- Clash 配置处理 (完全照搬，仅修正端口字段) ---
        clash_node = obj.copy()
        p_type = str(clash_node.get('type') or ('hysteria2' if 'bandwidth' in obj else 'vless')).lower()
        clash_node['type'] = p_type
        clash_node['port'] = main_port # 强制覆盖为解析出的正整数端口
        
        geo = get_geo_tag(host, host)
        node_name = f"{geo}_{node_count:02d}_{time_tag}"
        clash_node['name'] = node_name
        final_clash_proxies.append(clash_node)

        # --- 订阅生成 (跳过 mieru) ---
        if 'mieru' in p_type:
            node_count += 1
            continue

        srv_uri = f"[{host}]" if ':' in host else host
        name_enc = urllib.parse.quote(node_name)
        hop_ports = srv_raw.split(',', 1)[1] if ',' in srv_raw else ""

        if p_type == 'hysteria2' and is_json_source:
            sni = obj.get('sni') or (obj.get('tls',{}) if isinstance(obj.get('tls'),dict) else {}).get('sni') or "apple.com"
            v2_p = {"insecure": "1", "sni": sni}
            if hop_ports: v2_p["mport"] = hop_ports
            final_v2ray_uris.append(f"hysteria2://{pw}@{srv_uri}:{main_port}?{urllib.parse.urlencode(v2_p)}#{name_enc}")
            r_port = f"{main_port},{hop_ports}" if hop_ports else main_port
            final_rocket_uris.append(f"hysteria2://{pw}@{srv_uri}:{r_port}?sni={sni}&insecure=1#{name_enc}")
        
        elif 'vless' in p_type:
            tls_obj = obj.get('tls', {}) if isinstance(obj.get('tls'), dict) else {}
            sni = obj.get('servername') or obj.get('sni') or tls_obj.get('sni') or "itunes.apple.com"
            ro = obj.get('reality-opts') or tls_obj.get('reality') or {}
            v_p = {"encryption": "none", "security": "reality" if ro.get('public-key') else "none", "sni": sni, "fp": "chrome", "type": "tcp"}
            if ro.get('public-key'): v_p.update({"pbk": ro.get('public-key'), "sid": ro.get('short-id')})
            uri = f"vless://{pw}@{srv_uri}:{main_port}?{urllib.parse.urlencode(v_p)}#{name_enc}"
            final_v2ray_uris.append(uri); final_rocket_uris.append(uri)

        node_count += 1

    # --- 保存文件 ---
    with open("sub_v2ray.txt", "w", encoding="utf-8") as f: f.write("\n".join(final_v2ray_uris))
    with open("sub_rocket.txt", "w", encoding="utf-8") as f: f.write("\n".join(final_rocket_uris))
    with open("config.yaml", "w", encoding="utf-8") as f:
        yaml.dump({
            "ipv6": True, "allow-lan": True, "mode": "rule",
            "proxies": final_clash_proxies,
            "proxy-groups": [{"name": "🚀 节点选择", "type": "select", "proxies": ["♻️ 自动选择", "DIRECT"] + [p['name'] for p in final_clash_proxies]},
                             {"name": "♻️ 自动选择", "type": "url-test", "url": "http://www.gstatic.com/generate_204", "interval": 300, "proxies": [p['name'] for p in final_clash_proxies]}],
            "rules": ["MATCH,🚀 节点选择"]
        }, f, allow_unicode=True, sort_keys=False)

if __name__ == "__main__":
    main()
