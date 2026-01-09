def generate_uri(p):
    try:
        t = str(p.get('type') or p.get('protocol')).lower()
        addr = p.get('server')
        # --- 核心修复：确保端口是纯数字 ---
        raw_port = str(p.get('port'))
        if 'None' in raw_port or not raw_port: 
            return None # 丢弃无效端口节点
        # 如果是 27921,28000 这种格式，只取第一个
        port = re.findall(r'\d+', raw_port)[0] 
        
        name = quote(p.get('name', ''))
        
        if t == 'vless':
            ro, xh = p.get('reality-opts', {}), p.get('xhttp-opts', {})
            # 确保关键参数 pbk/sid 存在才生成 Reality
            params = {
                "security": "reality",
                "sni": p.get('servername') or p.get('sni'),
                "pbk": ro.get('public-key'),
                "sid": ro.get('short-id'),
                "type": p.get('network') or "tcp",
                "flow": p.get('flow')
            }
            if p.get('network') == 'xhttp':
                params["path"] = xh.get('path')
                params["mode"] = xh.get('mode', 'auto')
            
            # 检查是否有必填项，防止生成 :None 这种链接
            if not params["pbk"]: params["security"] = "none"
            
            query = urlencode({k: v for k, v in params.items() if v})
            return f"vless://{p.get('uuid')}@{addr}:{port}?{query}#{name}"
        
        elif t in ['hysteria2', 'hy2']:
            pw = p.get('password') or p.get('auth')
            return f"hysteria2://{pw}@{addr}:{port}?insecure=1&sni={p.get('sni', 'apple.com')}#{name}"
        
        elif t == 'anytls':
            pw = p.get('password') or p.get('auth')
            return f"anytls://{pw}@{addr}:{port}?alpn=h3&insecure=1#{name}"
            
        elif t == 'tuic':
            # TUIC 依然保留在 sub.txt 供支持的软件使用，v2rayN 请用 config.yaml
            val = p.get('uuid') or p.get('password')
            return f"tuic://{val}@{addr}:{port}?sni={p.get('sni','')}&alpn=h3#{name}"
            
    except: return None
