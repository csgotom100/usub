import requests
import os
import re
import base64
import urllib.parse

def decode_base64(data):
    try:
        missing_padding = len(data) % 4
        if missing_padding: data += '=' * (4 - missing_padding)
        return base64.b64decode(data).decode('utf-8')
    except: return ""

def extract_nodes(text):
    nodes = []
    # 如果是 Base64 订阅，先解码
    if re.match(r'^[A-Za-z0-9+/=\s]+$', text) and len(text) > 50:
        text = decode_base64(text)

    lines = text.splitlines()
    for line in lines:
        line = line.strip()
        if "://" in line or "- name:" in line:
            nodes.append(line)
    return nodes

def main():
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]

    all_nodes = []
    headers = {'User-Agent': 'clash-verge/1.0'}

    print(f"🚀 正在清洗源数据...")
    for idx, url in enumerate(urls):
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                nodes = extract_nodes(r.text)
                all_nodes.extend(nodes)
        except: continue

    unique_nodes = list(set(all_nodes))
    if not unique_nodes: return

    # 保存 V2Ray 明文供备份
    with open("sub_v2ray.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(unique_nodes))

    print(f"🎨 尝试最终渲染 (节点数: {len(unique_nodes)})...")
    
    # --- 改进点：使用更标准的 API 请求 ---
    try:
        data_content = "\n".join(unique_nodes)
        # 很多时候 POST 请求在 GitHub Actions 环境下会因为 Body 太大被拦截
        # 我们改用一个特殊的本地 API 路径，并加上基础配置参数
        api_url = "http://127.0.0.1:25500/sub"
        params = {
            "target": "clash",
            "data": data_content,
            "list": "false",
            "emoji": "true",
            "udp": "true",
            "sort": "true"
        }
        
        # 使用 json 或 data 提交，并检查响应
        r = requests.post(api_url, data=params, timeout=40)
        
        if "proxies:" in r.text and len(r.text) > 500:
            with open("config.yaml", "w", encoding="utf-8") as f:
                f.write(r.text)
            print(f"🎉 config.yaml 完美生成！(大小: {len(r.text)} 字节)")
        else:
            # 如果后端还是吐不出来，我们就用 Python 拼一个带基础分组的 Clash 文件
            print("⚠️ 后端转换不完整，启动本地模板引擎...")
            clash_template = [
                "port: 7890",
                "allow-lan: true",
                "mode: rule",
                "log-level: info",
                "proxies:"
            ]
            for node in unique_nodes:
                if "- name:" in node:
                    clash_template.append(f"  {node.strip()}")
            
            # 这里可以手动添加基础的分组逻辑（如果需要）
            with open("config.yaml", "w", encoding="utf-8") as f:
                f.write("\n".join(clash_template))
            print("✅ 极简自建版 config.yaml 已就绪")
            
    except Exception as e:
        print(f"❌ 渲染失败: {e}")

if __name__ == "__main__":
    main()
