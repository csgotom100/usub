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

def parse_server_field(srv_str):
    """
    精准解析各种复杂的 server 字段:
    1. [2001:db8::1]:27921,28000-29000
    2. 1.1.1.1:443
    3. example.com:80
    """
    host, main_port, hop_ports = "", "", ""
    try:
        srv_str = str(srv_str).strip()
        # 识别 IPv6
        if srv_str.startswith('['):
            host = re.search(r'\[(.+?)\]', srv_str).group(1)
            port_part = srv_str.split(']')[-1].lstrip(':')
        else:
            # 找到最后一个冒号分界线
            if ':' in srv_str:
                host, port_part = srv_str.rsplit(':', 1)
            else:
                host = srv_str
                port_part = ""

        # 分离主端口和跳跃端口
        if ',' in port_part:
            main_port = port_part.split(',')[0]
            hop_ports = port_part.split(',', 1)[1]
        else:
            main_port = port_part
            hop_ports = ""
            
        # 纯净数字处理 (防止提取失败)
        main_port = "".join(re.findall(r'\d+', main_port))
    except:
        pass
    return host, main_port, hop_ports

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
        
        # 使用精准解析器获取端口
        srv_raw = obj.get('server') or obj.get('add') or ""
        host, main_port, hop_ports = parse_server_field(srv_raw)
        
        # 如果 server 没带端口，尝试从 port 字段拿
        if not main_port:
            main_port = str(obj.get('port') or obj.get('server_port') or "")

        pw = str(obj.get('auth') or obj.get('password') or obj.get('uuid') or obj.get('id') or "")
        
        # 去重指纹
        unique_key = f"{host}_{main_port}_{pw}".lower()
        if unique_key in seen_keys or not pw or not host:
            continue
        seen_keys.add(unique_key)

        # --- Clash 照搬 ---
        clash_node = obj.copy()
        p_type = str(clash_node.get('type') or ('hysteria2' if 'bandwidth' in obj else 'vless')).lower()
        clash_node['type'] = p_type
        
        geo = get_geo_tag(host + str(obj.get('name','')), host)
        node_name = f"{geo}_{node_count:02d}_{time_tag}"
        clash_node['name'] = node_name
        final_clash_proxies.append(clash_node)

        # --- 订阅生成 ---
        if 'mieru' in p_type: 
            node_count += 1
            continue

        srv_uri = f"[{host}]" if ':' in host else host
        name_enc = urllib.parse.quote(node_name)

        if p_type == 'hysteria2':
            if is_json_source:
                sni = obj.get('sni') or (obj.get('tls',{}) if isinstance(obj.get('tls'),dict) else {}).get('sni') or "apple.com"
                v2_p = {"insecure": "1", "sni": sni}
                if hop_ports: v2_p["mport"] = hop_ports
                final_v2ray_uris.append(f"hysteria2://{pw}@{srv_uri}:{main_port}?{urllib.parse.urlencode(v2_p)}#{name_enc}")
                r_port = f"{main_port},{hop_ports}" if hop_ports else main_port
                final_rocket_uris.append(f"hysteria2://{pw}@{srv_uri}:{r_port}?sni={sni}&insecure=1#{name_enc}")
        else:
            tls_obj = obj.get('tls', {}) if isinstance(obj.get('tls'), dict) else {}
            sni = obj.get('servername') or obj.get('sni') or tls_obj.get('sni') or "itunes.apple.com"
            ro = obj.get('reality-opts') or tls_obj.get('reality') or {}
            pbk = ro.get('public-key') or ro.get('public_key') or ""
            sid = ro.get('short-id') or ro.get('short_id') or ""
            
            v_p = {"encryption": "none", "security": "reality" if pbk else "none", "sni": sni, "fp": "chrome", "type": "tcp"}
            if pbk: v_p.update({"pbk": pbk, "sid": sid})
            uri = f"vless://{pw}@{srv_uri}:{main_port}?{urllib.parse.urlencode(v_p)}#{name_enc}"
            final_v2ray_uris.append(uri)
            final_rocket_uris.append(uri)

        node_count += 1

    # 输出文件
    with open("sub_v2ray.txt", "w", encoding="utf-8") as f: f.write("\n".join(final_v2ray_uris))
    with open("sub_rocket.txt", "w", encoding="utf-8") as f: f.write("\n".join(final_rocket_uris))
    with open("config.yaml", "w", encoding="utf-8") as f:
        yaml.dump({"ipv6": True, "allow-lan": True, "mode": "rule", "proxies": final_clash_proxies, "proxy-groups": [{"name": "🚀 节点选择", "type": "select", "proxies": ["DIRECT"] + [p['name'] for p in final_clash_proxies]}], "rules": ["MATCH,🚀 节点选择"]}, f, allow_unicode=True, sort_keys=False)

if __name__ == "__main__":
    main()
