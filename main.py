import requests
import os
import re

def is_valid_clash_proxy(block):
    """基础校验，确保节点包含核心三要素"""
    return all(k in block for k in ["type:", "server:", "port:"])

def clean_node_block(block):
    """彻底过滤节点块中的非法关键字"""
    lines = block.splitlines()
    cleaned_lines = []
    # 过滤掉包含这些干扰词的行
    garbage_keywords = ["proxy-groups:", "rules:", "rule-providers:", "name:"]
    
    for line in lines:
        line_stripped = line.strip()
        # 只要行内包含垃圾关键字，或者是空行，就扔掉
        if any(kw in line_stripped for kw in garbage_keywords) or not line_stripped:
            continue
        cleaned_lines.append(line_stripped)
    return cleaned_lines

def main():
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]

    all_raw_chunks = []
    headers = {'User-Agent': 'clash-verge/1.0'}

    print("🚀 正在深度清洗节点...")
    for idx, url in enumerate(urls):
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                # 使用 server: 作为切割点，这是最稳妥的暴力切分法
                raw_blocks = re.split(r'\n\s*-\s*name:', r.text)
                for b in raw_blocks:
                    if is_valid_clash_proxy(b):
                        all_raw_chunks.append(b)
        except: continue

    # 按 Server 地址去重
    unique_dict = {}
    for chunk in all_raw_chunks:
        s_match = re.search(r'server:\s*([^\s]+)', chunk)
        if s_match:
            unique_dict[s_match.group(1)] = chunk
    
    unique_nodes = list(unique_dict.values())
    if not unique_nodes:
        print("❌ 未发现有效节点")
        return

    # 构建配置文件
    clash_config = [
        "port: 7890",
        "allow-lan: true",
        "mode: rule",
        "log-level: info",
        "proxies:"
    ]
    
    node_names = []
    for i, chunk in enumerate(unique_nodes):
        name = f"Node_{i+1:02d}"
        node_names.append(name)
        
        # 写入节点名
        clash_config.append(f"  - name: \"{name}\"")
        # 写入清洗后的属性行
        for attr_line in clean_node_block(chunk):
            clash_config.append(f"    {attr_line}")

    # 策略组
    clash_config.extend([
        "",
        "proxy-groups:",
        "  - name: 🚀 节点选择",
        "    type: select",
        "    proxies:"
    ])
    clash_config.extend([f"      - \"{n}\"" for n in node_names])
    clash_config.extend(["      - DIRECT", "", "rules:", "  - MATCH,🚀 节点选择"])

    with open("config.yaml", "w", encoding="utf-8") as f:
        f.write("\n".join(clash_config))
    
    print(f"🎉 任务完成！已成功清理并生成 {len(node_names)} 个节点。")

if __name__ == "__main__":
    main()
