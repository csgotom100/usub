def get_node_info(item):
    try:
        if not isinstance(item, dict): return None
        raw_server = item.get('server') or item.get('add') or item.get('address')
        if not raw_server: return None
        
        srv = str(raw_server).strip()
        # 提取端口：优先找独立字段，没有再从 server 字符串里抠
        port_field = str(item.get('port') or item.get('server_port') or "")
        
        # --- 真正的 IPv6/IPv4 提取逻辑 ---
        if srv.startswith('['): # 处理 [2001:db8::1]:12345
            match = re.match(r'\[(.+)\]:(\d+)', srv)
            if match:
                srv, port = match.group(1), match.group(2)
            else:
                srv = srv.strip('[]')
                port = port_field
        elif srv.count(':') > 1: # 裸 IPv6 地址 2001:db8::1
            # 这种情况通常 srv 就是纯 IP，端口在 port_field 里
            port = port_field
        elif ':' in srv: # 标准 IPv4:Port 1.1.1.1:443
            parts = srv.rsplit(':', 1)
            srv, port = parts[0], parts[1]
        else: # 纯域名或 IP
            port = port_field

        # 清洗端口：只留数字
        port = "".join(re.findall(r'\d+', str(port)))
        if not port: return None 

        # 协议判定 (排除 Mieru)
        p_type = str(item.get('type') or "").lower()
        if p_type == 'mieru': return None 
        
        # 剩下的逻辑 (PW, SNI, PBK, SID) 保持不变
        # ...
