import requests
import urllib.parse
import os

def main():
    # 1. 读取 sources.txt
    if not os.path.exists('sources.txt'):
        print("❌ 没找到 sources.txt")
        return
    
    with open('sources.txt', 'r', encoding='utf-8') as f:
        # 过滤掉非 http 链接并去重
        urls = list(set([l.strip() for l in f if l.startswith('http')]))
    
    if not urls:
        print("⚠️ sources.txt 里没有有效链接")
        return

    print(f"🚀 准备处理 {len(urls)} 个远程订阅源...")

    # SubConverter 本地服务地址
    api_base = "http://127.0.0.1:25500/sub?"

    # 2. 构造转换参数
    # target=clash: 生成 Clash 配置
    # url: 使用 | 分割多个链接
    # config: 使用内置的基础配置（可选）
    combined_urls = "|".join(urls)
    
    tasks = [
        ("config.yaml", "clash", "&emoji=true&list=false&udp=true"),
        ("sub_v2ray.txt", "v2ray", "&emoji=true&list=true")
    ]

    for filename, target, extra in tasks:
        try:
            print(f"🔄 正在转换至 {target}...")
            # 对超长 URL 进行编码
            api_url = f"{api_base}target={target}&url={urllib.parse.quote(combined_urls)}{extra}"
            
            # SubConverter 下载 30 多个源可能需要时间，超时设长一点
            r = requests.get(api_url, timeout=120)
            
            if r.status_code == 200:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(r.text)
                print(f"✅ {filename} 保存成功 (大小: {len(r.text)} 字节)")
            else:
                print(f"❌ {target} 转换失败: HTTP {r.status_code}")
                if r.status_code == 400:
                    print("提示: 可能是链接中包含特殊字符，或链接总数过多。")
        except Exception as e:
            print(f"❌ 运行异常: {e}")

if __name__ == "__main__":
    main()
