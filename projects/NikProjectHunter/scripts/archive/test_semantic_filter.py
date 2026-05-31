"""
测试语义过滤模块
测试场景：
1. 数据治理类项目 → 应该通过
2. OA系统/智慧校园 → 应该被过滤
3. 数据安全类项目 → 应该通过
4. AI项目 → 应该通过
"""

import asyncio
import json
from loguru import logger
from app.services.semantic_filter import semantic_filter


async def test_semantic_filter():
    logger.info("=" * 60)
    logger.info("🧪 语义过滤模块测试")
    logger.info("=" * 60)

    # ======================================================================
    # Test 1: 数据治理类项目
    # ======================================================================
    project_governance = {
        "title": "中国银行数据治理平台建设项目采购公告",
        "content": """
项目概况：中国银行总行拟建设企业级数据治理平台，实现全行数据标准管理、元数据管理、
数据质量管理、数据目录管理等功能。项目预算：800万元。
技术要求：支持主数据管理（MDM）、数据血缘追踪、数据质量监控、数据标准落地。
项目目标：构建全行级数据治理体系，提升数据资产化水平。
        """,
    }

    result1 = await semantic_filter.analyze(project_governance)
    logger.info(f"\n📋 Test 1 - 数据治理类项目")
    logger.info(f"   标题: {project_governance['title']}")
    logger.info(f"   结果: {'✅ 通过' if result1['is_relevant'] else '❌ 拒绝'}")
    logger.info(f"   评分: {result1['relevance_score']}")
    logger.info(f"   分类: {result1['category']}")
    logger.info(f"   原因: {result1['reason']}")

    # ======================================================================
    # Test 2: OA系统（应被过滤）
    # ======================================================================
    project_oa = {
        "title": "XX集团协同办公OA系统升级改造项目",
        "content": """
项目概况：XX集团拟对现有OA系统进行全面升级改造，实现办公自动化、流程审批、
公文管理、会议管理等功能。项目预算：200万元。
技术要求：支持移动办公、电子签章、流程引擎。
        """,
    }

    result2 = await semantic_filter.analyze(project_oa)
    logger.info(f"\n📋 Test 2 - OA系统（应被过滤）")
    logger.info(f"   标题: {project_oa['title']}")
    logger.info(f"   结果: {'✅ 通过' if result2['is_relevant'] else '❌ 拒绝'}")
    logger.info(f"   评分: {result2['relevance_score']}")
    logger.info(f"   拒绝原因: {result2.get('rejection_reason', '')}")

    # ======================================================================
    # Test 3: 数据安全类项目
    # ======================================================================
    project_security = {
        "title": "XX省数据分类分级及安全风险评估服务采购项目",
        "content": """
项目概况：XX省大数据局拟采购数据分类分级及安全风险评估服务。
工作内容：对全省政务数据进行全面分类分级，开展数据安全风险评估，
建立数据安全治理体系。项目预算：500万元。
资质要求：具备数据安全评估资质，有政务数据安全治理经验。
        """,
    }

    result3 = await semantic_filter.analyze(project_security)
    logger.info(f"\n📋 Test 3 - 数据安全类项目")
    logger.info(f"   标题: {project_security['title']}")
    logger.info(f"   结果: {'✅ 通过' if result3['is_relevant'] else '❌ 拒绝'}")
    logger.info(f"   评分: {result3['relevance_score']}")
    logger.info(f"   分类: {result3['category']}")

    # ======================================================================
    # Test 4: 智慧校园（应被过滤）
    # ======================================================================
    project_campus = {
        "title": "XX大学智慧校园信息化建设（一期）项目",
        "content": """
项目概况：XX大学拟建设智慧校园，包含校园一卡通、教务管理系统、
学生管理系统、校园门户网站等。项目预算：1500万元。
        """,
    }

    result4 = await semantic_filter.analyze(project_campus)
    logger.info(f"\n📋 Test 4 - 智慧校园（应被过滤）")
    logger.info(f"   标题: {project_campus['title']}")
    logger.info(f"   结果: {'✅ 通过' if result4['is_relevant'] else '❌ 拒绝'}")
    logger.info(f"   评分: {result4['relevance_score']}")
    logger.info(f"   拒绝原因: {result4.get('rejection_reason', '')}")

    # ======================================================================
    # Test 5: AI大模型类项目
    # ======================================================================
    project_ai = {
        "title": "XX银行AI大模型应用平台建设项目",
        "content": """
项目概况：XX银行拟建设AI大模型应用平台，基于LLM技术构建智能客服、
智能风控、智能营销等应用场景。项目预算：1200万元。
技术要求：支持大模型训练和推理、RAG知识库、Agent框架、
多智能体协同。需要具备NLP、深度学习等AI技术能力。
        """,
    }

    result5 = await semantic_filter.analyze(project_ai)
    logger.info(f"\n📋 Test 5 - AI大模型类项目")
    logger.info(f"   标题: {project_ai['title']}")
    logger.info(f"   结果: {'✅ 通过' if result5['is_relevant'] else '❌ 拒绝'}")
    logger.info(f"   评分: {result5['relevance_score']}")
    logger.info(f"   分类: {result5['category']}")

    # ======================================================================
    # Test 6: 网络设备采购（应被过滤）
    # ======================================================================
    project_network = {
        "title": "XX数据中心网络设备及服务器采购项目",
        "content": """
项目概况：XX单位采购核心交换机、路由器、防火墙、服务器等网络设备一批。
项目预算：300万元。
        """,
    }

    result6 = await semantic_filter.analyze(project_network)
    logger.info(f"\n📋 Test 6 - 网络设备采购（应被过滤）")
    logger.info(f"   标题: {project_network['title']}")
    logger.info(f"   结果: {'✅ 通过' if result6['is_relevant'] else '❌ 拒绝'}")
    logger.info(f"   评分: {result6['relevance_score']}")

    # ======================================================================
    # Summary
    # ======================================================================
    logger.info("\n" + "=" * 60)
    logger.info("📊 测试汇总")
    logger.info(f"   Test 1 (数据治理): {'✅' if result1['is_relevant'] else '❌'} (期望: ✅)")
    logger.info(f"   Test 2 (OA系统):   {'✅' if result2['is_relevant'] else '❌'} (期望: ❌)")
    logger.info(f"   Test 3 (数据安全): {'✅' if result3['is_relevant'] else '❌'} (期望: ✅)")
    logger.info(f"   Test 4 (智慧校园): {'✅' if result4['is_relevant'] else '❌'} (期望: ❌)")
    logger.info(f"   Test 5 (AI大模型): {'✅' if result5['is_relevant'] else '❌'} (期望: ✅)")
    logger.info(f"   Test 6 (网络设备): {'✅' if result6['is_relevant'] else '❌'} (期望: ❌)")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_semantic_filter())