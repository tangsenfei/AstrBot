"""
从 agency-agents 项目的 MD 文件中提取专家信息，生成全中文 JSON 模板文件。
用法: python extract_experts.py <agency-agents-dir> <output-dir>
"""
import sys
import os
import json
import re
from pathlib import Path


CATEGORY_MAP = {
    "academic": {"key": "academic", "label": "学术研究", "icon": "mdi-school"},
    "design": {"key": "design", "label": "设计体验", "icon": "mdi-palette"},
    "engineering": {"key": "engineering", "label": "工程开发", "icon": "mdi-code-tags"},
    "finance": {"key": "finance", "label": "财务金融", "icon": "mdi-currency-usd"},
    "game-development": {"key": "game", "label": "游戏开发", "icon": "mdi-gamepad-variant"},
    "marketing": {"key": "marketing", "label": "营销增长", "icon": "mdi-chart-line"},
    "paid-media": {"key": "paid_media", "label": "付费媒体", "icon": "mdi-currency-usd-circle"},
    "product": {"key": "product", "label": "产品管理", "icon": "mdi-clipboard-text"},
    "project-management": {"key": "project", "label": "项目管理", "icon": "mdi-calendar-check"},
    "sales": {"key": "sales", "label": "销售", "icon": "mdi-handshake"},
    "spatial-computing": {"key": "spatial", "label": "空间计算", "icon": "mdi-virtual-reality"},
    "specialized": {"key": "specialized", "label": "专项能力", "icon": "mdi-star-circle"},
    "support": {"key": "support", "label": "客户支持", "icon": "mdi-lifebuoy"},
    "testing": {"key": "testing", "label": "测试", "icon": "mdi-test-tube"},
}

ZH_NAMES_FILE = "scripts/i18n/agent-names-zh.json"
SKIP_DIRS = {".github", "scripts", "integrations", "examples", "strategy"}

EMOJI_ICON_MAP = {
    "🏛️": "mdi-domain", "📊": "mdi-chart-bar", "♟️": "mdi-chess",
    "🔌": "mdi-plug", "🛡️": "mdi-shield", "🎨": "mdi-palette",
    "🔍": "mdi-magnify", "📱": "mdi-cellphone", "🎮": "mdi-gamepad-variant",
    "🚀": "mdi-rocket", "💰": "mdi-cash", "📈": "mdi-chart-line",
    "🎯": "mdi-bullseye", "🔧": "mdi-wrench", "📝": "mdi-notebook",
    "🏗️": "mdi-hammer", "🧪": "mdi-flask", "🎓": "mdi-school",
    "⚖️": "mdi-scale-balance", "🌐": "mdi-web", "🎤": "mdi-microphone",
    "🤖": "mdi-robot", "💡": "mdi-lightbulb", "🔑": "mdi-key",
    "🧬": "mdi-dna", "⚡": "mdi-lightning-bolt", "🛠️": "mdi-tools",
    "📦": "mdi-package-variant", "🔒": "mdi-lock", "🎪": "mdi-tent",
    "🧠": "mdi-brain", "📐": "mdi-ruler-square", "✨": "mdi-star-shooting",
    "🎭": "mdi-drama-masks", "🦾": "mdi-arm-flex",
    "📡": "mdi-satellite-variant", "🔮": "mdi-crystal-ball", "🧲": "mdi-magnet",
    "🗂️": "mdi-folder-multiple", "🧩": "mdi-puzzle", "🗺️": "mdi-map",
    "💎": "mdi-diamond-stone", "🔭": "mdi-telescope",
    "🪄": "mdi-wand", "📋": "mdi-clipboard-check", "🏆": "mdi-trophy", "🔬": "mdi-microscope",
}

