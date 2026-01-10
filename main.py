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
    # 增强版解析：处理 [ipv6]:port 和包含端口偏移的字符串
    try:
        srv_str = str(srv_str).strip()
        # 处理 IPv6 [2a14...]:50022
        if srv_str.startswith('['):
            m = re.search(r'\[(.+?)\](?::(\d+))?', srv_str)
            if m:
                host, port = m.group(1), m.group(2)
                return host, int(port) if port else int(fallback_port)
        # 处理常见 host:port
        if ':' in srv_str and ',' not in srv_str:
            parts = srv_str.rsplit(':', 1)
            return parts[0], int(parts[1])
        # 处理带逗号的 (hy2 mport)
        host_part = srv_str.split(',')[0].split(':')[0]
        return host_part, int(fallback_port)
    except:
        return str(srv_str).split(':')[0], 443

def main():
    raw_nodes = []
    time_tag = get_beijing_time()
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]

    for url in urls:
        try:
            r = requests.get(url, timeout=15, verify=False)
            data = yaml.safe_load(r.text) if not r.text.strip().startswith('{') else r.json()
            def walk(obj):
                if isinstance(obj, dict):
                    if 'server' in obj or 'add' in obj: raw_nodes.append(obj)
                    else: [walk(v) for v in obj.values()]
                elif isinstance(obj, list): [walk(i) for i in obj]
            walk(data)
        except: continue

    final_clash, final_v2ray = [], []
    seen = set()
    count = 1

    for obj in raw_nodes:
        # 提取核心参数
        srv = obj.get('server') or obj.get('add') or ""
        port = obj.get('port') or obj.get('server_port') or 443
        host, actual_port = parse_node_address(srv, port)
        pw = obj.get('uuid') or obj.get('password') or obj.get('auth') or obj.get('id') or ""
        
        if not host or not pw or actual_port <= 0: continue
        if f"{host}{actual_port}{pw}" in seen: continue
        seen.add(f"{host}{actual_port}{pw}")

        # 协议深度识别
        full_str = str(obj).lower()
        is_hy2 = 'hysteria2' in full_str or 'hy2' in full_str
        is_anytls = 'anytls' in full_str
        is_xhttp = 'xhttp' in full_str
        
        # 参数清洗
        sni = obj.get('sni') or obj.get('servername') or ""
        if isinstance(obj.get('tls'), dict):
            sni = sni or obj['tls'].get('sni') or obj['tls'].get('servername') or ""
        
        pbk = obj.get('public-key') or ""
        sid = obj.get('short-id') or ""
        if 'reality' in full_str:
            # 尝试从各种嵌套里捞 Reality 参数
            for k, v in obj.items():
                if isinstance(v, dict):
                    pbk = pbk or v.get('public-key') or v.get('public_key')
                    sid = sid or v.get('short-id') or v.get('short_id')

        node_name = f"{get_geo_tag(host, host)}_{count:02d}_{time_tag}"

        # --- Clash 配置：强制扁平化 ---
        c_node = {
            "name": node_name,
            "server": host,
            "port": actual_port,
            "type": "hysteria2" if is_hy2 else "vless",
            "tls": True if (sni or pbk or is_anytls) else False,
            "skip-cert-verify": True
        }
        if is_hy2: c_node["password"] = pw
        else:
            c_node.update({"uuid": pw, "cipher": "auto", "network": "tcp"})
            if pbk: c_node["reality-opts"] = {"public-key": pbk, "short-id": sid}
            if is_xhttp: 
                c_node["network"] = "xhttp"
                # 尽量保留 xhttp 路径
                xh_path = obj.get('path') or "/default"
                c_node["xhttp-opts"] = {"path": xh_path}

        if sni: c_node["sni"] = sni
        final_clash.append(c_node)

        # --- v2rayN URI ---
        v_p = {"security": "tls" if c_node["tls"] else "none", "sni": sni, "type": "tcp"}
        if pbk: v_p.update({"security": "reality", "pbk": pbk, "sid": sid})
        if is_anytls: v_p["type"] = "anytls"
        if is_xhttp: v_p.update({"type": "xhttp", "path": obj.get('path', '/')})

        prefix = "hysteria2" if is_hy2 else "vless"
        uri_host = f"[{host}]" if ':' in host else host
        final_v2ray.append(f"{prefix}://{pw}@{uri_host}:{actual_port}?{urllib.parse.urlencode(v_p)}#{urllib.parse.quote(node_name)}")
        count += 1

    # 保存
    with open("sub_v2ray.txt", "w", encoding="utf-8") as f: f.write("\n".join(final_v2ray))
    with open("config.yaml", "w", encoding="utf-8") as f:
        yaml.dump({"proxies": final_clash, "proxy-groups": [{"name": "节点选择", "type": "select", "proxies": ["DIRECT"]+[p['name'] for p in final_clash]}], "rules": ["MATCH,节点选择"]}, f, allow_unicode=True)

if __name__ == "__main__": main()
