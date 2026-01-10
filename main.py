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

def main():
    raw_nodes = [] # 暂存所有初步识别到的节点
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
                        # 存储原始对象和来源属性
                        raw_nodes.append({"data": obj.copy(), "is_json": source_is_json})
                    else:
                        for v in obj.values(): walk(v, source_is_json)
                elif isinstance(obj, list):
                    for i in obj: walk(i, source_is_json)
            walk(data, is_json)
        except: continue

    # --- 统一去重处理 ---
    final_clash_proxies = []
    final_v2ray_uris = []
    final_rocket_uris = []
    seen_keys = set()
    node_count = 1

    for item in raw_nodes:
        obj = item["data"]
        is_json_source = item["is_json"]
        
        # 提取核心去重指纹：服务器:主端口 (忽略跳跃端口的差异)
        srv_raw = str(obj.get('server') or obj.get('add') or "")
        main_srv = srv_raw.split(',')[0].strip('[]')
        pw = str(obj.get('auth') or obj.get('password') or obj.get('uuid') or obj.get('id') or "")
        
        unique_key = f"{main_srv}_{pw}".lower()
        if unique_key in seen_keys or not pw:
            continue
        seen_keys.add(unique_key)

        # --- A. 准备 Clash 节点 (照搬) ---
        clash_node = obj.copy()
        p_type = str(clash_node.get('type') or ('hysteria2' if 'bandwidth' in obj else 'vless')).lower()
        clash_node['type'] = p_type
        
        geo = get_geo_tag(main_srv + str(obj.get('name','')), main_srv)
        node_name = f"{geo}_{node_count:02d}_{time_tag}"
        clash_node['name'] = node_name
        final_clash_proxies.append(clash_node)

        # --- B. 准备 订阅 URI ---
        if 'mieru' in p_type: 
            node_count += 1
            continue

        # 解析端口
        if ':' in main_srv and not main_srv.startswith('['): # 处理 IPV4 连带端口的情况
            host, main_port = main_srv.rsplit(':', 1)
        else:
            host = main_srv
            main_port = re.search(r'\d+', srv_raw.split(':')[-1]).group() if ':' in srv_raw else "443"
        
        hop_ports = srv_raw.split(',', 1)[1] if ',' in srv_raw else ""
        srv_uri = f"[{host}]" if ':' in host else host
        name_enc = urllib.parse.quote(node_name)

        # HY2 订阅逻辑
        if p_type == 'hysteria2':
            if is_json_source: # 仅当源是 JSON 时才进订阅
                sni = obj.get('sni') or (obj.get('tls',{}) if isinstance(obj.get('tls'),dict) else {}).get('sni') or "apple.com"
                # v2rayN
                v2_params = {"insecure": "1", "sni": sni}
                if hop_ports: v2_params["mport"] = hop_ports
                final_v2ray_uris.append(f"hysteria2://{pw}@{srv_uri}:{main_port}?{urllib.parse.urlencode(v2_params)}#{name_enc}")
                # Rocket
                r_port = f"{main_port},{hop_ports}" if hop_ports else main_port
                final_rocket_uris.append(f"hysteria2://{pw}@{srv_uri}:{r_port}?sni={sni}&insecure=1#{name_enc}")
        
        # VLESS 订阅逻辑
        else:
            tls_obj = obj.get('tls', {}) if isinstance(obj.get('tls'), dict) else {}
            sni = obj.get('servername') or obj.get('sni') or tls_obj.get('sni') or "itunes.apple.com"
            ro = obj.get('reality-opts') or tls_obj.get('reality') or {}
            pbk = ro.get('public-key') or ro.get('public_key') or ""
            sid = ro.get('short-id') or ro.get('short_id') or ""
            
            v_params = {"encryption": "none", "security": "reality" if pbk else "none", "sni": sni, "fp": "chrome", "type": "tcp"}
            if pbk: v_params.update({"pbk": pbk, "sid": sid})
            uri = f"vless://{pw}@{srv_uri}:{main_port}?{urllib.parse.urlencode(v_params)}#{name_enc}"
            final_v2ray_uris.append(uri)
            final_rocket_uris.append(uri)

        node_count += 1

    # 保存文件
    with open("sub_v2ray.txt", "w", encoding="utf-8") as f: f.write("\n".join(final_v2ray_uris))
    with open("sub_rocket.txt", "w", encoding="utf-8") as f: f.write("\n".join(final_rocket_uris))
    with open("config.yaml", "w", encoding="utf-8") as f:
        yaml.dump({
            "ipv6": True, "allow-lan": True, "mode": "rule",
            "proxies": final_clash_proxies,
            "proxy-groups": [{"name": "🚀 节点选择", "type": "select", "proxies": ["DIRECT"] + [p['name'] for p in final_clash_proxies]}],
            "rules": ["MATCH,🚀 节点选择"]
        }, f, allow_unicode=True, sort_keys=False)

if __name__ == "__main__":
    main()
