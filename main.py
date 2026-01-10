import requests
import os
import re

def clean_text(text):
    if "<html" in text.lower():
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
    print(f"🚀 开始下载 {len(urls)} 个源...")
    headers = {'User-Agent': 'clash-verge/1.0; Mozilla/5.0'}

    for idx, url in enumerate(urls):
        try:
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code == 200:
                content = clean_text(r.text.strip())
                if content:
                    all_raw_content.append(content)
                    print(f"   [{idx+1}] 成功")
        except:
            continue

    if not all_raw_content:
        print("❌ 没有任何有效内容")
        return

    # --- 核心改进：分段提取 ---
    final_links = set()
    print(f"📦 正在分段交给 SubConverter 处理 (共 {len(all_raw_content)} 段)...")
    
    for i, content in enumerate(all_raw_content):
        try:
            # 每一段单独发送，避免 413 错误
            post_data = {"target": "v2ray", "data": content, "list": "true"}
            r = requests.post("http://127.0.0.1:25500/sub", data=post_data, timeout=30)
            
            if r.status_code == 200:
                lines = r.text.splitlines()
                for line in lines:
                    if line.strip(): final_links.add(line.strip())
                print(f"   进度: {i+1}/{len(all_raw_content)} 提取完成")
            else:
                print(f"   跳过第 {i+1} 段: HTTP {r.status_code}")
        except:
            print(f"   第 {i+1} 段处理超时")

    links_list = list(final_links)
    print(f"✅ 汇总去重完成，共 {len(links_list)} 个唯一节点")

    if not links_list: return

    # 保存 v2ray 列表
    with open("sub_v2ray.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(links_list))

    # 最后一步：将去重后的干净链接转为 Clash
    # 此时 links_list 已经剔除了垃圾字符，体积大大缩小，POST 到 Clash 不会报 413
    print("🎨 正在生成最终 config.yaml...")
    try:
        final_post = {"target": "clash", "data": "\n".join(links_list)}
        r_clash = requests.post("http://127.0.0.1:25500/sub", data=final_post, timeout=60)
        if "proxies:" in r_clash.text:
            with open("config.yaml", "w", encoding="utf-8") as f:
                f.write(r_clash.text)
            print("🎉 全部完成！config.yaml 已就绪。")
    except Exception as e:
        print(f"❌ 最终 Clash 转换失败: {e}")

if __name__ == "__main__":
    main()
