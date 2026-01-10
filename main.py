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
            
            def walk(obj):
                if isinstance(obj, dict):
                    if 'server' in obj or 'add' in obj: raw_nodes.append(obj.copy())
                    else:
                        for v in obj.values(): walk(v)
                elif isinstance(obj, list):
                    for i in obj: walk(i)
            walk(data)
        except: continue

    final_clash_proxies, final_v2ray_uris = [], []
    seen_keys = set()
    node_count = 1

    for obj in raw_nodes:
        # 1. 基础信息提取
        srv_raw = str(obj.get('server') or obj.get('add') or "")
        host, main_port = parse_node_address(srv_raw, obj.get('port') or obj.get('server_port') or 443)
        pw = str(obj.get('auth') or obj.get('password') or obj.get('uuid') or obj.get('id') or "")
        if not host or not pw or main_port <= 0: continue

        # 2. 去重
        unique_key = f"{host}_{main_port}_{pw}".lower()
        if unique_key in seen_keys: continue
        seen_keys.add(unique_key)

        # 3. 协议与传输层判定 (重点搜救 AnyTLS 和 xhttp)
        full_text = str(obj).lower()
        p_type = str(obj.get('type', '')).lower()
        if 'anytls' in full_text: p_type = 'anytls'
        elif 'hysteria2' in full_text or 'hy2' in full_text: p_type = 'hysteria2'
        elif not p_type: p_type = 'vless'

        net = str(obj.get('network') or obj.get('net') or "").lower()
        if 'xhttp' in full_text: net = 'xhttp'

        # 4. 参数提取 (TLS/Reality/xhttp)
        tls_map = obj.get('tls', {}) if isinstance(obj.get('tls'), dict) else {}
        sni = obj.get('sni') or obj.get('servername') or tls_map.get('sni') or ""
        
        ro = obj.get('reality-opts') or obj.get('reality_settings') or tls_map.get('reality') or {}
        pbk = ro.get('public-key') or ro.get('public_key') or obj.get('public-key') or ""
        sid = ro.get('short-id') or ro.get('short_id') or obj.get('short-id') or ""

        xh_opts = obj.get('xhttp-opts') or obj.get('xhttpSettings') or {}

        geo = get_geo_tag(host + str(obj.get('name', '')), host)
        node_name = f"{geo}_{node_count:02d}_{time_tag}"

        # --- 重构 Clash 代理对象 (彻底解决 Bool/Map 冲突) ---
        clean_node = {
            "name": node_name, "type": p_type if p_type != 'anytls' else 'vless', # Clash 不认识 anytls, 映射为 vless
            "server": host, "port": main_port, "uuid": pw, "cipher": "auto", "tls": True if (sni or pbk) else False
        }
        if sni: clean_node["sni"] = sni
        if pbk: clean_node["reality-opts"] = {"public-key": pbk, "short-id": sid}
        if net: clean_node["network"] = net
        if net == 'xhttp' and xh_opts: clean_node["xhttp-opts"] = xh_opts
        
        # 特殊：如果原本就是 Hysteria2
        if p_type == 'hysteria2':
            clean_node.update({"type": "hysteria2", "password": pw})
            clean_node.pop("uuid", None); clean_node.pop("cipher", None)

        final_clash_proxies.append(clean_node)

        # --- 生成 v2rayN URI (包含 anytls 和 xhttp 标志) ---
        if p_type == 'mieru': continue
        
        v_p = {"encryption": "none", "fp": "chrome", "type": net or "tcp"}
        if pbk: v_p.update({"security": "reality", "pbk": pbk, "sid": sid, "sni": sni})
        elif sni or p_type == 'anytls': v_p.update({"security": "tls", "sni": sni})
        
        if p_type == 'anytls': v_p['type'] = 'anytls'
        if net == 'xhttp' or xh_opts:
            v_p['type'] = 'xhttp'
            for k in ['path', 'mode']: 
                if xh_opts.get(k): v_p[k] = xh_opts.get(k)

        prefix = "hysteria2" if p_type == "hysteria2" else "vless"
        srv_uri = f"[{host}]" if ':' in host else host
        uri = f"{prefix}://{pw}@{srv_uri}:{main_port}?{urllib.parse.urlencode(v_p)}#{urllib.parse.quote(node_name)}"
        final_v2ray_uris.append(uri)
        node_count += 1

    # --- 保存文件 ---
    with open("sub_v2ray.txt", "w", encoding="utf-8") as f: f.write("\n".join(final_v2ray_uris))
    with open("config.yaml", "w", encoding="utf-8") as f:
        yaml.dump({"proxies": final_clash_proxies, "proxy-groups": [{"name": "🚀 节点选择", "type": "select", "proxies": ["DIRECT"] + [p['name'] for p in final_clash_proxies]}], "rules": ["MATCH,🚀 节点选择"]}, f, allow_unicode=True, sort_keys=False)

if __name__ == "__main__": main()