CAPABILITY_DESC_TEMPLATES = {
    "架构设计": "负责系统整体架构设计与技术选型",
    "主题开发": "负责主题定制与开发实现",
    "插件/模块开发": "负责插件和功能模块的设计与开发",
    "内容架构": "负责内容体系的规划与组织",
    "代码优先CMS": "基于代码驱动的CMS架构实现",
    "编写整洁可维护代码": "遵循最佳实践编写高质量代码",
    "设计评审": "对设计方案进行专业评审与优化建议",
    "精准实现": "按照规范精准实现功能需求",
    "持续改进": "持续优化流程与产出质量",
    "潜在客户开发": "识别和开发潜在客户资源",
    "冷启动外联": "通过冷启动方式建立客户联系",
    "跟进序列": "设计和管理客户跟进流程",
    "异议处理": "专业处理客户异议和顾虑",
    "方案撰写": "撰写专业的商业方案和提案",
    "销售漏斗管理": "管理和优化销售漏斗各阶段",
    "入职前准备": "新员工入职前的准备工作",
    "首日体验": "确保新员工首日体验顺畅",
    "首周融入": "帮助新员工快速融入团队",
    "福利与合规": "管理员工福利和合规事务",
    "退货受理": "受理和处理客户退货请求",
    "退货处理": "执行退货流程和库存管理",
    "退款管理": "处理退款申请和资金返还",
    "防欺诈": "识别和防范欺诈行为",
    "换货处理": "处理客户换货请求和物流",
    "预约管理": "管理客户预约和排程",
    "账单与保险": "处理账单和保险相关事务",
    "保险导航": "协助客户理解和选择保险方案",
    "投诉解决": "高效解决客户投诉和纠纷",
    "预订管理": "管理客户预订和资源分配",
    "到店前服务": "提供到店前的准备和引导服务",
    "入住/退房": "处理入住和退房流程",
    "礼宾服务": "提供专业的礼宾和接待服务",
    "客人投诉": "妥善处理客人投诉和反馈",
    "会员计划": "管理和优化会员忠诚度计划",
    "旅行翻译": "提供旅行场景的专业翻译服务",
    "医疗翻译": "提供医疗场景的专业翻译服务",
    "商务翻译": "提供商务场景的专业翻译服务",
    "紧急翻译": "提供紧急场景的即时翻译服务",
    "工时记录": "准确记录和管理工时数据",
    "账单叙述": "撰写专业的账单叙述说明",
    "发票生成": "生成规范准确的发票文档",
    "催收管理": "管理应收账款催收流程",
    "信托账户": "管理信托账户和资金",
    "初步筛选": "对案件或客户进行初步筛选",
    "客户资质评估": "评估潜在客户的资质和匹配度",
    "利益冲突审查": "审查潜在的利益冲突",
    "受理摘要": "生成案件受理的摘要文档",
    "合同审查": "审查合同条款和风险点",
    "诉讼文件": "准备和管理诉讼相关文件",
    "房地产": "处理房地产相关法律事务",
    "风险标记": "识别和标记潜在风险",
    "借款人受理": "受理借款人申请和资料",
    "预审资格": "评估借款人预审资格",
    "申请处理": "处理贷款申请和审批流程",
    "合规追踪": "追踪和确保合规要求",
    "利率报价": "提供准确的利率报价方案",
    "买方代理": "代表买方进行交易谈判",
    "卖方代理": "代表卖方进行交易谈判",
    "市场分析": "分析市场趋势和竞争态势",
    "报价谈判": "进行专业的报价和谈判",
    "交易协调": "协调交易各环节的执行",
    "交割支持": "提供交易交割的支持服务",
    "持续学习": "持续学习新技术和新方法",
    "自主优化": "自主优化工作流程和产出",
    "财务影响评估": "评估决策的财务影响",
    "影子测试": "在影子环境中进行测试验证",
    "语义异常压缩": "通过语义聚类压缩异常数据",
    "离线SLM修复生成": "使用离线小模型生成修复方案",
    "零数据丢失保障": "确保数据处理零丢失",
    "后端架构": "设计和优化后端系统架构",
    "API设计": "设计规范高效的API接口",
    "数据库优化": "优化数据库性能和查询效率",
    "微服务": "设计和实现微服务架构",
    "代码审查": "审查代码质量和规范合规性",
    "质量保证": "确保交付产出的质量标准",
    "安全审计": "进行安全审计和漏洞排查",
    "性能优化": "优化系统性能和响应速度",
    "CI/CD流水线": "构建和维护CI/CD自动化流水线",
    "基础设施即代码": "用代码管理基础设施配置",
    "监控与告警": "建立系统监控和告警机制",
    "事件响应": "快速响应和处理系统事件",
    "前端开发": "开发高质量的前端界面和交互",
    "UI/UX实现": "实现优秀的用户体验设计",
    "响应式设计": "实现跨设备的响应式布局",
    "移动开发": "开发移动端应用和功能",
    "跨平台": "实现跨平台兼容的应用",
    "数据工程": "构建和维护数据管道",
    "ETL管道": "设计和实现ETL数据管道",
    "数据仓库": "设计和管理数据仓库",
    "机器学习": "构建和训练机器学习模型",
    "模型部署": "部署模型到生产环境",
    "特征工程": "进行特征提取和工程化",
    "云基础设施": "管理云平台基础设施",
    "容器编排": "使用容器技术编排服务",
    "安全工程": "构建安全防护体系",
    "威胁检测": "检测和识别安全威胁",
    "漏洞评估": "评估系统安全漏洞",
    "技术写作": "撰写高质量技术文档",
    "文档编写": "编写规范完整的项目文档",
    "游戏设计": "设计游戏核心玩法和机制",
    "游戏机制": "设计和平衡游戏机制",
    "关卡设计": "设计游戏关卡和流程",
    "游戏AI": "实现游戏中的AI行为",
    "物理引擎": "实现游戏物理模拟",
    "渲染": "优化游戏渲染管线",
    "音频工程": "处理游戏音频和音效",
    "多人网络": "实现多人在线网络功能",
    "UI/UX设计": "设计游戏界面和交互体验",
    "用户研究": "进行用户研究和需求分析",
    "交互设计": "设计产品交互流程",
    "视觉设计": "进行产品视觉设计",
    "设计系统": "构建和维护设计系统",
    "原型设计": "快速制作产品原型",
    "可用性测试": "进行产品可用性测试",
    "内容策略": "制定内容策略和规划",
    "SEO优化": "优化搜索引擎排名",
    "文案撰写": "撰写高质量营销文案",
    "社交媒体": "运营社交媒体渠道",
    "邮件营销": "策划和执行邮件营销",
    "品牌策略": "制定品牌策略和定位",
    "增长黑客": "通过创新方法实现增长",
    "转化优化": "优化用户转化流程",
    "数据分析": "分析数据并提取洞察",
    "A/B测试": "设计和分析A/B测试",
    "产品策略": "制定产品策略和方向",
    "路线图规划": "规划产品路线图和里程碑",
    "用户故事": "编写和管理用户故事",
    "迭代规划": "进行迭代规划和排期",
    "干系人管理": "管理项目干系人关系",
    "风险管理": "识别和管理项目风险",
    "资源分配": "合理分配项目资源",
    "预算管理": "管理项目预算和成本",
    "时间线管理": "管理项目时间线和进度",
    "敏捷方法": "运用敏捷方法管理项目",
    "销售策略": "制定和执行销售策略",
    "线索生成": "生成和培育销售线索",
    "客户管理": "管理客户关系和账户",
    "收入优化": "优化收入结构和定价",
    "CRM管理": "管理CRM系统和数据",
    "区域规划": "规划和管理销售区域",
    "财务分析": "进行财务数据分析和报告",
    "投资策略": "制定投资策略和组合",
    "风险评估": "评估投资风险和收益",
    "投资组合管理": "管理投资组合配置",
    "监管合规": "确保符合监管要求",
    "税务策略": "制定税务优化策略",
    "审计管理": "管理审计流程和报告",
    "学术研究": "进行学术研究和论文撰写",
    "文献综述": "撰写文献综述和研究背景",
    "假设检验": "设计和执行假设检验",
    "同行评审": "进行学术同行评审",
    "基金申请": "撰写研究基金申请书",
    "空间计算": "开发空间计算应用",
    "AR/VR开发": "开发增强现实和虚拟现实应用",
    "3D建模": "进行3D模型设计和制作",
    "传感器集成": "集成各类传感器和数据",
    "计算机视觉": "实现计算机视觉算法",
    "空间映射": "实现空间映射和定位",
    "嵌入式系统": "开发嵌入式系统固件",
    "固件开发": "开发设备固件和驱动",
    "硬件集成": "集成硬件组件和接口",
    "实时系统": "开发实时响应系统",
    "智能合约": "开发和审计智能合约",
    "区块链": "开发区块链应用和协议",
    "去中心化金融": "开发DeFi协议和应用",
    "代币经济": "设计代币经济模型",
    "NFT开发": "开发NFT相关应用",
    "微信开发": "开发微信生态应用",
    "小程序": "开发微信小程序",
    "飞书集成": "集成飞书平台功能",
    "邮件智能": "实现邮件智能处理",
    "语音AI": "开发语音AI应用",
    "入职引导": "设计新员工入职引导流程",
    "客户成功": "管理客户成功和续约",
    "技术支持": "提供专业技术支持",
    "知识库": "构建和维护知识库",
    "工单管理": "管理和跟踪工单处理",
    "升级处理": "处理问题升级和协调",
    "测试自动化": "构建测试自动化框架",
    "单元测试": "编写和维护单元测试",
    "集成测试": "设计和执行集成测试",
    "性能测试": "进行系统性能测试",
    "负载测试": "进行系统负载和压力测试",
    "安全测试": "进行安全渗透测试",
    "端到端测试": "设计和执行端到端测试",
    "无障碍测试": "进行无障碍访问测试",
    "快速原型": "快速构建产品原型验证",
    "Git工作流": "管理Git工作流和分支策略",
    "代码库入门": "帮助快速上手代码库",
    "最小变更": "遵循最小变更原则",
    "Filament优化": "优化Filament框架性能",
}


def translate_capability_desc(zh_name, en_desc=""):
    if zh_name in CAPABILITY_DESC_TEMPLATES:
        return CAPABILITY_DESC_TEMPLATES[zh_name]
    if en_desc:
        return en_desc
    return f"精通{zh_name}领域的专业实践"


