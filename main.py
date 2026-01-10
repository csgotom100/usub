def get_node_info(item):
    try:
        if not isinstance(item, dict): return None
        
        # 1. 强化提取 Server 和 Port
        raw_server = item.get('server') or item.get('add') or item.get('address')
        if not raw_server or str(raw_server).startswith('127.'): return None
        
        srv = str(raw_server).strip()
        # 初始尝试从字段获取端口
        port = str(item.get('port') or item.get('server_port') or "")

        # --- IPv6 兼容逻辑：从右往左查找最后一个冒号 ---
        if ':' in srv:
            if srv.startswith('['): # 标准 [IPv6]:Port 格式
                srv_part, port_part = srv.split(']:', 1)
                srv = srv_part.replace('[', '')
                port = port_part.split(',')[0] # 丢弃跳跃端口，只取第一个
            elif srv.count(':') > 1: # 裸 IPv6 地址如 2001:bc8:...
                # 这种情况下通常 port 会在独立的字段里，不需要从 srv 里切
                pass 
            else: # 标准 IPv4:Port 格式
                srv_part, port_part = srv.rsplit(':', 1)
                srv = srv_part
                port = port_part.split(',')[0]

        # 清洗端口：只保留数字。如果端口字段是空的，尝试从 server 再次尝试提取
        port = "".join(re.findall(r'\d+', str(port)))
        
        # 致命点修复：如果没有获取到端口，返回 None 触发 walk 继续深度搜索，而不是默认 443
        if not port: return None 

        # 2. 识别协议与密钥
        item_raw = str(item).lower()
        pw = item.get('auth') or item.get('password') or item.get('uuid') or item.get('id')
        
        if 'auth' in item and 'bandwidth' in item or 'hysteria2' in item_raw:
            p = 'hysteria2'
        elif 'tuic' in item_raw:
            p = 'tuic'
        elif 'anytls' in item_raw:
            p = 'anytls'
        else:
            p = 'vless'

        if not pw and p != 'anytls': return None

        # 3. 提取 Reality 核心参数 (PBK/SID)
        tls = item.get('tls', {}) if isinstance(item.get('tls'), dict) else {}
        sni = item.get('servername') or item.get('sni') or tls.get('sni') or tls.get('server_name') or ""
        
        ro = item.get('reality-opts') or tls.get('reality') or item.get('reality_settings') or {}
        pbk = ro.get('public-key') or ro.get('public_key') or item.get('public-key') or ""
        sid = ro.get('short-id') or ro.get('short_id') or item.get('short-id') or ""

        return {
            "server": srv.strip('[]'), "port": port, "type": p, "pw": pw,
            "sni": sni, "pbk": pbk, "sid": sid, "name": item.get('tag') or item.get('name') or ""
        }
    except:
        return None
