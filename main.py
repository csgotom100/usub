import requests
import os
import re
import urllib.parse

def clean_text(text):
    if "<html" in text.lower():
        match = re.search(r'[A-Za-z0-9+/=]{50,}', text)
        return match.group(0) if match else ""
    return text

def main():
    if not os.path.exists('sources.txt'): return
    
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]
    
    all_raw_content = []
    print(f"🚀 正在下载源并清洗数据...")
    headers = {'User-Agent': 'clash-verge/1.0; Mozilla/5.0'}

    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                content = clean_text(r.text.strip())
                if content: all_raw_content.append(content)
        except: continue

    if not all_raw_content:
        print("❌ 没有任何有效内容")
        return

    # --- 关键改动：写入本地文件而非传递超长参数 ---
    temp_file = "temp_nodes.txt"
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write("\n".join(all_raw_content))
    
    # 获取文件的绝对路径，并转换成 SubConverter 识别的本地文件 URL
    # 在 GitHub Actions 里的路径通常是 /home/runner/work/仓库名/仓库名/temp_nodes.txt
    abs_path = os.path.abspath(temp_file)
    file_url = f"http://127.0.0.1:25500/sub?target=v2ray&url={urllib.parse.quote(abs_path)}&list=true"

    print(f"📦 正在请求本地转换...")
    
    try:
        # SubConverter 支持直接读取本地绝对路径
        r = requests.get(file_url, timeout=60)
        
        if r.status_code == 200 and r.text.strip():
            links = list(set(r.text.splitlines())) # 去重
            print(f"✅ 提取成功，共 {len(links)} 个节点")
            
            # 保存 v2ray
            with open("sub_v2ray.txt", "w", encoding="utf-8") as f:
                f.write("\n".join(links))

            # 生成最终 Clash
            print("🎨 正在生成最终 config.yaml...")
            clash_url = f"http://127.0.0.1:25500/sub?target=clash&url={urllib.parse.quote(abs_path)}"
            r_clash = requests.get(clash_url, timeout=60)
            if "proxies:" in r_clash.text:
                with open("config.yaml", "w", encoding="utf-8") as f:
                    f.write(r_clash.text)
                print("🎉 任务圆满完成！")
        else:
            print(f"❌ 转换失败: HTTP {r.status_code}")
            # 调试信息：如果失败，看看日志
            if os.path.exists("subconverter/subconverter.log"):
                with open("subconverter/subconverter.log", "r") as log:
                    print("SubConverter 日志最后几行：")
                    print(log.readlines()[-5:])
    except Exception as e:
        print(f"❌ 发生异常: {e}")
    finally:
        if os.path.exists(temp_file): os.remove(temp_file)

if __name__ == "__main__":
    main()