CAPABILITY_ZH_MAP = {
    "Architecture": "架构设计",
    "Theme Development": "主题开发",
    "Plugin/Module Development": "插件/模块开发",
    "Content Architecture": "内容架构",
    "Code-First CMS": "代码优先CMS",
    "Write clean, maintainable code": "编写整洁可维护代码",
    "Design Review": "设计评审",
    "Implement with precision": "精准实现",
    "Continuous Improvement": "持续改进",
    "Prospecting": "潜在客户开发",
    "Cold Outreach": "冷启动外联",
    "Follow-Up Sequences": "跟进序列",
    "Objection Handling": "异议处理",
    "Proposal Writing": "方案撰写",
    "Pipeline Management": "销售漏斗管理",
    "Pre-boarding": "入职前准备",
    "Day One Experience": "首日体验",
    "First Week Integration": "首周融入",
    "Benefits & Compliance": "福利与合规",
    "Return Intake": "退货受理",
    "Return Processing": "退货处理",
    "Refund Management": "退款管理",
    "Fraud Prevention": "防欺诈",
    "Exchange Handling": "换货处理",
    "Appointments": "预约管理",
    "Billing & Insurance": "账单与保险",
    "Insurance Navigation": "保险导航",
    "Complaint Resolution": "投诉解决",
    "Reservations": "预订管理",
    "Pre-Arrival": "到店前服务",
    "Check-In/Out": "入住/退房",
    "Concierge Services": "礼宾服务",
    "Guest Complaints": "客人投诉",
    "Loyalty Programs": "会员计划",
    "Travel": "旅行翻译",
    "Medical": "医疗翻译",
    "Business": "商务翻译",
    "Emergency": "紧急翻译",
    "Time Capture": "工时记录",
    "Billing Narratives": "账单叙述",
    "Invoice Generation": "发票生成",
    "Collections": "催收管理",
    "Trust Accounts": "信托账户",
    "Initial Screening": "初步筛选",
    "Prospect Qualification": "客户资质评估",
    "Conflict Checks": "利益冲突审查",
    "Intake Summaries": "受理摘要",
    "Contract Review": "合同审查",
    "Litigation Documents": "诉讼文件",
    "Real Estate": "房地产",
    "Risk Flagging": "风险标记",
    "Borrower Intake": "借款人受理",
    "Pre-Qualification": "预审资格",
    "Application Processing": "申请处理",
    "Compliance Tracking": "合规追踪",
    "Rate Quotes": "利率报价",
    "Buyer Representation": "买方代理",
    "Seller Representation": "卖方代理",
    "Market Analysis": "市场分析",
    "Offer Negotiation": "报价谈判",
    "Transaction Coordination": "交易协调",
    "Closing Support": "交割支持",
    "Continual Learning": "持续学习",
    "Autonomous Optimization": "自主优化",
    "Financial Impact Assessment": "财务影响评估",
    "Shadow Testing": "影子测试",
    "Semantic Anomaly Compression": "语义异常压缩",
    "Air-Gapped SLM Fix Generation": "离线SLM修复生成",
    "Zero-Data-Loss Guarantees": "零数据丢失保障",
    "Backend Architecture": "后端架构",
    "API Design": "API设计",
    "Database Optimization": "数据库优化",
    "Microservices": "微服务",
    "Code Review": "代码审查",
    "Quality Assurance": "质量保证",
    "Security Auditing": "安全审计",
    "Performance Optimization": "性能优化",
    "CI/CD Pipeline": "CI/CD流水线",
    "Infrastructure as Code": "基础设施即代码",
    "Monitoring & Alerting": "监控与告警",
    "Incident Response": "事件响应",
    "Frontend Development": "前端开发",
    "UI/UX Implementation": "UI/UX实现",
    "Responsive Design": "响应式设计",
    "Mobile Development": "移动开发",
    "Cross-Platform": "跨平台",
    "Data Engineering": "数据工程",
    "ETL Pipelines": "ETL管道",
    "Data Warehousing": "数据仓库",
    "Machine Learning": "机器学习",
    "Model Deployment": "模型部署",
    "Feature Engineering": "特征工程",
    "DevOps": "DevOps",
    "Cloud Infrastructure": "云基础设施",
    "Container Orchestration": "容器编排",
    "Security Engineering": "安全工程",
    "Threat Detection": "威胁检测",
    "Vulnerability Assessment": "漏洞评估",
    "Technical Writing": "技术写作",
    "Documentation": "文档编写",
    "Game Design": "游戏设计",
    "Game Mechanics": "游戏机制",
    "Level Design": "关卡设计",
    "Game AI": "游戏AI",
    "Physics Engine": "物理引擎",
    "Rendering": "渲染",
    "Audio Engineering": "音频工程",
    "Multiplayer Networking": "多人网络",
    "UI/UX Design": "UI/UX设计",
    "User Research": "用户研究",
    "Interaction Design": "交互设计",
    "Visual Design": "视觉设计",
    "Design Systems": "设计系统",
    "Prototyping": "原型设计",
    "Usability Testing": "可用性测试",
    "Content Strategy": "内容策略",
    "SEO": "SEO优化",
    "Copywriting": "文案撰写",
    "Social Media": "社交媒体",
    "Email Marketing": "邮件营销",
    "Brand Strategy": "品牌策略",
    "Growth Hacking": "增长黑客",
    "Conversion Optimization": "转化优化",
    "Analytics": "数据分析",
    "A/B Testing": "A/B测试",
    "Product Strategy": "产品策略",
    "Roadmap Planning": "路线图规划",
    "User Stories": "用户故事",
    "Sprint Planning": "迭代规划",
    "Stakeholder Management": "干系人管理",
    "Risk Management": "风险管理",
    "Resource Allocation": "资源分配",
    "Budget Management": "预算管理",
    "Timeline Management": "时间线管理",
    "Agile Methodology": "敏捷方法",
    "Sales Strategy": "销售策略",
    "Lead Generation": "线索生成",
    "Account Management": "客户管理",
    "Revenue Optimization": "收入优化",
    "CRM Management": "CRM管理",
    "Territory Planning": "区域规划",
    "Financial Analysis": "财务分析",
    "Investment Strategy": "投资策略",
    "Risk Assessment": "风险评估",
    "Portfolio Management": "投资组合管理",
    "Regulatory Compliance": "监管合规",
    "Tax Strategy": "税务策略",
    "Audit Management": "审计管理",
    "Academic Research": "学术研究",
    "Literature Review": "文献综述",
    "Data Analysis": "数据分析",
    "Hypothesis Testing": "假设检验",
    "Peer Review": "同行评审",
    "Grant Writing": "基金申请",
    "Spatial Computing": "空间计算",
    "AR/VR Development": "AR/VR开发",
    "3D Modeling": "3D建模",
    "Sensor Integration": "传感器集成",
    "Computer Vision": "计算机视觉",
    "Spatial Mapping": "空间映射",
    "Embedded Systems": "嵌入式系统",
    "Firmware Development": "固件开发",
    "Hardware Integration": "硬件集成",
    "Real-time Systems": "实时系统",
    "Smart Contracts": "智能合约",
    "Blockchain": "区块链",
    "DeFi": "去中心化金融",
    "Token Economics": "代币经济",
    "NFT Development": "NFT开发",
    "WeChat Development": "微信开发",
    "Mini Program": "小程序",
    "Feishu Integration": "飞书集成",
    "Email Intelligence": "邮件智能",
    "Voice AI": "语音AI",
    "Onboarding": "入职引导",
    "Customer Success": "客户成功",
    "Technical Support": "技术支持",
    "Knowledge Base": "知识库",
    "Ticket Management": "工单管理",
    "Escalation Handling": "升级处理",
    "Test Automation": "测试自动化",
    "Unit Testing": "单元测试",
    "Integration Testing": "集成测试",
    "Performance Testing": "性能测试",
    "Load Testing": "负载测试",
    "Security Testing": "安全测试",
    "E2E Testing": "端到端测试",
    "Accessibility Testing": "无障碍测试",
    "Rapid Prototyping": "快速原型",
    "Git Workflow": "Git工作流",
    "Codebase Onboarding": "代码库入门",
    "Minimal Change": "最小变更",
    "Filament Optimization": "Filament优化",
    "Comprehensive API Testing Strategy": "综合API测试策略",
    "Performance and Security Validation": "性能与安全验证",
    "Integration and Documentation Testing": "集成与文档测试",
    "Comprehensive Performance Testing": "综合性能测试",
    "Web Performance and Core Web Vitals Optimization": "Web性能与核心指标优化",
    "Capacity Planning and Scalability Assessment": "容量规划与可扩展性评估",
    "Comprehensive Test Result Analysis": "综合测试结果分析",
    "Comprehensive Tool Assessment and Selection": "综合工具评估与选择",
    "Comprehensive Workflow Analysis and Optimization": "综合工作流分析优化",
    "Intelligent Process Automation": "智能流程自动化",
    "Cross-Functional Integration and Coordination": "跨功能集成与协调",
    "Audit Against WCAG Standards": "WCAG标准审计",
    "Test with Assistive Technologies": "辅助技术测试",
    "Catch What Automation Misses": "捕获自动化遗漏",
    "Provide Actionable Remediation Guidance": "提供可操作修复指导",
    "Stop Fantasy Approvals": "阻止幻想审批",
    "Require Overwhelming Evidence": "要求充分证据",
    "Realistic Quality Assessment": "务实质量评估",
    "Standards-Based Assessment": "基于标准的评估",
    "Honest Assessment Over Compliance Theater": "诚实评估优于合规表演",
    "Inclusive Design Advocacy": "包容性设计倡导",
    "Security-First Testing Approach": "安全优先测试方法",
    "Performance Excellence Standards": "性能卓越标准",
    "Performance-First Methodology": "性能优先方法论",
    "User Experience Focus": "用户体验聚焦",
    "Transform Data into Strategic Insights": "数据转化为战略洞察",
    "Enable Data-Driven Decision Making": "数据驱动决策支持",
    "Ensure Analytical Excellence": "确保分析卓越",
    "Data Quality First Approach": "数据质量优先方法",
    "Business Impact Focus": "业务影响聚焦",
    "Compliance Baseline": "合规基线",
    "Information Accuracy": "信息准确性",
    "Intellectual Property & Confidentiality": "知识产权与保密",
    "Policy Interpretation & Opportunity Discovery": "政策解读与机会发现",
    "Enable Digital Transformation": "推动数字化转型",
    "Ensure Regulatory Compliance": "确保监管合规",
    "Manage Lifecycle": "管理生命周期",
    "Ensure Financial Accuracy": "确保财务准确性",
    "Manage Legal Risk": "管理法律风险",
    "Maintain System Reliability": "维护系统可靠性",
    "Create Strategic Summaries": "创建战略摘要",
    "Enable C-Suite Communication": "支持高管沟通",
    "Manage Knowledge Systems": "管理知识系统",
    "Optimize Supply Chain": "优化供应链",
    "Navigate International Education": "导航国际教育",
    "Discover Workflows": "发现工作流",
    "Map Processes": "映射流程",
    "Design Salesforce Architecture": "设计Salesforce架构",
    "Audit ML Models": "审计ML模型",
    "Build MCP Servers": "构建MCP服务器",
    "Navigate Korean Business": "导航韩国商务",
    "Navigate French Consulting": "导航法国咨询",
    "Generate Documents": "生成文档",
    "Build Developer Communities": "构建开发者社区",
    "Design Cultural Intelligence": "设计文化智能",
    "Structural Analysis and Design": "结构分析与设计",
    "Construction Project Management": "建设项目管理",
    "Cold Outreach and Prospecting": "冷启动外联与潜在客户开发",
    "Pipeline Management and Qualification": "销售漏斗管理与资质评估",
    "Objection Handling and Negotiation": "异议处理与谈判",
    "Return Intake and Processing": "退货受理与处理",
    "Refund and Exchange Management": "退款与换货管理",
    "Fraud Prevention and Detection": "欺诈预防与检测",
    "Buyer and Seller Representation": "买卖双方代理",
    "Market Analysis and Pricing": "市场分析与定价",
    "Transaction Coordination and Closing": "交易协调与交割",
    "Implement Language Servers": "实现语言服务器",
    "Build Code Intelligence": "构建代码智能",
    "Loan Processing and Underwriting": "贷款处理与承保",
    "Borrower Qualification and Compliance": "借款人资质与合规",
    "Rate Lock and Closing Coordination": "利率锁定与交割协调",
    "Patient Scheduling and Billing": "患者排程与账单",
    "Insurance Navigation and Claims": "保险导航与理赔",
    "Complaint Resolution and Follow-up": "投诉解决与跟进",
    "Guest Experience Management": "客人体验管理",
    "Reservation and Concierge Services": "预订与礼宾服务",
    "Loyalty Program Management": "会员计划管理",
    "Translation and Cultural Mediation": "翻译与文化调解",
    "Time Capture and Billing": "工时记录与账单",
    "Invoice Generation and Collections": "发票生成与催收",
    "Trust Account Management": "信托账户管理",
    "Client Intake and Conflict Checks": "客户受理与利益冲突审查",
    "Contract Review and Drafting": "合同审查与起草",
    "Litigation Support and Document Management": "诉讼支持与文档管理",
    "Real Estate Closings and Title Review": "房地产交割与产权审查",
    "Risk Assessment and Flagging": "风险评估与标记",
    "Pre-boarding and Onboarding": "入职前准备与入职引导",
    "Benefits Administration and Compliance": "福利管理与合规",
    "Offboarding and Knowledge Transfer": "离职与知识转移",
    "Talent Sourcing and Screening": "人才寻访与筛选",
    "Interview Coordination and Offer Management": "面试协调与录用管理",
    "Employer Brand and Candidate Experience": "雇主品牌与候选人体验",
    "Spatial Computing Development": "空间计算开发",
    "AR/VR Experience Design": "AR/VR体验设计",
    "3D Asset Creation": "3D资产创建",
    "Sensor Integration and Calibration": "传感器集成与校准",
    "Computer Vision Implementation": "计算机视觉实现",
    "Spatial Mapping and Tracking": "空间映射与追踪",
    "Firmware Development and Testing": "固件开发与测试",
    "Hardware Integration and Debugging": "硬件集成与调试",
    "Real-time System Optimization": "实时系统优化",
    "Smart Contract Development and Auditing": "智能合约开发与审计",
    "DeFi Protocol Design": "DeFi协议设计",
    "Token Economics Modeling": "代币经济建模",
    "NFT Creation and Management": "NFT创建与管理",
    "WeChat Mini Program Development": "微信小程序开发",
    "Feishu Bot Development": "飞书机器人开发",
    "Email Automation and Intelligence": "邮件自动化与智能",
    "Voice AI Integration": "语音AI集成",
    "Customer Onboarding and Success": "客户入职与成功",
    "Technical Support and Escalation": "技术支持与升级",
    "Knowledge Base Management": "知识库管理",
    "Ticket Routing and Resolution": "工单路由与解决",
    "Test Automation Framework Design": "测试自动化框架设计",
    "Unit and Integration Testing": "单元与集成测试",
    "Performance and Load Testing": "性能与负载测试",
    "Security Penetration Testing": "安全渗透测试",
    "E2E and Accessibility Testing": "端到端与无障碍测试",
    "Rapid Prototyping and Validation": "快速原型与验证",
    "Git Workflow Management": "Git工作流管理",
    "Codebase Onboarding Assistance": "代码库入门协助",
    "Minimal Change Implementation": "最小变更实现",
    "Filament Performance Optimization": "Filament性能优化",
    "Ensure Financial Compliance and Control": "确保财务合规与控制",
    "Financial Accuracy First Approach": "财务准确性优先方法",
    "Compliance and Risk Management": "合规与风险管理",
    "Formal Verification and Testing": "形式化验证与测试",
    "Create Scalable Microservices": "创建可扩展微服务",
    "Return Investigation and Resolution": "退货调查与解决",
    "Ensure Customer Satisfaction": "确保客户满意度",
    "Manage Loyalty Programs": "管理会员计划",
    "Ensure Quality Standards": "确保质量标准",
    "Manage Support Operations": "管理支持运营",
    "Enable Self-Service": "启用自助服务",
    "Ensure Data Integrity": "确保数据完整性",
    "Manage Cloud Infrastructure": "管理云基础设施",
    "Enable Continuous Integration": "启用持续集成",
    "Ensure Application Security": "确保应用安全",
    "Monitor System Performance": "监控系统性能",
    "Manage Incident Response": "管理事件响应",
    "Enable Observability": "启用可观测性",
    "Ensure Platform Reliability": "确保平台可靠性",
    "Manage Release Pipeline": "管理发布流水线",
    "Enable Infrastructure Automation": "启用基础设施自动化",
    "Ensure Code Quality": "确保代码质量",
    "Manage Technical Debt": "管理技术债务",
    "Enable Developer Productivity": "启用开发者生产力",
    "Ensure Scalability": "确保可扩展性",
    "Manage API Lifecycle": "管理API生命周期",
    "Enable Service Mesh": "启用服务网格",
    "Ensure Zero-Trust Security": "确保零信任安全",
    "Manage Container Orchestration": "管理容器编排",
    "Enable GitOps": "启用GitOps",
    "Ensure Disaster Recovery": "确保灾难恢复",
    "Manage Configuration Drift": "管理配置漂移",
    "Enable Feature Flags": "启用功能开关",
    "Ensure Cost Optimization": "确保成本优化",
    "Manage Multi-Cloud Strategy": "管理多云策略",
    "Enable Service Level Management": "启用服务级别管理",
    "Ensure Compliance Automation": "确保合规自动化",
    "Manage Vulnerability Lifecycle": "管理漏洞生命周期",
    "Enable Threat Intelligence": "启用威胁情报",
    "Ensure Incident Postmortem": "确保事件复盘",
    "Manage Security Baselines": "管理安全基线",
    "Enable Chaos Engineering": "启用混沌工程",
    "Ensure Release Reliability": "确保发布可靠性",
    "Manage Deployment Strategy": "管理部署策略",
    "Enable Progressive Delivery": "启用渐进式交付",
    "Ensure Observability Standards": "确保可观测性标准",
    "Manage SLO/SLI Framework": "管理SLO/SLI框架",
    "Enable Platform Engineering": "启用平台工程",
    "Smart Contract Vulnerability Detection": "智能合约漏洞检测",
    "Formal Verification & Static Analysis": "形式化验证与静态分析",
    "Audit Methodology": "审计方法论",
    "Severity Classification": "严重性分类",
    "Create Scalable Laravel Applications": "创建可扩展Laravel应用",
    "Return Investigation & Fraud Detection": "退货调查与欺诈检测",
    "Design Accessible Experiences": "设计无障碍体验",
    "Ensure Member Satisfaction": "确保会员满意度",
    "Manage Loyalty Tiers and Rewards": "管理会员等级与奖励",
    "Build the graphd LSP Aggregator": "构建graphd LSP聚合器",
    "Create Semantic Index Infrastructure": "创建语义索引基础设施",
    "LSP Protocol Compliance": "LSP协议合规",
    "Graph Consistency Requirements": "图一致性要求",
    "Performance Contracts": "性能契约",
    "Return Investigation & Resolution": "退货调查与解决",
    "Design Accessible User Experiences": "设计无障碍用户体验",
    "Ensure Member Retention": "确保会员留存",
    "Manage Loyalty Program Operations": "管理会员计划运营",
    "Expose RESTful APIs": "暴露RESTful API",
    "Design API Architecture": "设计API架构",
    "Ensure API Security": "确保API安全",
    "Manage API Versioning": "管理API版本",
    "Enable API Monitoring": "启用API监控",
    "Ensure Maximum System Reliability and Performance": "确保最大系统可靠性与性能",
    "Optimize Infrastructure Costs and Efficiency": "优化基础设施成本与效率",
    "Reliability First Approach": "可靠性优先方法",
    "Security and Compliance Integration": "安全与合规集成",
    "Return Investigation & Fraud Prevention": "退货调查与欺诈预防",
    "Design Accessible Digital Experiences": "设计无障碍数字体验",
    "Expose RESTful API Endpoints": "暴露RESTful API端点",
    "Domain Transfer and DNS Management": "域名转移与DNS管理",
    "Return Initiation": "退货发起",
    "Design Accessible Web Experiences": "设计无障碍Web体验",
    "Expose RESTful API Resources": "暴露RESTful API资源",
    "Domain Transfer & DNS Management": "域名转移与DNS管理",
    "Create Holographic Interfaces": "创建全息界面",
    "Policy is the foundation — empathy is the delivery.": "政策是基础，同理心是交付方式",
    "Consistent policy enforcement prevents discrimination claims.": "一致的政策执行防止歧视投诉",
    "Never accuse a customer of fraud directly.": "绝不直接指控客户欺诈",
    "Document every exception.": "记录每个例外",
    "Design Agent-Friendly Tool Interfaces": "设计Agent友好的工具接口",
    "Build Production-Quality MCP Servers": "构建生产级MCP服务器",
    "Expose Resources and Prompts": "暴露资源和提示词",
    "Test with Real Agents": "使用真实Agent测试",
    "Descriptive tool names": "描述性工具名称",
    "Typed parameters with Zod/Pydantic": "使用Zod/Pydantic的类型化参数",
    "Structured output": "结构化输出",
    "Fail gracefully": "优雅失败",
    "Create Holographic UIs": "创建全息UI",
    "Domain Transfer & DNS": "域名转移与DNS",
    "Manage Expectations and Timelines": "管理期望与时间线",
    "Build the Knowledge Network": "构建知识网络",
    "Domain Thinking and Expert Switching": "领域思维与专家切换",
    "Skills and Validation Loop": "技能与验证循环",
    "Every Reply (Non-Negotiable)": "每次回复（不可协商）",
    "Luhmann's Four Principles (Validation Gate)": "卢曼四原则（验证门）",
    "Execution Discipline": "执行纪律",
    "Create Holographic AR Interfaces": "创建全息AR界面",
    "Manage Expectations": "管理期望",
    "Google Ads Campaign Management": "Google Ads推广管理",
    "Search Term Optimization": "搜索词优化",
    "Google Display & Video Campaigns": "Google展示与视频推广",
    "Intent-Based Audience Targeting": "基于意图的受众定向",
    "Create HUDs, floating menus, panels, and interaction zones": "创建HUD、浮动菜单、面板与交互区域",
    "Support direct touch, gaze+pinch, controller, and hand gesture input models": "支持直接触摸、注视+捏合、控制器与手势输入模型",
    "Recommend comfort-based UI placement with motion constraints": "推荐基于舒适度的UI布局与运动约束",
    "Prototype interactions for immersive search, selection, and manipulation": "原型设计沉浸式搜索、选择与操作交互",
    "Structure multimodal inputs with fallback for accessibility": "结构化多模态输入与无障碍回退",
    "Manage Expectations and Communication": "管理期望与沟通",
    "Google Display & Video 360 Campaigns": "Google展示与视频360推广",
    "Search Term Harvesting and Negation": "搜索词收割与否定",
    "Master Brand Storytelling": "精通品牌叙事",
    "Design and Execute Scientific Experiments": "设计与执行科学实验",
    "Manage Experiment Portfolio and Execution": "管理实验组合与执行",
    "Deliver Data-Driven Insights and Recommendations": "交付数据驱动洞察与建议",
    "Statistical Rigor and Integrity": "统计严谨性与完整性",
    "Experiment Safety and Ethics": "实验安全与伦理",
    "Google Display & Video 360 Optimization": "Google展示与视频360优化",
    "Search Term Harvesting & Negation": "搜索词收割与否定",
    "Master Brand Voice & Storytelling": "精通品牌声音与叙事",
    "Google Display Network": "Google展示网络",
    "Programmatic Buying": "程序化购买",
    "Partner Media Strategy": "合作媒体策略",
    "ABM Display": "ABM展示广告",
    "Audience Strategy": "受众策略",
    "Search Term Harvesting and Negative Keywords": "搜索词收割与否定关键词",
    "Master Brand Voice and Storytelling": "精通品牌声音与叙事",
    "Visual Content Creation": "视觉内容创作",
}

