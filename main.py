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
    v2ray_uris = []
    rocket_uris = []
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
            is_json = content.startswith(('{', '['))
            data = json.loads(content) if is_json else yaml.safe_load(content)
            
            def walk(obj):
                if isinstance(obj, dict):
                    if 'server' in obj:
                        # --- 1. Clash 照搬 (保持物理一致性) ---
                        ckey = f"{obj['server']}_{obj.get('auth') or obj.get('uuid') or obj.get('password')}"
                        if ckey not in seen_clash:
                            raw_node = obj.copy()
                            raw_node['name'] = f"Node_{len(seen_clash)+1}_{time_tag}"
                            if 'type' not in raw_node:
                                raw_node['type'] = 'hysteria2' if 'bandwidth' in obj else 'vless'
                            clash_proxies.append(raw_node)
                            seen_clash.add(ckey)

                        # --- 2. 订阅提取逻辑 ---
                        # 识别协议
                        item_raw = str(obj).lower()
                        p_type = str(obj.get('type', '')).lower()
                        if 'mieru' in p_type or 'mieru' in item_raw: return # 订阅不输出 Mieru

                        # 严格拆解 Server 和 Port
                        srv_raw = str(obj.get('server') or obj.get('add') or "")
                        if not srv_raw: return
                        
                        # 处理 IPv6 格式与端口拆分
                        if srv_raw.startswith('['):
                            host = re.search(r'\[(.+)\]', srv_raw).group(1)
                            port_part = srv_raw.split(']')[-1].strip(':')
                        elif srv_raw.count(':') > 1 and ',' not in srv_raw: # 纯 IPv6 无端口
                            host = srv_raw
                            port_part = str(obj.get('port', ''))
                        elif ':' in srv_raw:
                            host, port_part = srv_raw.rsplit(':', 1)
                        else:
                            host = srv_raw
                            port_part = str(obj.get('port', ''))

                        # 提取主端口和跳跃端口
                        main_port = re.search(r'\d+', port_part).group() if re.search(r'\d+', port_part) else "443"
                        hop_ports = port_part.split(',', 1)[1] if ',' in port_part else ""
                        
                        # 提取共有参数
                        pw = obj.get('auth') or obj.get('password') or obj.get('uuid') or obj.get('id')
                        if not pw: return
                        
                        tls_obj = obj.get('tls', {}) if isinstance(obj.get('tls'), dict) else {}
                        sni = obj.get('servername') or obj.get('sni') or tls_obj.get('sni') or ""
                        
                        geo = get_geo_tag(host + str(obj.get('name','')), host)
                        name_tag = f"{geo}_{len(seen_sub)+1}_{time_tag}"
                        name_enc = urllib.parse.quote(name_tag)
                        srv_uri = f"[{host}]" if ':' in host else host

                        # --- A. HY2 逻辑 (仅限 JSON 源) ---
                        if 'bandwidth' in obj or 'hysteria2' in p_type:
                            if not is_json: return # 遵守你的指令：HY2 只从 JSON 提
                            sni = sni or "apple.com"
                            # v2rayN
                            v2_h = {"insecure": "1", "sni": sni}
                            if hop_ports: v2_h["mport"] = hop_ports
                            v2ray_uris.append(f"hysteria2://{pw}@{srv_uri}:{main_port}?{urllib.parse.urlencode(v2_h)}#{name_enc}")
                            # Shadowrocket
                            r_port = f"{main_port},{hop_ports}" if hop_ports else main_port
                            rocket_uris.append(f"hysteria2://{pw}@{srv_uri}:{r_port}?sni={sni}&insecure=1#{name_enc}")

                        # --- B. VLESS 逻辑 (含 Reality) ---
                        else:
                            ro = obj.get('reality-opts') or tls_obj.get('reality') or obj.get('reality_settings') or {}
                            pbk = ro.get('public-key') or ro.get('public_key') or obj.get('public-key') or ""
                            sid = ro.get('short-id') or ro.get('short_id') or obj.get('short-id') or ""
                            
                            v_params = {"encryption": "none", "security": "reality" if pbk else "none", "sni": sni or "itunes.apple.com", "fp": "chrome", "type": "tcp"}
                            if pbk: v_params.update({"pbk": pbk, "sid": sid})
                            
                            uri = f"vless://{pw}@{srv_uri}:{main_port}?{urllib.parse.urlencode(v_params)}#{name_enc}"
                            v2ray_uris.append(uri)
                            rocket_uris.append(uri)

                        seen_sub.add(ckey)
                    else:
                        for v in obj.values(): walk(v)
                elif isinstance(obj, list):
                    for i in obj: walk(i)
            walk(data)
        except: continue

    # 保存文件
    with open("sub_v2ray.txt", "w", encoding="utf-8") as f: f.write("\n".join(v2ray_uris))
    with open("sub_rocket.txt", "w", encoding="utf-8") as f: f.write("\n".join(rocket_uris))
    with open("config.yaml", "w", encoding="utf-8") as f:
        yaml.dump({"ipv6": True, "allow-lan": True, "proxies": clash_proxies, "proxy-groups": [{"name": "🚀 节点选择", "type": "select", "proxies": ["DIRECT"] + [p['name'] for p in clash_proxies]}], "rules": ["MATCH,🚀 节点选择"]}, f, allow_unicode=True, sort_keys=False)

if __name__ == "__main__":
    main()
