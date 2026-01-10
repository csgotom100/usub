import requests
import os
import re

def clean_node_block(block):
    """清洗节点块：只保留 key: value 格式的有效行"""
    cleaned_lines = []
    # 定义需要剔除的干扰特征
    garbage_patterns = [
        r'^http',          # 纯网址行
        r'dongtaiwang',    # 来源标记行
        r'proxy-groups',   # 残留的分组头
        r'name:',          # 旧的名字行
    ]
    
    for line in block.splitlines():
        line_stripped = line.strip()
        # 1. 必须包含冒号 (key: value 结构)
        if ':' not in line_stripped:
            continue
        # 2. 不能匹配垃圾模式
        if any(re.search(p, line_stripped, re.I) for p in garbage_patterns):
            continue
        cleaned_lines.append(line_stripped)
    return cleaned_lines

def main():
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]

    all_raw_chunks = []
    headers = {'User-Agent': 'clash-verge/1.0'}

    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                # 暴力切割：按 - name: 切分
                chunks = re.split(r'-\s*name:', r.text)
                for c in chunks:
                    if "server:" in c and "port:" in c:
                        all_raw_chunks.append(c)
        except: continue

    # 按 Server 去重
    unique_dict = {}
    for chunk in all_raw_chunks:
        s_match = re.search(r'server:\s*([^\s]+)', chunk)
        if s_match: unique_dict[s_match.group(1)] = chunk
    
    unique_nodes = list(unique_dict.values())
    
    # 构建最终 YAML
    clash_config = [
        "port: 7890",
        "allow-lan: true",
        "mode: rule",
        "proxies:"
    ]
    
    node_names = []
    for i, chunk in enumerate(unique_nodes):
        name = f"Node_{i+1:02d}"
        node_names.append(name)
        clash_config.append(f"  - name: \"{name}\"")
        # 核心：只压入清洗后的干净行
        for attr in clean_node_block(chunk):
            clash_config.append(f"    {attr}")

    # 策略组
    clash_config.extend(["", "proxy-groups:", "  - name: 🚀 节点选择", "    type: select", "    proxies:"])
    clash_config.extend([f"      - \"{n}\"" for n in node_names])
    clash_config.extend(["      - DIRECT", "", "rules:", "  - MATCH,🚀 节点选择"])

    with open("config.yaml", "w", encoding="utf-8") as f:
        f.write("\n".join(clash_config))
    print(f"🎉 成功！已清理并提取 {len(node_names)} 个纯净节点。")

if __name__ == "__main__":
    main()