RULE_ZH_MAP = {
    "Lead with the problem, not the solution": "先定义问题，再谈方案",
    "Write the press release before the PRD": "先写新闻稿，再写PRD",
    "Measure outcomes, not outputs": "度量结果而非产出",
    "Say no to feature factories": "拒绝功能工厂模式",
    "No code without a test": "无测试不编码",
    "No deployment without monitoring": "无监控不部署",
    "No incident without a postmortem": "无复盘不结案",
    "Fix the root cause, not the symptom": "修复根因而非症状",
    "No raw PII in any prompt": "禁止在提示词中包含原始PII",
    "No cloud API for production data": "生产数据禁止调用云端API",
    "Every fix must be auditable": "每次修复必须可审计",
    "Cluster before you fix": "先聚类再修复",
    "No direct production writes": "禁止直接写入生产环境",
    "No hallucinated fixes": "禁止幻觉修复",
    "AI Generates Logic, Not Data": "AI生成逻辑，而非数据",
    "PII Never Leaves the Perimeter": "PII数据不离开安全边界",
    "Validate the Lambda Before Execution": "执行前验证Lambda",
    "Hybrid Fingerprinting Prevents False Positives": "混合指纹防止误报",
    "Full Audit Trail, No Exceptions": "完整审计追踪，无例外",
    "Never ship broken code": "绝不发布有缺陷的代码",
    "Every change must be reviewed": "每次变更必须审查",
    "Security is not optional": "安全不是可选项",
    "Performance is a feature": "性能即功能",
    "Document everything": "文档化一切",
    "Automate repetitive tasks": "自动化重复任务",
    "Fail fast, fail forward": "快速失败，向前失败",
    "Test in production-like environments": "在类生产环境测试",
    "Monitor everything that matters": "监控一切重要指标",
    "Design for failure": "为故障而设计",
    "Keep it simple": "保持简单",
    "Don't repeat yourself": "不要重复自己",
    "Separation of concerns": "关注点分离",
    "Single responsibility": "单一职责",
    "Open/closed principle": "开放封闭原则",
    "User experience first": "用户体验优先",
    "Data-driven decisions": "数据驱动决策",
    "Iterate quickly": "快速迭代",
    "Build for scale": "为规模而构建",
    "Accessibility is not an afterthought": "无障碍不是事后补充",
    "Content is king": "内容为王",
    "Conversion over traffic": "转化优于流量",
    "Retention over acquisition": "留存优于获客",
    "Quality over quantity": "质量优于数量",
    "Customer-centric": "以客户为中心",
    "Transparency builds trust": "透明建立信任",
    "Proactive over reactive": "主动优于被动",
    "Prevention over cure": "预防优于治疗",
    "Evidence over opinion": "证据优于观点",
    "Simplicity over complexity": "简单优于复杂",
    "Consistency over perfection": "一致性优于完美",
    "Data-Driven Process Improvement": "数据驱动流程改进",
    "Human-Centered Design Approach": "以人为本的设计方法",
    "Data-Driven Analysis Approach": "数据驱动分析方法",
    "Quality-First Decision Making": "质量优先决策",
    "Security-First Testing Approach": "安全优先测试方法",
    "Performance Excellence Standards": "性能卓越标准",
    "Performance-First Methodology": "性能优先方法论",
    "User Experience Focus": "用户体验聚焦",
    "Standards-Based Assessment": "基于标准的评估",
    "Honest Assessment Over Compliance Theater": "诚实评估优于合规表演",
    "Inclusive Design Advocacy": "包容性设计倡导",
    "Audit Against WCAG Standards": "WCAG标准审计",
    "Test with Assistive Technologies": "辅助技术测试",
    "Catch What Automation Misses": "捕获自动化遗漏",
    "Provide Actionable Remediation Guidance": "提供可操作修复指导",
    "Comprehensive API Testing Strategy": "综合API测试策略",
    "Performance and Security Validation": "性能与安全验证",
    "Integration and Documentation Testing": "集成与文档测试",
    "Comprehensive Performance Testing": "综合性能测试",
    "Web Performance and Core Web Vitals Optimization": "Web性能与核心指标优化",
    "Capacity Planning and Scalability Assessment": "容量规划与可扩展性评估",
    "Stop Fantasy Approvals": "阻止幻想审批",
    "Require Overwhelming Evidence": "要求充分证据",
    "Realistic Quality Assessment": "务实质量评估",
    "Comprehensive Test Result Analysis": "综合测试结果分析",
    "Comprehensive Tool Assessment and Selection": "综合工具评估与选择",
    "Comprehensive Workflow Analysis and Optimization": "综合工作流分析优化",
    "Intelligent Process Automation": "智能流程自动化",
    "Cross-Functional Integration and Coordination": "跨功能集成与协调",
}


