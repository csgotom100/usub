import requests
import os
import re

def extract_real_nodes(text):
    real_nodes = []
    # 匹配 Clash 节点块：从 - name: 开始，直到遇到下一个 - name: 或配置大项
    # 这个正则能处理各种缩进不规范的情况
    pattern = r'(?:^|\n)-\s*name:[\s\S]+?(?=\n(?:-?\s*name:|[a-z\-]+:)|$)'
    matches = re.findall(pattern, text)
    
    for m in matches:
        content = m.strip()
        if "server:" in content and "type:" in content:
            real_nodes.append(content)
            
    # 同时兼容提取标准链接 (vmess/ss等)
    links = re.findall(r'(?:vmess|ss|trojan|vless|ssr|hy2)://[^\s]+', text)
    real_nodes.extend(links)
    
    return real_nodes

def main():
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]

    all_nodes = []
    headers = {'User-Agent': 'clash-verge/1.0'}

    print(f"🚀 开始深度扫描节点...")
    for idx, url in enumerate(urls):
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                nodes = extract_real_nodes(r.text)
                if nodes:
                    all_nodes.extend(nodes)
                    print(f"   [{idx+1}] ✅ 提取到 {len(nodes)} 个节点")
        except: continue

    # 简单去重
    unique_nodes = list(set(all_nodes))
    if not unique_nodes:
        print("❌ 未抓取到有效节点，请检查源链接")
        return

    print(f"--- 📊 汇总完成: 有效节点 {len(unique_nodes)} ---")

    # 1. 保存原始节点供调试
    with open("sub_v2ray.txt", "w", encoding="utf-8") as f:
        f.write("\n\n".join(unique_nodes))

    # 2. 构建 config.yaml
    node_names = []
    proxy_blocks = []
    
    for node in unique_nodes:
        # 清理节点内容：移除可能存在的旧缩进，统一由脚本添加
        clean_node = node.lstrip('-').lstrip() 
        # 尝试提取名字用于策略组
        name_match = re.search(r'name:\s*["\']?(.*?)["\']?(?:\n|$)', clean_node)
        if name_match:
            name = name_match.group(1).strip()
            # 这里的名字如果包含特殊字符，最好用引号包裹
            node_names.append(name)
            proxy_blocks.append(clean_node)

    clash_template = [
        "port: 7890",
        "socks-port: 7891",
        "allow-lan: true",
        "mode: rule",
        "log-level: info",
        "proxies:"
    ]
    
    # 填充 proxies
    for block in proxy_blocks:
        # 每个节点块开头必须是 - name: 且带两个空格缩进
        lines = block.splitlines()
        clash_template.append(f"  - {lines[0]}") # 处理第一行 name
        for line in lines[1:]:
            clash_template.append(f"    {line.strip()}") # 其余行增加四个空格缩进

    # 填充策略组
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

    # 填充规则
    clash_template.extend([
        "",
        "rules:",
        "  - GEOIP,CN,DIRECT",
        "  - MATCH,🚀 节点选择"
    ])

    with open("config.yaml", "w", encoding="utf-8") as f:
        f.write("\n".join(clash_template))
    
    print("🎉 config.yaml 注入成功！")

if __name__ == "__main__":
    main()
