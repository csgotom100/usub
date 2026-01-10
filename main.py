import requests
import urllib.parse
import os
import time

def main():
    if not os.path.exists('sources.txt'): return
    with open('sources.txt', 'r', encoding='utf-8') as f:
        urls = list(set([l.strip() for l in f if l.startswith('http')]))
    
    if not urls: return

    print(f"🚀 开始逐个处理 {len(urls)} 个订阅源...")
    api_base = "http://127.0.0.1:25500/sub?"
    
    all_nodes = [] # 存放提取出的明文 v2ray 链接

    for idx, url in enumerate(urls):
        print(f"[{idx+1}/{len(urls)}] 正在抓取: {url[:50]}...")
        try:
            # 每一个源单独请求 SubConverter，转成明文列表(list=true)
            # 这样压力极小，几乎不会 500
            api_url = f"{api_base}target=v2ray&url={urllib.parse.quote(url)}&list=true"
            r = requests.get(api_url, timeout=20)
            
            if r.status_code == 200 and r.text.strip():
                lines = r.text.splitlines()
                valid_lines = [l for l in lines if "://" in l]
                all_nodes.extend(valid_lines)
                print(f"   ✅ 成功提取 {len(valid_lines)} 个节点")
            else:
                print(f"   ❌ 跳过 (HTTP {r.status_code})")
        except Exception as e:
            print(f"   ⚠️ 超时或错误")
        
        # 停顿一下，温柔一点
        time.sleep(0.2)

    # 去重
    unique_nodes = list(set(all_nodes))
    print(f"--- 📊 汇总完成: 唯一节点总数 {len(unique_nodes)} ---")

    if not unique_nodes:
        print("😭 最终没有获取到任何节点")
        return

    # 1. 保存 v2ray 明文列表
    with open("sub_v2ray.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(unique_nodes))

    # 2. 生成最终的 Clash 配置 (将汇总后的纯净节点再次喂给 SubConverter)
    print("🎨 正在渲染最终 config.yaml...")
    try:
        # 将所有节点拼成大字符串，使用 data 协议
        # 此时已经是纯净节点，SubConverter 处理起来飞快
        all_data = "\n".join(unique_nodes)
        
        # 如果节点太多，我们通过 POST 提交（SubConverter 的 /sub 接口也支持 POST data）
        payload = {"target": "clash", "data": all_data}
        r_clash = requests.post("http://127.0.0.1:25500/sub", data=payload, timeout=60)
        
        if "proxies:" in r_clash.text:
            with open("config.yaml", "w", encoding="utf-8") as f:
                f.write(r_clash.text)
            print("🎉 恭喜！config.yaml 终于生成成功了！")
        else:
            print("❌ 最后的渲染步骤失败了")
    except Exception as e:
        print(f"❌ 渲染异常: {e}")

if __name__ == "__main__":
    main()