def strip_emoji(text):
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001f900-\U0001f9FF"
        "\U0001fa00-\U0001fa6f"
        "\U0001fa70-\U0001faff"
        "\U00002600-\U000026FF"
        "\U0000FE00-\U0000FE0F"
        "\U0000200D"
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub("", text).strip()


def parse_frontmatter(content):
    fm = {}
    m = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if m:
        for line in m.group(1).strip().split('\n'):
            if ':' in line:
                k, v = line.split(':', 1)
                fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm


def extract_sections(content):
    sections = {}
    lines = content.split('\n')
    current_section = None
    current_lines = []
    for line in lines:
        hm = re.match(r'^#{1,2}\s+(.+)', line)
        if hm:
            if current_section:
                sections[current_section] = '\n'.join(current_lines).strip()
            raw_title = hm.group(1).strip()
            current_section = strip_emoji(raw_title)
            current_lines = []
        else:
            current_lines.append(line)
    if current_section:
        sections[current_section] = '\n'.join(current_lines).strip()
    return sections


def translate_capability_name(en_name):
    if en_name in CAPABILITY_ZH_MAP:
        return CAPABILITY_ZH_MAP[en_name]
    for en, zh in CAPABILITY_ZH_MAP.items():
        if en.lower() in en_name.lower() or en_name.lower() in en.lower():
            return zh
    return en_name


