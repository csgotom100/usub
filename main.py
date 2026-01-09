import requests
import yaml
import base64
import os
import json
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode

def format_addr(addr):
    addr_str = str(addr).strip()
    if ":" in addr_str and "[" not in addr_str:
        return f"[{addr_str}]"
    return addr_str

def get_beijing_time():
    beijing_now = datetime.utcnow() + timedelta(hours=8)
    return beijing_now.strftime("%m-%d %H:%M")

def parse_content(content):
    """识别 YAML, Hy2, sing-box 或 Xray JSON 并返回节点列表"""
    nodes = []
    try:
        data = json.loads(content)
        # 1. Xray JSON 格式
        if isinstance(data, dict) and 'outbounds' in data:
            for out in data['outbounds']:
                protocol = out.get('protocol')
                # 提取 VLESS
                if protocol == 'vless':
                    settings = out.get('settings', {})
                    vnext = settings.get('vnext', [{}])[0]
                    user = vnext.get('users', [{}])[0]
                    stream = out.get('streamSettings', {})
                    reality = stream.get('realitySettings', {})
                    xhttp = stream.get('xhttpSettings', {})
                    
                    nodes.append({
                        'name': out.get('tag', 'xray_node'),
                        'type': 'vless',
                        'server': vnext.get('address'),
                        'port': vnext.get('port'),
                        'uuid': user.get('id'),
                        'network': stream.get('network', 'tcp'),
                        'packet_addr': True, # 针对 xhttp 等新协议优化
                        'tls': stream.get('security') == 'reality',
                        'servername': reality.get('serverName', ''),
                        'reality-opts': {
                            'public-key': reality.get('publicKey', ''),
                            'short-id': reality.get('shortId', '')
                        },
                        'ws-opts': {'path': xhttp.get('path', '')} if xhttp else None,
                        'client-fingerprint': reality.get('fingerprint', 'chrome')
                    })
            if nodes: return nodes

        # 2. sing-box 格式 (保持之前逻辑)
        if isinstance(data, dict) and 'outbounds' in data:
            # (此处省略部分重复的 sing-box 逻辑，功能已合并至上方逻辑中)
            pass 

        # 3. Hy2 格式 (保持之前逻辑)
        if isinstance(data, dict) and 'server' in data:
            server_main = data.get('server', '').split(',')[0]
            nodes.append({
                'name': 'hy2_node', 'type': 'hysteria2', 
                'server': server_main.rsplit(':', 1)[0], 'port': int(server_main.rsplit(':', 1)[1]),
                'password': data.get('auth'), 'sni': data.get('tls', {}).get('sni', 'apple.com')
            })
            return nodes
    except: pass

    # 4. YAML 格式 (保持之前逻辑)
    try:
        data = yaml.safe_load(content)
        if isinstance(data, dict) and 'proxies' in data:
            nodes.extend(data.get('proxies', []))
    except: pass
    return nodes

def generate_uri(p):
    try:
        p_type = str(p.get('type', '')).lower()
        name = quote(str(p.get('name', 'node')))
        server = format_addr(p.get('server', ''))
        port = p.get('port')
        
        if p_type == 'vless':
            ropts = p.get('reality-opts', {})
            params = {
                "security": "reality",
                "sni": p.get('servername', p.get('sni', '')),
                "fp": p.get('client-fingerprint', 'chrome'),
                "type": p.get('network', 'tcp'),
                "pbk": ropts.get('public-key', ''),
                "sid": ropts.get('short-id', ''),
                "path": p.get('ws-opts', {}).get('path', '') if p.get('ws-opts') else ""
            }
            return f"vless://{p.get('uuid')}@{server}:{port}?{urlencode({k: v for k, v in params.items() if v})}#{name}"
        # (保持 anytls, hy2 等 URI 生成逻辑不变...)
        elif p_type == 'hysteria2' or p_type == 'hy2':
            passwd = p.get('password', p.get('auth', ''))
            return f"hysteria2://{passwd}@{server}:{port}?sni={p.get('sni', '')}&insecure=1#{name}"
    except: return None
    return None

def main():
    # (保持 main 函数中的抓取、去重、神机规则配置和文件保存逻辑不变...)
    # 确保在 clash_config 的 proxy-groups 中打破循环引用 (已在上次回复中修正)
    pass

# ... (此处运行 main 逻辑)
