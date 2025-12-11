import requests
import traceback
import time
import os
import json

# API 密钥
CF_API_TOKEN    =   os.environ["CF_API_TOKEN"]
CF_ZONE_ID      =   os.environ["CF_ZONE_ID"]
CF_DNS_NAME     =   os.environ["CF_DNS_NAME"]
#在 Cloudflare 后台给DNS记录填写的备注关键词
CF_DNS_COMMENT  =   "auto" 

# notice
#PUSHPLUS_TOKEN  =   os.environ["PUSHPLUS_TOKEN"]
TELEGRAM_BOT_TOKEN  =   os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID  =   os.environ["TELEGRAM_CHAT_ID"]

headers = {
    'Authorization': f'Bearer {CF_API_TOKEN}',
    'Content-Type': 'application/json'
}

def get_cf_speed_test_ip(timeout=10, max_retries=5):
    for attempt in range(max_retries):
        try:
            response = requests.get('https://ip.164746.xyz/ipTop10.html', timeout=timeout)
            if response.status_code == 200:
                return response.text
        except Exception as e:
            traceback.print_exc()
            print(f"get_cf_speed_test_ip Request failed (attempt {attempt + 1}/{max_retries}): {e}")
    return None

#获取DNS记录 (增加备注筛选)
def get_dns_records(name):
    def_info = []
    url = f'https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records'
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        records = response.json()['result']
        for record in records:
            # 匹配域名 匹配类型为 A 记录 匹配备注(Comment)中包含特定关键词
            # record.get('comment', '') 获取备注，防止字段不存在报错
            record_comment = record.get('comment', '')
            if record_comment is None: record_comment = "" # 防止备注为 None

            if (record['name'] == name and 
                record['type'] == 'A' and 
                CF_DNS_COMMENT in str(record_comment)):
                
                def_info.append(record['id'])
        
        # 为了保证稳定性，可以对 ID 进行排序，确保每次更新的顺序一致
        def_info.sort() 
        return def_info
    else:
        print('Error fetching DNS records:', response.text)
        return []

# 更新 DNS 记录
def update_dns_record(record_id, name, cf_ip):
    url = f'https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records/{record_id}'
    data = {
        'type': 'A',
        'name': name,
        'content': cf_ip,
        # 更新时保留备注，否则备注会被清空导致下次脚本找不到这条记录
        'comment': CF_DNS_COMMENT 
    }

    response = requests.put(url, headers=headers, json=data)

    if response.status_code == 200:
        print(f"cf_dns_change success: ---- ip: {cf_ip}")
        return "ip:" + str(cf_ip) + " 解析 " + str(name) + " 成功"
    else:
        traceback.print_exc()
        print(f"cf_dns_change ERROR: {response.text}")
        return "ip:" + str(cf_ip) + " 解析 " + str(name) + " 失败"

def send_telegram_message(content):
    if not content: return
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    data = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': f"🌐 IP优选DNS更新通知\n\n{content}",
        'parse_mode': 'HTML'
    }
    try:
        requests.post(url, json=data, timeout=10)
    except Exception as e:
        print(f"❌ Telegram 通知异常: {e}")

def main():
    print("🚀 开始执行 DNS 更新任务 (仅更新备注含 '{CF_DNS_COMMENT}' 的记录)")
    
    # 获取优选IP
    ip_addresses_str = get_cf_speed_test_ip()
    if not ip_addresses_str:
        print("❌ 获取 IP 失败")
        return
    
    ip_addresses = ip_addresses_str.split(',')
    ip_addresses = [ip.strip() for ip in ip_addresses if ip.strip()][:4]
    
    # 获取特定备注的 DNS 记录
    dns_records = get_dns_records(CF_DNS_NAME)
    
    if not dns_records:
        print(f"❌ 未找到任何域名为 {CF_DNS_NAME} 且备注包含 '{CF_DNS_COMMENT}' 的 A 记录。请先去 Cloudflare 后台给要更新的 3 条记录添加备注")
        return

    print(f"📡 匹配到 {len(dns_records)} 条带有 '{CF_DNS_COMMENT}' 备注的记录")
    print(f"📊 准备更新的优选 IP: {ip_addresses}")

    send_telegram_message_content = []
    
    # 只更新匹配数量的记录 (取最小值)
    # 比如你后台标记了 3 条记录，拿到了 3 个IP，就更新 3 次
    # 如果后台标记了 5 条，只拿到 3 个IP，只更新前 3 条，不多删也不乱改
    update_count = min(len(ip_addresses), len(dns_records))
    
    for i in range(update_count):
        print(f"\n   [{i+1}/{update_count}] 更新记录 {dns_records[i]} → {ip_addresses[i]}")
        dns = update_dns_record(dns_records[i], CF_DNS_NAME, ip_addresses[i])
        send_telegram_message_content.append(dns)

    # 这里的逻辑改为：仅仅是遍历完了，不删除任何东西
    print(f"\n✅ 更新完成，共更新 {update_count} 条")
    
    if send_telegram_message_content:
        send_telegram_message('\n'.join(send_telegram_message_content))

if __name__ == '__main__':
    main()
