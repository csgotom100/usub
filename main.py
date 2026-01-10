import requests
import os
import re

def extract_real_nodes(text):
    real_nodes = []
    # 匹配 Clash 节点块：从 - name: 开始，直到遇到下一个 - name: 或配置大项
    # 这个正则能完美提取包含 server, port, type 的完整块
    pattern = r'-\s*name:[\s\S]+?server:\s*[^\s]+[\s\S]+?(?=\n-\s*name:|\n[a-z\-]+:|$)'
    matches = re.findall(pattern, text)
    
    for m in matches:
        if "type:" in m and "server:" in m:
            real_nodes.append(m.strip())
            
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

    print(f"🚀 正在提取真实节点...")
    for idx, url in enumerate(urls):
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                nodes = extract_real_nodes(r.text)
                all_nodes.extend(nodes)
                if nodes: print(f"   [{idx+1}] ✅ 提取到 {len(nodes)} 个节点")
        except: continue

    unique_nodes = list(set(all_nodes))
    if not unique_nodes:
        print("❌ 没抓到任何有效节点")
        return

    print(f"--- 📊 汇总完成: 有效节点 {len(unique_nodes)} ---")

    # 1. 生成 V2Ray 订阅 (链接格式)
    with open("sub_v2ray.txt", "w", encoding="utf-8") as f:
        f.write("\n".join([n for n in unique_nodes if "://" in n]))

    # 2. 【核心】手动构建标准的 Clash 配置文件
    print(f"🎨 正在生成全手工 config.yaml...")
    
    # 提取节点名称用于分组
    node_names = []
    proxy_list = []
    
    for node in unique_nodes:
        if "- name:" in node:
            # 提取 name: 后面的值
            name_match = re.search(r'name:\s*([''"]?)(.*?)\1(?:\s|$)', node)
            if name_match:
                name = name_match.group(2)
                node_names.append(name)
                proxy_list.append(node)
        elif "://" in node:
            # 这种链接需要转换，暂时放在备注里或跳过
            # 如果你有大量这种链接，我们可以以后再加转换逻辑
            continue

    # 构造 Clash 模板
    clash_config = [
        "port: 7890",
        "socks-port: 7891",
        "allow-lan: true",
        "mode: rule",
        "log-level: info",
        "external-controller: 127.0.0.1:9090",
        "",
        "proxies:"
    ]
    
    # 添加节点
    for p in proxy_list:
        # 确保缩进正确 (每个节点块前加两个空格)
        indented_node = "  " + p.replace("\n", "\n  ")
        clash_config.append(indented_node)

    # 添加基础策略组
    if node_names:
        clash_config.extend([
            "",
            "proxy-groups:",
            "  - name: 🚀 节点选择",
            "    type: select",
            "    proxies:"
        ])
        for name in node_names:
            clash_config.append(f"      - \"{name}\"")
        clash_config.append("      - DIRECT")

    # 添加基础规则
    clash_config.extend([
        "",
        "rules:",
        "  - GEOIP,CN,DIRECT",
        "  - MATCH,🚀 节点选择"
    ])

    with open("config.yaml", "w", encoding="utf-8") as f:
        f.write("\n".join(clash_config))
    
    print("🎉 任务圆满完成！config.yaml 已生成，包含完整节点和策略组。")

if __name__ == "__main__":
    main()
