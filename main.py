import requests
import os
import re

def clean_text(text):
    """简单清洗：去掉 HTML 标签，只保留疑似节点协议的内容"""
    # 如果内容包含 HTML 标签，尝试提取可能存在的 Base64 或 节点行
    if "<html" in text.lower():
        # 提取可能是 Base64 的长字符串
        match = re.search(r'[A-Za-z0-9+/=]{50,}', text)
        return match.group(0) if match else ""
    return text

def main():
    if not os.path.exists('sources.txt'):
        print("❌ 没找到 sources.txt")
        return
    
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]
    
    all_raw_content = []
    print(f"🚀 开始手动下载 {len(urls)} 个源...")

    headers = {'User-Agent': 'clash-verge/1.0; Mozilla/5.0'}

    for idx, url in enumerate(urls):
        try:
            # 第一步：Python 手动下载
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code == 200:
                content = clean_text(r.text.strip())
                if content:
                    all_raw_content.append(content)
                    print(f"   [{idx+1}] 下载成功: {url[:40]}...")
            else:
                print(f"   [{idx+1}] 下载失败 (HTTP {r.status_code}): {url[:40]}")
        except Exception as e:
            print(f"   [{idx+1}] 连接错误: {e}")

    if not all_raw_content:
        print("❌ 没有任何有效内容可供转换")
        return

    # 第二步：合并所有内容
    full_data = "\n".join(all_raw_content)
    
    # 第三步：将所有内容 POST 给本地 SubConverter 转换成明文 V2Ray 格式
    print(f"📦 正在将汇总数据交给 SubConverter 提取节点...")
    try:
        # 使用 /conat 接口或 data 参数直接处理文本
        # 我们先把它转成 v2ray 列表，这样方便后续去重
        post_data = {
            "target": "v2ray",
            "data": full_data,
            "list": "true"
        }
        r = requests.post("http://127.0.0.1:25500/sub", data=post_data, timeout=60)
        
        if r.status_code == 200 and r.text.strip():
            links = list(set(r.text.splitlines())) # 去重
            print(f"✅ 提取成功，共 {len(links)} 个唯一节点")
            
            # 保存 V2Ray 列表
            with open("sub_v2ray.txt", "w", encoding="utf-8") as f:
                f.write("\n".join(links))

            # 第四步：将去重后的链接再次转为 Clash
            print("🎨 正在生成最终 config.yaml...")
            post_data_clash = {
                "target": "clash",
                "data": "\n".join(links)
            }
            r_clash = requests.post("http://127.0.0.1:25500/sub", data=post_data_clash, timeout=60)
            if "proxies:" in r_clash.text:
                with open("config.yaml", "w", encoding="utf-8") as f:
                    f.write(r_clash.text)
                print("🎉 config.yaml 生成成功！")
        else:
            print(f"❌ SubConverter 提取失败: {r.status_code} {r.text[:100]}")
    except Exception as e:
        print(f"❌ 最终转换环节崩溃: {e}")

if __name__ == "__main__":
    main()
