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
    """获取北京时间戳字符串"""
    # GitHub Actions 运行在 UTC 时间，需要 +8 小时偏移
    beijing_now = datetime.utcnow() + timedelta(hours=8)
    return beijing_now.strftime("%m-%d %H:%M")

def parse_clash_yaml(yaml_content):
    try:
        data = yaml.safe_load(yaml_content)
        if isinstance(data, dict) and 'proxies' in data:
            return data.get('proxies', [])
    except:
        pass
    return []

def generate_uri(p):
    """转换为 v2rayN 兼容 URI"""
    try:
        p_type = str(p.get('type', '')).lower()
        name = quote(str(p.get('name', 'node')))
        server = format_addr(p.get('server', ''))
        port = p.get('port')
        
        if p_type == 'vless':
            reality = p.get('reality-opts', {})
            params = {
                "security": "reality",
                "sni": p.get('servername') or p.get('sni', ''),
                "fp": "chrome",
                "type": p.get('network', 'tcp'),
                "pbk": reality.get('public-key', ''),
                "sid": reality.get('short-id', ''),
            }
            return f"vless://{p.get('uuid')}@{server}:{port}?{urlencode({k: v for k, v in params.items() if v})}#{name}"
        
        elif p_type == 'anytls':
            params = {"alpn": ",".join(p.get('alpn', [])), "insecure": "1"}
            return f"anytls://{p.get('password')}@{server}:{port}?{urlencode(params)}#{name}"
            
        elif p_type == 'hysteria2' or p_type == 'hy2':
            return f"hysteria2://{p.get('password', p.get('auth', ''))}@{server}:{port}?sni={p.get('sni', '')}&insecure=1#{name}"
        
        elif p_type == 'tuic':
            return f"tuic://{p.get('uuid')}:{p.get('password')}@{server}:{port}?sni={p.get('sni', '')}&insecure=1&alpn=h3#{name}"
        
        elif p_type == 'mieru':
            return f"mieru://{p.get('username')}:{p.get('password')}@{server}:{port}?transport=tcp#{name}"
    except:
        return None
    return None

def main():
    all_proxies = []
    if not os.path.exists('sources.txt'): return

    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip() and line.startswith("http")]

    for url in urls:
        try:
            print(f"正在抓取: {url}")
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                # 这里默认所有 sources.txt 里的链接都尝试作为 YAML 解析
                # 如果未来有 JSON 源，可以根据内容特征在这里分流处理
                all_proxies.extend(parse_clash_yaml(resp.text))
        except: 
            continue

    # --- 深度去重逻辑 (全配置匹配) ---
    unique_nodes = []
    seen_configs = set()
    
    for p in all_proxies:
        temp_p = p.copy()
        # 排除掉名称，仅对比核心连接配置
        temp_p.pop('name', None)
        # 转换为 JSON 字符串作为指纹进行比对
        config_fingerprint = json.dumps(temp_p, sort_keys=True)
        
        if config_fingerprint not in seen_configs:
            seen_configs.add(config_fingerprint)
            unique_nodes.append(p)

    # --- 重新命名并加上北京时间戳 ---
    final_proxies = []
    protocol_counts = {}
    time_tag = get_beijing_time()
    
    for p in unique_nodes:
        p_type = str(p.get('type', 'unknown')).upper()
        count = protocol_counts.get(p_type, 0) + 1
        protocol_counts[p_type] = count
        
        # 格式: [协议名] 编号 (月-日 时:分)
        p['name'] = f"[{p_type}] {count:02d} ({time_tag})"
        final_proxies.append(p)

    # 1. 保存 config.yaml (Clash 格式)
    with open('config.yaml', 'w', encoding='utf-8') as f:
        yaml.dump({"port": 7890, "allow-lan": True, "mode": "rule", "proxies": final_proxies}, f, allow_unicode=True, sort_keys=False)

    # 2. 生成 URI 并保存 sub.txt (明文格式)
    uris = [generate_uri(p) for p in final_proxies if generate_uri(p)]
    with open('sub.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(uris))

    # 3. 保存 sub_base64.txt (标准订阅格式)
    sub_base64 = base64.b64encode("\n".join(uris).encode('utf-8')).decode('utf-8')
    with open('sub_base64.txt', 'w', encoding='utf-8') as f:
        f.write(sub_base64)
    
    print(f"完成！去重后共有 {len(final_proxies)} 个节点。")

if __name__ == "__main__":
    main()
