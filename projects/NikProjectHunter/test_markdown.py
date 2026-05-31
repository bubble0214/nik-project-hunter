import asyncio
import httpx
import os

async def test_markdown():
    webhook_url = os.getenv("WECHAT_WEBHOOK_URL", "")
    if not webhook_url:
        print("WECHAT_WEBHOOK_URL 未配置")
        return
    
    # 构建企业微信 markdown 格式消息
    data = {
        "msgtype": "markdown",
        "markdown": {
            "content": f"""## 【🔥 每日商机汇报】

**1. 国家知识产权局专利局复杂数据标准化处理技术服务（2026-2027年）公开招标公告**
> 🏢 **采购单位**: 国家知识产权局
> 💰 **预算**: —
> 📍 **地区**: 北京
> 🏷️ **来源平台**: 中国政府采购网
> 📅 **发布日期**: 2026-05-30
> 🏷️ **公告类型**: 未知
> ⏰ **标书获取截止**: 待正式招标
> ⏰ **投标截止**: 待正式招标
> 🏗️ **销售方式**: 未知
> 📊 **评分/等级**: **88** / A
> 🔗 **详情链接**: [查看详情](https://www.ccgp.gov.cn/cggg/zygg/zbgg/202605/t20260530_123456.html)

---

> 📝 **项目摘要**: 复杂数据标准化处理技术服务

---
统计：共 1 条商机"""
        }
    }
    
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(webhook_url, json=data)
        print(f"状态码: {resp.status_code}")
        print(f"响应: {resp.text}")

asyncio.run(test_markdown())