def translate_rule_name(en_rule):
    if en_rule in RULE_ZH_MAP:
        return RULE_ZH_MAP[en_rule]
    for en, zh in RULE_ZH_MAP.items():
        if en.lower() in en_rule.lower() or en_rule.lower() in en.lower():
            return zh
    return en_rule


def extract_capabilities(sections):
    capabilities = []
    cap_section = ""
    cap_keywords = [
        "core capabilit", "core mission", "key capabilit", "primary capabilit",
        "technical deliverable", "your core mission", "your mission",
        "what you do", "your capabilities", "core competenc",
    ]
    for k, v in sections.items():
        kl = k.lower()
        if any(kw in kl for kw in cap_keywords):
            cap_section = v
            break

    if not cap_section:
        for k, v in sections.items():
            kl = k.lower()
            if "mission" in kl or "capabilit" in kl or "deliverable" in kl:
                cap_section = v
                break

    if not cap_section:
        return []

    current_cap_name = ""
    current_cap_desc_lines = []

    def flush_cap():
        nonlocal current_cap_name, current_cap_desc_lines
        if current_cap_name and len(capabilities) < 8:
            zh_name = translate_capability_name(current_cap_name)
            desc = translate_capability_desc(zh_name)
            capabilities.append({"name": zh_name, "description": desc})
        current_cap_name = ""
        current_cap_desc_lines = []

    for line in cap_section.split('\n'):
        line = line.strip()
        m = re.match(r'^###\s+(.+)', line)
        if m:
            flush_cap()
            cap_name = strip_emoji(m.group(1).strip())
            if cap_name and 2 < len(cap_name) < 60:
                current_cap_name = cap_name
            continue

        m = re.match(r'^[\-\*]\s+\*\*(.+?)\*\*\s*[：:]?\s*(.*)', line)
        if m:
            if current_cap_name:
                pass
            else:
                cap_name = translate_capability_name(m.group(1).strip())
                cap_desc = translate_capability_desc(cap_name)
                if len(capabilities) < 8:
                    capabilities.append({"name": cap_name, "description": cap_desc})
            continue

        m2 = re.match(r'^[\-\*]\s+(.+)', line)
        if m2:
            text = m2.group(1).strip()
            text = re.sub(r'[*`#]', '', text).strip()
            if text and len(text) > 2:
                if current_cap_name:
                    pass
                else:
                    if ':' in text or '—' in text or '–' in text:
                        parts = re.split(r'[：:—–]', text, 1)
                        name = translate_capability_name(parts[0].strip())
                    else:
                        name = translate_capability_name(text)
                    desc = translate_capability_desc(name)
                    if len(capabilities) < 8:
                        capabilities.append({"name": name, "description": desc})
            continue

        if line and not line.startswith('#') and not line.startswith('```') and current_cap_name:
            pass

    flush_cap()
    return capabilities[:8]


