import requests
import os
import re
import base64

def decode_base64(data):
    """尝试解码 Base64 数据"""
    try:
        # 补全 Base64 末尾的等号
        missing_padding = len(data) % 4
        if missing_padding:
            data += '=' * (4 - missing_padding)
        return base64.b64decode(data).decode('utf-8')
    except:
        return ""

def extract_nodes(text):
    """从文本中提取节点行 (支持明文和 Base64)"""
    nodes = []
    # 如果是 Base64 订阅，先解码
    if re.match(r'^[A-Za-z0-9+/=\s]+$', text) and len(text) > 50:
        decoded = decode_base64(text)
        if decoded: text = decoded

    # 提取所有看起来像节点的行 (ss, vmess, vless, trojan, hysteria 等)
    lines = text.splitlines()
    for line in lines:
        line = line.strip()
        if "://" in line: # 标准链接格式
            nodes.append(line)
        elif "- name:" in line: # Clash 格式节点行
            nodes.append(line)
    return nodes

def main():
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]

    all_nodes = []
    headers = {'User-Agent': 'clash-verge/1.0'}

    print(f"🚀 正在本地下载并分析源数据...")
    for idx, url in enumerate(urls):
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                nodes = extract_nodes(r.text)
                if nodes:
                    all_nodes.extend(nodes)
                    print(f"   [{idx+1}] ✅ 提取到 {len(nodes)} 个节点")
        except: continue

    # 去重
    unique_nodes = list(set(all_nodes))
    print(f"--- 📊 汇总完成: 唯一节点总数 {len(unique_nodes)} ---")

    if not unique_nodes:
        print("❌ 最终没有获取到任何节点")
        return

    # 1. 生成 V2Ray 订阅文件
    with open("sub_v2ray.txt", "w", encoding="utf-8") as f:
        f.write("\n".join([n for n in unique_nodes if "://" in n]))
    print("🎉 sub_v2ray.txt 生成成功")

    # 2. 生成一个最基础的 Clash 配置文件
    # 如果节点是 Clash 格式则直接放进 proxies，如果是链接格式则放入后端的 data 转换
    # 为了保险，我们直接尝试再次 POST 给后端（因为这次数据很小）
    # 如果后端还是不行，我们就生成一个简单的列表
    print("🎨 正在尝试最终渲染...")
    try:
        payload = "\n".join(unique_nodes)
        r = requests.post("http://127.0.0.1:25500/sub", data={"target": "clash", "data": payload}, timeout=30)
        
        if "proxies:" in r.text:
            with open("config.yaml", "w", encoding="utf-8") as f:
                f.write(r.text)
            print("🎉 config.yaml 完美生成！")
        else:
            # 兜底：如果后端还是空白，手动生成一个极简 Clash
            with open("config.yaml", "w", encoding="utf-8") as f:
                f.write("proxies:\n")
                for node in unique_nodes:
                    if "- name:" in node: f.write(f"{node}\n")
            print("⚠️ 后端仍不可用，已生成极简版 config.yaml")
    except:
        print("❌ 转换失败")

if __name__ == "__main__":
    main()
