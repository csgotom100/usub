import requests
import os
import re

def extract_real_nodes(text):
    real_nodes = []
    # 更加强力的 Clash 节点块匹配
    pattern = r'(?:^|\n)-\s*name:[\s\S]+?(?=\n(?:-?\s*name:|[a-z\-]+:)|$)'
    matches = re.findall(pattern, text)
    
    for m in matches:
        content = m.strip()
        if "server:" in content and "type:" in content:
            real_nodes.append(content)
            
    # 兼容链接格式
    links = re.findall(r'(?:vmess|ss|trojan|vless|ssr|hy2)://[^\s]+', text)
    real_nodes.extend(links)
    return real_nodes

def main():
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]

    all_nodes = []
    headers = {'User-Agent': 'clash-verge/1.0'}

    print(f"🚀 正在提取节点并解决同名冲突...")
    for idx, url in enumerate(urls):
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                nodes = extract_real_nodes(r.text)
                all_nodes.extend(nodes)
        except: continue

    unique_nodes = list(set(all_nodes))
    if not unique_nodes:
        print("❌ 未抓取到有效节点")
        return

    print(f"--- 📊 汇总完成: 共获取 {len(unique_nodes)} 个原始块 ---")

    clash_template = [
        "port: 7890",
        "socks-port: 7891",
        "allow-lan: true",
        "mode: rule",
        "log-level: info",
        "proxies:"
    ]
    
    node_names = []
    
    # 遍历节点并强制重命名
    for i, node in enumerate(unique_nodes):
        # 1. 提取节点的类型 (vmess/vless/hysteria等)
        type_match = re.search(r'type:\s*(\w+)', node)
        node_type = type_match.group(1) if type_match else "proxy"
        
        # 2. 赋予唯一名称，防止覆盖
        new_name = f"{node_type}_{i+1:02d}"
        node_names.append(new_name)
        
        # 3. 清理并重组节点内容
        # 移除原有的 name 行，换成我们生成的唯一 name
        clean_lines = []
        lines = node.splitlines()
        
        # 跳过原始的 name 行，其他的保留
        for line in lines:
            line_stripped = line.strip()
            if line_stripped.startswith("- name:") or line_stripped.startswith("name:"):
                continue
            if line_stripped:
                clean_lines.append(line_stripped)
        
        # 按照 Clash 缩进格式添加
        clash_template.append(f"  - name: \"{new_name}\"")
        for clean_line in clean_lines:
            clash_template.append(f"    {clean_line}")

    # 4. 生成策略组
    if node_names:
        clash_template.extend([
            "",
            "proxy-groups:",
            "  - name: 🚀 节点选择",
            "    type: select",
            "    proxies:"
        ])
        for name in node_names:
            clash_template.append(f"      - \"{name}\"")
        clash_template.append("      - DIRECT")

    # 5. 生成规则
    clash_template.extend([
        "",
        "rules:",
        "  - GEOIP,CN,DIRECT",
        "  - MATCH,🚀 节点选择"
    ])

    with open("config.yaml", "w", encoding="utf-8") as f:
        f.write("\n".join(clash_template))
    
    print(f"🎉 任务圆满完成！已生成 {len(node_names)} 个独立节点。")

if __name__ == "__main__":
    main()