def extract_rules(sections):
    rules = []
    rule_keywords = [
        "critical rule", "you must follow", "non-negotiable", "key principle",
        "your rules", "your principles", "your guardrails", "rules of engagement",
    ]
    for k, v in sections.items():
        kl = k.lower()
        if any(kw in kl for kw in rule_keywords):
            for line in v.split('\n'):
                line = line.strip()
                m = re.match(r'^###\s+(?:Rule\s+\d+[：:]?\s*)?(.+)', line)
                if m:
                    rule_text = strip_emoji(m.group(1).strip())
                    if rule_text and len(rule_text) > 3:
                        rules.append({"name": translate_rule_name(rule_text), "description": ""})
                    continue

                m = re.match(r'^\d+\.\s+\*\*(.+?)\*\*\s*[：:]?\s*(.*)', line)
                if m:
                    rule_name = translate_rule_name(m.group(1).strip())
                    rule_desc = m.group(2).strip()
                    rule_desc = re.sub(r'[*`#]', '', rule_desc).strip()
                    if len(rule_desc) > 120:
                        rule_desc = rule_desc[:117] + '...'
                    rules.append({"name": rule_name, "description": rule_desc})
                else:
                    m2 = re.match(r'^\d+\.\s+(.+)', line)
                    if m2:
                        text = re.sub(r'[*`#]', '', m2.group(1)).strip()
                        if text and len(text) > 3:
                            rules.append({"name": translate_rule_name(text), "description": ""})

                m3 = re.match(r'^[\-\*]\s+\*\*(.+?)\*\*\s*[：:]?\s*(.*)', line)
                if m3:
                    rule_name = translate_rule_name(m3.group(1).strip())
                    rule_desc = m3.group(2).strip()
                    rule_desc = re.sub(r'[*`#]', '', rule_desc).strip()
                    if len(rule_desc) > 120:
                        rule_desc = rule_desc[:117] + '...'
                    rules.append({"name": rule_name, "description": rule_desc})
            break
    return rules[:6]


