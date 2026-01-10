import requests
import os
import time

def main():
    # 1. 读取 sources.txt
    if not os.path.exists('sources.txt'):
        print("❌ 没找到 sources.txt")
        return
    
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.startswith('http')]
    
    if not urls:
        print("⚠️ sources.txt 是空的")
        return

    print(f"✅ 准备处理 {len(urls)} 个链接")
    api_base = "http://127.0.0.1:25500/sub?"
    
    # 用来存储所有抓取到的节点内容
    all_clash_proxies = []
    all_v2ray_links = []

    for idx, url in enumerate(urls):
        print(f"[{idx+1}/{len(urls)}] 正在处理: {url[:50]}...")
        
        # 转换 Clash 格式
        try:
            # 加上 &list=true 方便我们之后自己合并
            clash_url = f"{api_base}target=clash&url={url}&list=true"
            r = requests.get(clash_url, timeout=15)
            if r.status_code == 200 and "proxies:" in r.text:
                # 简单提取 proxies 部分 (这里为了稳妥，我们后续直接用 v2ray 模式汇总再转)
                pass 
        except:
            pass

        # 转换 v2ray 格式 (这个最稳，因为是纯文本行)
        try:
            v2ray_url = f"{api_base}target=v2ray&url={url}&list=true"
            r = requests.get(v2ray_url, timeout=15)
            if r.status_code == 200:
                links = r.text.splitlines()
                all_v2ray_links.extend(links)
                print(f"   成功: 抓取到 {len(links)} 个节点")
            else:
                print(f"   跳过: 状态码 {r.status_code}")
        except Exception as e:
            print(f"   错误: {e}")
        
        # 稍微停顿一下，防止请求过快
        time.sleep(0.5)

    # 2. 去重汇总
    unique_links = list(set(all_v2ray_links))
    print(f"--- 汇总完毕，总计唯一节点: {len(unique_links)} ---")

    if not unique_links:
        print("❌ 未获取到任何有效节点")
        return

    # 3. 将汇总后的节点再次交给 SubConverter 生成最终文件
    # 我们把所有节点合并成一个大字符串，再转一次
    final_raw_text = "\n".join(unique_links)
    
    # 保存 v2ray 明文列表
    with open("sub_v2ray.txt", "w", encoding="utf-8") as f:
        f.write(final_raw_text)

    # 重点：利用 SubConverter 将汇总后的链接转为最终的 Clash 配置
    try:
        # 注意：这里我们使用 data 模式或者将汇总后的内容再次上传/转换
        # 最简单的方法：利用一个公开的 pastebin 或者直接让 subconverter 处理这一大串
        # 但既然我们有本地 subconverter，我们可以直接请求转换
        print("正在生成最终 config.yaml...")
        payload = {"target": "clash", "data": final_raw_text}
        # 使用 POST 请求处理大量数据
        r = requests.post("http://127.0.0.1:25500/sub", data=payload, timeout=30)
        if "proxies:" in r.text:
            with open("config.yaml", "w", encoding="utf-8") as f:
                f.write(r.text)
            print("🎉 最终 config.yaml 已生成")
    except Exception as e:
        print(f"生成最终配置失败: {e}")

if __name__ == "__main__":
    main()
