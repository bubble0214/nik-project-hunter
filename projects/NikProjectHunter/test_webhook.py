import asyncio
import httpx

async def test_webhook():
    # 测试企业微信 webhook
    webhook_url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
    
    # 从环境变量读取实际 URL
    import os
    webhook_url = os.getenv("WECHAT_WEBHOOK_URL", "")
    
    if not webhook_url:
        print("WECHAT_WEBHOOK_URL 未配置")
        return
    
    test_data = {
        "msgtype": "text",
        "text": {
            "content": "测试消息 - NPH 推送验证"
        }
    }
    
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(webhook_url, json=test_data)
        print(f"状态码: {resp.status_code}")
        print(f"响应: {resp.text}")

asyncio.run(test_webhook())