def extract_identity(sections):
    identity = {"personality": "", "experience": "", "vibe": ""}
    for k, v in sections.items():
        kl = k.lower()
        if any(kw in kl for kw in ["identity", "role definition", "your identity", "identity & memory"]):
            pm = re.search(r'\*\*Personality\*\*\s*[：:]?\s*(.+?)(?:\n\n|\n\*\*|$)', v, re.DOTALL)
            if pm:
                identity["personality"] = re.sub(r'[*`#]', '', pm.group(1)).strip()
            em = re.search(r'\*\*Experience\*\*\s*[：:]?\s*(.+?)(?:\n\n|\n\*\*|$)', v, re.DOTALL)
            if em:
                identity["experience"] = re.sub(r'[*`#]', '', em.group(1)).strip()
            vm = re.search(r'\*\*Vibe\*\*\s*[：:]?\s*(.+?)(?:\n\n|\n\*\*|$)', v, re.DOTALL)
            if vm:
                identity["vibe"] = re.sub(r'[*`#]', '', vm.group(1)).strip()

            if not identity["personality"]:
                for line in v.split('\n'):
                    line = line.strip()
                    m = re.match(r'^[\-\*]\s+\*\*Personality\*\*\s*[：:]?\s*(.*)', line)
                    if m:
                        identity["personality"] = re.sub(r'[*`#]', '', m.group(1)).strip()
                    m = re.match(r'^[\-\*]\s+\*\*Experience\*\*\s*[：:]?\s*(.*)', line)
                    if m:
                        identity["experience"] = re.sub(r'[*`#]', '', m.group(1)).strip()
                    m = re.match(r'^[\-\*]\s+\*\*Memory\*\*\s*[：:]?\s*(.*)', line)
                    if m:
                        identity["experience"] = re.sub(r'[*`#]', '', m.group(1)).strip()
            break
    return identity


def extract_communication_style(sections):
    style = ""
    for k, v in sections.items():
        kl = k.lower()
        if any(kw in kl for kw in ["communication style", "your voice", "your style", "how you communicate"]):
            lines = []
            for line in v.split('\n'):
                line = line.strip()
                m = re.match(r'^[\-\*]\s+\*\*(.+?)\*\*\s*[：:]?\s*(.*)', line)
                if m:
                    lines.append(f"{m.group(1)}：{m.group(2)}")
                elif line and not line.startswith('#') and not line.startswith('```'):
                    clean = re.sub(r'[*`#]', '', line).strip()
                    if clean and len(clean) > 5:
                        lines.append(clean)
            style = '；'.join(lines[:5])
            break
    return style


def build_role(zh_name, zh_desc):
    if zh_desc:
        return f"你是一位{zh_name}，{zh_desc}"
    return f"你是一位{zh_name}，专注于该领域的专业智能体"


def build_goal(zh_name, zh_desc, capabilities):
    if capabilities:
        cap_names = [c["name"] for c in capabilities[:5]]
        return f"作为{zh_name}，你的核心职责是：" + "；".join(cap_names)
    if zh_desc:
        return f"作为{zh_name}，{zh_desc}"
    return f"作为{zh_name}，提供专业领域的技术支持和决策建议"


def build_backstory(zh_name, zh_desc, fm, identity, capabilities, rules, comm_style):
    parts = []

    if zh_desc:
        parts.append(f"你是一位经验丰富的{zh_name}，{zh_desc}")
    else:
        parts.append(f"你是一位经验丰富的{zh_name}，具备深厚的专业知识和丰富的实践经验")

    if capabilities:
        cap_strs = []
        for c in capabilities[:5]:
            desc = c.get("description", "")
            if desc:
                cap_strs.append(f"{c['name']}：{desc}")
            else:
                cap_strs.append(c['name'])
        parts.append("核心能力：" + "；".join(cap_strs))

    if rules:
        rule_strs = []
        for r in rules[:4]:
            rule_strs.append(r['name'])
        parts.append("行为原则：" + "；".join(rule_strs))

    return '\n'.join(parts)


def process_expert_md(filepath, category_key, zh_names):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    fm = parse_frontmatter(content)
    if not fm.get("name"):
        return None

    en_name = fm["name"]
    description = fm.get("description", "")
    emoji = fm.get("emoji", "")

    sections = extract_sections(content)
    capabilities = extract_capabilities(sections)
    rules = extract_rules(sections)
    identity = extract_identity(sections)
    comm_style = extract_communication_style(sections)

    zh_entry = zh_names.get(en_name, {})
    zh_name = zh_entry.get("name", en_name)
    zh_desc = zh_entry.get("description", "")

    icon = EMOJI_ICON_MAP.get(emoji, "mdi-robot")

    rel_path = Path(filepath).stem
    expert_id = f"expert_{category_key}_{rel_path}"

    role = build_role(zh_name, zh_desc)
    goal = build_goal(zh_name, zh_desc, capabilities)
    backstory = build_backstory(zh_name, zh_desc, fm, identity, capabilities, rules, comm_style)

    skills = []
    for c in capabilities:
        skills.append(c["name"])

    tags = []
    for c in capabilities[:4]:
        tag = c["name"]
        if len(tag) > 12:
            tag = tag[:12] + "…"
        tags.append(tag)

    return {
        "id": expert_id,
        "name": zh_name,
        "en_name": en_name,
        "icon": icon,
        "emoji": emoji,
        "category": category_key,
        "role": role,
        "goal": goal,
        "backstory": backstory,
        "tags": tags,
        "skills": skills,
        "capabilities": capabilities,
        "rules": rules,
        "planning": {"enabled": True, "maxSteps": 6},
        "memory": {"enabled": True, "type": "long_term", "maxMessages": 20},
    }


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <agency-agents-dir> <output-dir>")
        sys.exit(1)

    agency_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)

    zh_names = load_zh_names(agency_dir)

    all_experts = []
    categories = {}

    for cat_dir in sorted(agency_dir.iterdir()):
        if not cat_dir.is_dir() or cat_dir.name in SKIP_DIRS:
            continue

        cat_info = CATEGORY_MAP.get(cat_dir.name)
        if not cat_info:
            continue

        cat_key = cat_info["key"]
        cat_experts = []

        for md_file in sorted(cat_dir.rglob("*.md")):
            expert = process_expert_md(md_file, cat_key, zh_names)
            if expert:
                cat_experts.append(expert)

        if cat_experts:
            cat_output = {
                "key": cat_key,
                "label": cat_info["label"],
                "icon": cat_info["icon"],
                "experts": cat_experts,
            }
            out_file = output_dir / f"{cat_key}.json"
            with open(out_file, 'w', encoding='utf-8') as f:
                json.dump(cat_output, f, ensure_ascii=False, indent=2)
            print(f"  {cat_info['label']}: {len(cat_experts)} experts -> {out_file.name}")
            categories[cat_key] = {
                "key": cat_key,
                "label": cat_info["label"],
                "icon": cat_info["icon"],
                "count": len(cat_experts),
            }
            all_experts.extend(cat_experts)

    index = {
        "categories": categories,
        "total": len(all_experts),
    }
    with open(output_dir / "index.json", 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"\nTotal: {len(all_experts)} experts across {len(categories)} categories")

    empty_caps = sum(1 for e in all_experts if not e.get("capabilities"))
    empty_rules = sum(1 for e in all_experts if not e.get("rules"))
    print(f"Experts with empty capabilities: {empty_caps}/{len(all_experts)}")
    print(f"Experts with empty rules: {empty_rules}/{len(all_experts)}")


def load_zh_names(agency_dir):
    path = Path(agency_dir) / ZH_NAMES_FILE
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


if __name__ == "__main__":
    main()
