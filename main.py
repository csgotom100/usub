import requests
import os
import re

def extract_real_nodes(text):
    """
    精准提取：只保留真正的节点，剔除策略组和规则名
    """
    real_nodes = []
    
    # 1. 提取所有标准链接格式 (vmess://, ss://, trojan://, vless:// 等)
    links = re.findall(r'(?:vmess|ss|trojan|vless|ssr|hysteria2|hy2)://[^\s]+', text)
    real_nodes.extend(links)

    # 2. 提取 Clash 格式节点 (必须包含 type: 和 server:)
    # 我们寻找以 - name: 开头，且后面紧跟着类型和服务器地址的块
    clash_pattern = r'-\s*name:[^:]+?type:\s*\w+?[\s\S]+?server:\s*[^\s]+'
    clash_nodes = re.findall(clash_pattern, text)
    
    # 清理一下 clash 节点中的多余空白
    for node in clash_nodes:
        # 简单校验，防止误抓策略组
        if "server:" in node and "type:" in node:
            real_nodes.append(node.strip())

    return real_nodes

def main():
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]

    all_nodes = []
    headers = {'User-Agent': 'clash-verge/1.0'}

    print(f"🚀 正在精准过滤真实节点...")
    for idx, url in enumerate(urls):
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                nodes = extract_real_nodes(r.text)
                if nodes:
                    all_nodes.extend(nodes)
                    print(f"   [{idx+1}] ✅ 提取到 {len(nodes)} 个真实节点")
        except: continue

    unique_nodes = list(set(all_nodes))
    if not unique_nodes:
        print("❌ 没抓到任何带 IP 的真实节点，请检查源链接内容。")
        return

    print(f"--- 📊 汇总完成: 有效节点 {len(unique_nodes)} ---")

    # 保存明文
    with open("sub_v2ray.txt", "w", encoding="utf-8") as f:
        f.write("\n".join([n for n in unique_nodes if "://" in n]))

    # 构建 Clash
    print(f"🎨 正在渲染最终 config.yaml...")
    try:
        # 将节点列表发给后端
        data_content = "\n".join(unique_nodes)
        api_url = "http://127.0.0.1:25500/sub"
        params = {"target": "clash", "data": data_content, "emoji": "true"}
        
        r = requests.post(api_url, data=params, timeout=40)
        
        # 即使后端失败，我们也手动生成一个
        if "proxies:" in r.text:
            with open("config.yaml", "w", encoding="utf-8") as f:
                f.write(r.text)
            print("🎉 config.yaml 完美生成！")
        else:
            with open("config.yaml", "w", encoding="utf-8") as f:
                f.write("proxies:\n")
                for node in unique_nodes:
                    # 如果是链接格式，SubConverter 没转成，我们这里也存一份
                    f.write(f"  # {node[:30]}... (需要转换)\n")
            print("⚠️ 仅生成节点占位符，请检查后端 API 环境。")
            
    except Exception as e:
        print(f"❌ 错误: {e}")

if __name__ == "__main__":
    main()
