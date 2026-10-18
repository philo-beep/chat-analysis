"""Shared schema, domain rules, entity extraction, and pure-Python model helpers."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "models" / "char_ngram_nb.json"
MAX_INPUT_CHARS = 6000
MAX_DIALOGUE_CHARS = 50000
FIELDS = ("需求", "待确认问题", "建议待办", "回复草稿")
EMPTY_RESULT = {
    "需求": "",
    "待确认问题": [],
    "建议待办": [],
    "回复草稿": "",
}

# Intent ids are stable training labels. Outputs are deliberately reviewed templates.
INTENTS: dict[str, dict[str, Any]] = {
    "price": {
        "需求": "询问产品价格并希望了解优惠",
        "待确认问题": ["预算范围", "预计采购数量"],
        "建议待办": ["根据数量核算报价", "确认是否适用批量优惠", "发送正式报价单"],
        "回复草稿": "您好，价格会根据产品规格和采购数量核算。方便告知您的预算范围和预计采购数量吗？我确认后尽快为您整理报价。",
    },
    "purchase": {
        "需求": "表达了采购意向，准备进一步下单",
        "待确认问题": ["产品规格与数量", "收货地址", "期望到货时间"],
        "建议待办": ["确认订单规格和数量", "核实库存及交期", "整理下单信息"],
        "回复草稿": "您好，感谢您的咨询。请问您确认的产品规格、数量和收货地区是什么？我先帮您核实库存与预计交期。",
    },
    "auto_sales": {
        "需求": "汽车/车辆选购意向",
        "待确认问题": ["预算范围", "主要用车场景", "偏好车型、能源和配置", "计划购车时间"],
        "建议待办": ["按预算和场景筛选车型", "核对配置、报价、库存和优惠", "确认试驾及购车流程"],
        "回复草稿": "您好，可以帮您筛选合适的车型。请告知购车预算、主要用车场景、车型或配置偏好以及计划购车时间。",
    },
    "software_sales": {
        "需求": "咨询企业软件、SaaS订阅或系统部署",
        "待确认问题": ["企业规模与使用人数", "需要解决的业务场景", "所需功能或集成", "预算和上线时间"],
        "建议待办": ["梳理业务流程与功能需求", "匹配软件版本、许可和部署方案", "安排演示并提供报价"],
        "回复草稿": "您好，可以为您介绍合适的软件方案。请告知企业规模、使用场景、需要的功能或系统集成、预算及计划上线时间。",
    },
    "product_info": {
        "需求": "咨询产品功能、规格或适用场景",
        "待确认问题": ["具体使用场景", "关注的规格参数", "计划采购数量"],
        "建议待办": ["发送产品参数资料", "按使用场景推荐型号"],
        "回复草稿": "您好，可以为您介绍。方便说一下主要使用场景，以及您最关注的规格或功能吗？我会据此整理合适的产品资料。",
    },
    "customization": {
        "需求": "咨询定制、打样或个性化方案",
        "待确认问题": ["定制内容与尺寸", "预计数量", "期望交付时间"],
        "建议待办": ["收集定制要求", "评估打样与生产周期", "确认定制报价"],
        "回复草稿": "您好，我们可以先评估定制可行性。请问需要调整的内容、尺寸或工艺是什么，预计数量和希望交付时间大概是怎样的？",
    },
    "logistics": {
        "需求": "咨询发货、配送范围或物流进度",
        "待确认问题": ["收货地区", "订单编号或下单时间", "期望到货时间"],
        "建议待办": ["核实配送范围与运费", "查询物流或预计发货时间", "回复配送安排"],
        "回复草稿": "您好，我来帮您核实配送安排。麻烦提供收货地区；如果是查询已有订单，也请发一下订单编号或下单时间。",
    },
    "after_sales": {
        "需求": "反馈产品使用、质量或售后问题",
        "待确认问题": ["产品型号", "问题现象及发生时间", "订单编号"],
        "建议待办": ["收集问题描述与照片", "核对订单和质保信息", "安排技术或售后跟进"],
        "回复草稿": "您好，很抱歉给您带来不便，我们会尽快协助处理。请提供产品型号、订单编号和问题现象；如方便，也请附上照片或视频。",
    },
    "wholesale": {
        "需求": "咨询批发、代理或长期供货合作",
        "待确认问题": ["预计月采购量", "经营地区", "合作类型"],
        "建议待办": ["了解经营资质与渠道", "核算阶梯价格", "整理合作政策"],
        "回复草稿": "您好，感谢您关注合作。方便介绍一下经营地区、销售渠道和预计月采购量吗？我会根据情况为您整理对应的供货及合作政策。",
    },
    "sample": {
        "需求": "希望申请样品或先行试用",
        "待确认问题": ["意向产品与规格", "样品数量", "收件地区"],
        "建议待办": ["确认样品库存", "核实样品费用与运费", "登记寄送信息"],
        "回复草稿": "您好，可以先确认样品安排。请问您想了解的产品规格和样品数量是什么，收件地区在哪里？我核实库存及相关费用后回复您。",
    },
    "payment_invoice": {
        "需求": "咨询付款方式、账期或发票事宜",
        "待确认问题": ["对应订单或采购金额", "发票类型", "开票抬头及税号（如需开票）"],
        "建议待办": ["核实可用付款方式", "确认账期条件", "收集开票资料"],
        "回复草稿": "您好，我可以帮您确认付款和开票安排。请问对应的订单或采购金额是多少？如需开票，也请告知发票类型和开票信息。",
    },
    "dining": {
        "需求": "餐饮/用餐需求",
        "待确认问题": ["用餐地点或餐厅类型", "用餐人数", "用餐时间", "菜系或口味偏好", "预算范围"],
        "建议待办": ["确认用餐条件", "按地点、人数和口味筛选餐厅", "核实营业时间和订位情况"],
        "回复草稿": "您好，可以帮您安排用餐。请补充用餐地点、人数、时间、菜系或口味偏好以及预算，我再为您筛选合适的餐厅。",
    },
    "attraction_ticket": {
        "需求": "咨询景区、门票或预约安排",
        "待确认问题": ["景区或目的地", "参观日期", "人数", "门票或预约类型"],
        "建议待办": ["核实开放时间和预约规则", "确认票种与余票", "整理入园安排"],
        "回复草稿": "您好，我可以帮您核实景区安排。请告知景区名称、参观日期、人数以及需要的票种或预约类型。",
    },
    "hotel": {
        "需求": "咨询酒店、住宿或房型安排",
        "待确认问题": ["住宿地点", "入住和退房日期", "入住人数", "房型和预算"],
        "建议待办": ["按地点和日期查询房态", "比较房型与价格", "确认入住政策"],
        "回复草稿": "您好，可以帮您筛选住宿。请补充住宿地点、入住和退房日期、人数、房型偏好及预算，我再核实房态。",
    },
    "transport": {
        "需求": "咨询交通、车票、接送或出行路线",
        "待确认问题": ["出发地和目的地", "出行日期", "人数", "交通方式或车型"],
        "建议待办": ["确认路线和出行条件", "查询车票或车辆安排", "整理交通方案和费用"],
        "回复草稿": "您好，可以帮您安排交通。请告知出发地、目的地、日期、人数以及偏好的交通方式或车型。",
    },
    "travel": {
        "需求": "有旅游、出行或游玩意向，需要进一步规划行程",
        "待确认问题": ["目的地或游玩区域", "出行人数", "出行时间", "预算范围", "游玩偏好和交通方式"],
        "建议待办": ["确认行程细节", "根据人数、时间和偏好推荐路线", "整理并发送行程方案"],
        "回复草稿": "您好，当然可以帮您规划出行。请告诉我目的地或想去的区域、出行人数、时间、预算和游玩偏好，我再为您推荐合适的路线和方案。",
    },
    "service_consult": {
        "需求": "咨询可提供的服务内容与安排",
        "待确认问题": ["需要的服务类型", "服务地点和时间", "人数或规模", "预算范围"],
        "建议待办": ["确认服务需求和执行条件", "匹配可行服务方案", "整理并发送服务说明"],
        "回复草稿": "您好，可以先帮您了解。请问您需要哪类服务、在哪个地点和时间使用，人数或规模以及预算大概是多少？我再为您匹配合适的方案。",
    },
    "vague": {
        "需求": "有初步咨询意向，但尚未说明具体产品或需求",
        "待确认问题": ["关注的产品或服务", "使用场景", "预算或时间计划"],
        "建议待办": ["进一步了解客户场景", "根据客户关注点整理初步方案"],
        "回复草稿": "您好，没问题，我可以先帮您梳理。您目前主要想了解哪类产品或服务，计划用于什么场景？有预算或时间要求也可以一并告诉我。",
    },
    "no_intent": {
        "需求": "",
        "待确认问题": [],
        "建议待办": [],
        "回复草稿": "",
    },
}

DOMAIN_BY_INTENT = {
    "price": "product_sales",
    "purchase": "product_sales",
    "auto_sales": "auto_sales",
    "software_sales": "software_sales",
    "product_info": "product_sales",
    "customization": "product_sales",
    "wholesale": "product_sales",
    "sample": "product_sales",
    "logistics": "logistics",
    "after_sales": "after_sales",
    "payment_invoice": "payment_invoice",
    "dining": "dining",
    "attraction_ticket": "attraction_ticket",
    "hotel": "hotel",
    "transport": "transport",
    "travel": "travel",
    "service_consult": "service_consult",
    "vague": "vague",
    "no_intent": "no_intent",
}
NEED_TO_INTENT = {value["需求"]: key for key, value in INTENTS.items()}

# General words such as "我想" and "两个人" intentionally do not appear in a
# strong domain list. They are useful only in combination with an object or action.
KEYWORD_CUES: dict[str, tuple[str, ...]] = {
    "price": ("多少钱", "价格", "报价", "单价", "优惠", "折扣", "便宜", "价位", "阶梯价", "核价", "报价单"),
    "purchase": ("下单", "订购", "订单", "留货", "给我留", "锁定", "采购一批", "确定采购", "想买", "我要买", "准备买", "买一辆", "要买", "购买", "有库存", "现货"),
    "product_info": ("功能", "参数", "尺寸", "规格", "型号", "车型", "车款", "说明书", "兼容", "适合", "使用方法", "保修期", "材料", "材质", "防水", "批量导入", "数据备份", "处理多少", "多少单"),
    "auto_sales": ("汽车", "车型", "车款", "SUV", "轿车", "新能源车", "电动车", "混动车", "商务车", "用车", "家用车", "二手车", "代步车", "空间大的车", "试驾", "续航", "购车"),
    "software_sales": ("软件", "SaaS", "系统", "ERP", "CRM", "进销存", "POS", "订阅", "部署", "接口", "系统集成", "产品演示", "账号"),
    "customization": ("定制", "logo", "印我们", "打样", "打个样", "特殊尺寸", "品牌色", "二维码", "模具", "工艺", "改造", "按图纸"),
    "logistics": ("发货", "出库", "配送", "物流", "运费", "到货", "派送", "快递", "寄到", "送到", "收货地址", "订单已发", "订单已经发", "几天能到", "能到", "查物流", "物流进度", "最早收到", "最早什么时候可以收到"),
    "after_sales": ("故障", "开不了", "维修", "破损", "退换", "退货和换货", "少发", "数量不对", "缺件", "噪音", "报修", "售后", "质量问题", "异味", "漏液", "质保", "报错", "无法连接", "补发"),
    "wholesale": ("代理", "经销", "批发", "长期供货", "供货", "合作", "月采购", "经销商", "区域保护", "渠道"),
    "sample": ("样品", "寄样", "试用", "试用装", "小样", "体验", "样板", "样品费"),
    "payment_invoice": ("微信", "支付宝", "信用卡", "银行卡", "转账", "账期", "发票", "开票", "对公", "付款方式", "付款", "怎么支付", "月结", "税号", "专票", "货后款"),
    "dining": ("吃饭", "想吃", "吃海鲜", "用餐", "餐厅", "餐馆", "饭店", "订位", "订座", "菜系", "口味", "川菜", "粤菜", "湘菜", "日料", "韩餐", "火锅", "烧烤", "海鲜", "自助餐", "外卖", "团餐", "宴会", "堂食"),
    "attraction_ticket": ("门票", "儿童票", "学生票", "老人票", "景区预约", "入园", "开放时间", "开放日期", "余票", "预约参观", "景区"),
    "hotel": ("酒店", "住宿", "订房", "房间", "入住", "退房", "房型", "宾馆", "民宿", "想住", "住一晚", "住两晚", "住三晚", "大床房", "双床房", "亲子房"),
    "transport": ("包车", "车票", "高铁", "火车票", "交通路线", "机场接送", "机场到", "商务用车接送", "接送", "打车", "租车", "租一辆车", "车辆", "地铁", "公交", "直达车", "车次"),
    "travel": ("旅游", "旅行", "出游", "游玩", "出去玩", "去玩", "一日游", "周末游", "行程", "路线", "景点", "景点顺序", "美食游", "度假", "跟团", "自由行", "想去玩", "短途游", "爬山", "自然风景", "亲子游", "团建出游"),
    "service_consult": ("导游", "预订", "预约", "安排服务", "咨询服务", "服务内容", "执行服务", "活动策划", "活动要策划", "摄影跟拍", "讲解员", "培训", "场地"),
    "vague": ("没确定", "还没想好", "不太明确", "做规划", "推荐", "想了解一下", "想了解", "先了解", "想找", "想做个", "新项目", "方案", "门店运营", "介绍", "咨询一下", "想咨询"),
    "no_intent": ("谢谢", "收到", "嗯嗯", "暂时不用", "再见", "回头聊", "晚点再联系", "知道了", "先这样", "没有其他问题", "你好"),
}
STRONG_DOMAIN_ORDER = (
    "dining", "after_sales", "customization", "attraction_ticket", "transport", "hotel", "auto_sales", "software_sales", "sample", "logistics",
    "payment_invoice", "wholesale", "purchase", "price", "travel", "product_info", "service_consult",
)
TRAVEL_TIME_CUES = (
    "下周末", "本周末", "这个周末", "周末", "下周", "本周", "下个月", "本月",
    "明天", "后天", "今天", "周六", "周日", "星期六", "星期日", "暑假", "寒假",
    "国庆", "五一", "春节",
)
TRAVEL_PREFERENCE_CUES = ("自然风光", "历史文化", "人文", "美食", "亲子", "轻松", "徒步", "爬山", "打卡", "拍照", "博物馆", "校园", "看风景", "不赶行程")
TRAVEL_GENERIC_DESTINATIONS = ("旅游", "旅行", "出游", "游玩", "玩", "景点", "目的地", "地方", "周边", "附近")
TRAVEL_DESTINATION_STOPWORDS = ("但是", "不过", "还没", "没有", "暂时", "先帮", "想想")
UNKNOWN_NO_INTENT_CUES = ("去医院", "上班", "看电影", "日常安排", "不是旅游", "不是出游", "客户问我", "客服正在询问", "这不是我的出行信息", "先记录一下")
DINING_CUISINES = ("川菜", "粤菜", "湘菜", "淮扬菜", "本帮菜", "日料", "韩餐", "西餐", "火锅", "烧烤", "素食", "海鲜", "自助餐")
DINING_TYPES = ("餐厅", "餐馆", "饭店", "咖啡馆", "茶餐厅", "酒楼", "小吃店", "团餐", "宴会")
MEANINGFUL_CHAR_RE = re.compile(r"[A-Za-z0-9\u3400-\u9fff]")
ROLE_PATTERN = re.compile(r"^\s*(客户(?:\d+)?|顾客|用户|客人|客服人员|客服|商家|销售|导游)\s*[:：]\s*(.*)$")


def domain_for_intent(intent: str | None) -> str:
    return DOMAIN_BY_INTENT.get(intent or "", "unknown")


def parse_dialogue(text: str) -> dict[str, Any]:
    """Parse roles and attach each customer turn to the preceding agent question."""
    records: list[dict[str, Any]] = []
    preamble: list[str] = []
    for line in str(text).splitlines():
        match = ROLE_PATTERN.match(line)
        if match:
            role, body = match.group(1), match.group(2).strip()
            normalized_role = "customer" if role.startswith(("客户", "顾客", "用户", "客人")) else "agent"
            records.append({"role": normalized_role, "text": body})
        elif line.strip():
            if records:
                records[-1]["text"] = (records[-1]["text"] + " " + line.strip()).strip()
            else:
                preamble.append(line.strip())
    if preamble:
        records.insert(0, {"role": "customer", "text": " ".join(preamble)})
    if not records:
        content = str(text).strip()
        records = [{"role": "customer", "text": content}] if content else []
    customers: list[str] = []
    agents: list[str] = []
    customer_turns: list[dict[str, Any]] = []
    preceding_agent = ""
    for turn_index, record in enumerate(records):
        record["turn_index"] = turn_index
        if record["role"] == "agent":
            agents.append(record["text"])
            preceding_agent = record["text"]
        elif record["text"]:
            customers.append(record["text"])
            record["preceding_agent"] = preceding_agent
            customer_turns.append({
                "turn_index": turn_index,
                "text": record["text"],
                "preceding_agent": preceding_agent,
            })
    return {
        "customer_messages": customers,
        "agent_messages": agents,
        "customer_turns": customer_turns,
        "turns": records,
        "is_dialogue": len(records) > 1,
        "recent_customer_message": customers[-1] if customers else "",
    }


def _agent_question_slots(agent_text: str) -> set[str]:
    text = agent_text.lower()
    slots: set[str] = set()
    if re.search(r"支付|付款|信用卡|银行卡|转账|微信|支付宝", text):
        slots.add("payment_method")
    if re.search(r"车型|车款|型号|产品|规格|功能", text):
        slots.add("product")
    if re.search(r"几个人|几位|人数|多少人", text):
        slots.add("people")
    if re.search(r"预算|多少钱|价格|价位", text):
        slots.add("budget")
    if re.search(r"什么时候|哪天|日期|时间|几月|周几", text):
        slots.add("time")
    if re.search(r"地址|收货|寄到|发到", text):
        slots.add("address")
    if re.search(r"还有什么需求|具体需求|需要什么", text):
        slots.add("need")
    return slots


def _looks_like_slot_answer(message: str, preceding_agent: str) -> bool:
    """A short answer to an agent question is context, not a new intent."""
    text = message.strip().lower()
    slots = _agent_question_slots(preceding_agent)
    if not slots or "need" in slots:
        return False
    has_action = bool(re.search(r"想|要|需要|请|买|订|购|咨询|了解|推荐|安排|规划|反馈|报修|申请|找", text))
    if "payment_method" in slots and re.fullmatch(r"(?:信用卡|银行卡|借记卡|微信|支付宝|现金|转账|对公转账|分期|月结|货到付款)[。！!？?]??", text):
        return True
    if not has_action and len(text) <= 24:
        return True
    return False


def _primary_customer_messages(parsed: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]], list[str]]:
    primary: list[str] = []
    slot_answers: list[dict[str, Any]] = []
    for turn in parsed.get("customer_turns", []):
        message = turn["text"].strip()
        preceding_agent = turn.get("preceding_agent", "")
        if _looks_like_slot_answer(message, preceding_agent):
            slot_answers.append({
                "text": message,
                "preceding_agent": preceding_agent,
                "slots": sorted(_agent_question_slots(preceding_agent)),
            })
            continue
        if message in {"你好", "您好", "嗯", "嗯嗯", "好的", "收到", "谢谢"} and len(parsed.get("customer_turns", [])) > 1:
            continue
        primary.append(message)
    if not primary and parsed.get("customer_messages"):
        primary = [parsed["customer_messages"][-1]]
    primary_text = "\n".join(primary)
    has_concrete_signal = any(_cue_hits(primary_text, intent) for intent in STRONG_DOMAIN_ORDER) or _has_travel_evidence(primary_text)
    model_messages = list(primary)
    if slot_answers and not has_concrete_signal:
        model_messages.extend(item["text"] for item in slot_answers)
    return primary, slot_answers, model_messages


def customer_text_views(text: str, dialogue: dict[str, Any] | None = None) -> dict[str, Any]:
    parsed = dialogue or parse_dialogue(text)
    customers = parsed["customer_messages"]
    combined = "\n".join(customers).strip()
    primary, slot_answers, model_messages = _primary_customer_messages(parsed)
    model_text = "\n".join(model_messages).strip()
    if parsed["is_dialogue"] and len(combined) > MAX_DIALOGUE_CHARS:
        combined = (combined[:5000] + "\n" + combined[-(MAX_DIALOGUE_CHARS - 5000):]).strip()
    elif not parsed["is_dialogue"] and len(combined) > MAX_INPUT_CHARS:
        combined = combined[:MAX_INPUT_CHARS].rstrip()
    return {
        "full": combined,
        "model": model_text or combined,
        "recent": parsed.get("recent_customer_message", ""),
        "summary": "；".join(customers),
        "primary_messages": primary,
        "model_messages": model_messages,
        "slot_answers": slot_answers,
    }


def customer_text_for_model(text: str, dialogue: dict[str, Any] | None = None) -> str:
    return customer_text_views(text, dialogue)["model"]


def _clean_candidate(value: str) -> str:
    candidate = value.strip().strip("，。！？、：；,.!?;:()（）[]【】")
    candidate = re.sub(r"^(?:我想|我们想|计划|准备|想要|希望|打算)\s*", "", candidate)
    candidate = re.sub(r"(?:一日游|两日游|三日游|[一二两三四五六七八九十\d]+天)$", "", candidate)
    if any(candidate.startswith(word) for word in TRAVEL_GENERIC_DESTINATIONS):
        return ""
    if any(word in candidate for word in TRAVEL_DESTINATION_STOPWORDS) or "主要是" in candidate:
        stopwords = TRAVEL_DESTINATION_STOPWORDS + ("主要是",)
        candidate = re.split("|".join(map(re.escape, stopwords)), candidate, maxsplit=1)[0]
    if candidate.endswith("目的地") or candidate in {"", "出去", "那里", "哪里", "附近", "周边", "地方", "餐厅", "饭店", "吃饭", "用餐"}:
        return ""
    return candidate.rsplit("的", 1)[-1].strip()


def extract_entities(text: str, dialogue: dict[str, Any] | None = None) -> dict[str, str]:
    """Extract customer facts while using agent questions only as slot context."""
    parsed = dialogue or parse_dialogue(text)
    customer_text = "\n".join(parsed["customer_messages"])
    entities: dict[str, str] = {}
    destination_match = re.search(
        r"(?:去|到|前往|抵达|在)\s*([\u3400-\u9fffA-Za-z0-9]{2,18}?)(?=(?:的一日游|一日游|两日游|三日游|旅游|旅行|出游|游玩|玩|参观|打卡|吃饭|用餐|逛|$|[，。！？、\s]))",
        customer_text,
    )
    if destination_match:
        value = _clean_candidate(destination_match.group(1))
        if value:
            entities["目的地"] = value
    origin_match = re.search(r"(?:从|由)\s*([\u3400-\u9fffA-Za-z0-9]{2,12}?)(?:出发|出发前往|出发去)", customer_text)
    if origin_match:
        value = _clean_candidate(origin_match.group(1))
        if value:
            entities["出发地"] = value
    location_match = re.search(r"(?:发到|寄到|送到|收货在|住宿在|住在|用餐在)\s*([\u3400-\u9fffA-Za-z0-9]{2,18})", customer_text)
    if location_match:
        value = _clean_candidate(location_match.group(1))
        if value:
            entities["地点"] = value
    people_match = re.search(r"(?<!\d)(\d{1,3}|[一二两三四五六七八九十几]+)\s*(?:个)?\s*(?:人|位)", customer_text)
    if people_match:
        entities["人数"] = f"{people_match.group(1).replace('两', '2')}人"
    else:
        family_match = re.search(r"一家([一二两三四五六七八九十\d]+)口", customer_text)
        if family_match:
            entities["人数"] = f"{family_match.group(1).replace('两', '2')}人"
    time_match = re.search(r"\d{1,4}\s*年?\s*\d{1,2}\s*月\s*\d{1,2}\s*[日号]?", customer_text)
    if time_match:
        entities["时间"] = re.sub(r"\s+", "", time_match.group(0))
    else:
        time_value = next((cue for cue in TRAVEL_TIME_CUES if cue in customer_text), "")
        if time_value:
            entities["时间"] = time_value
    budget_match = re.search(
        r"(?:预算|人均|每人|价格)\s*(?:大约|大概|约|是|在)?\s*([0-9一二两三四五六七八九十几百千万]+\s*(?:[-至到]\s*[0-9一二两三四五六七八九十几百千万]+)?\s*(?:元|块|千|万)?(?:左右|上下|以内)?)",
        customer_text,
    )
    if budget_match:
        entities["预算"] = re.sub(r"\s+", "", budget_match.group(1))
    product_match = re.search(r"(?:型号|产品|设备|款)\s*([A-Za-z0-9][A-Za-z0-9_-]{0,15})", customer_text)
    if product_match:
        entities["产品/型号"] = product_match.group(1)
    product_type_match = re.search(r"(车型|车款|汽车|车辆|SUV|轿车|电动车|摩托车)", customer_text, re.IGNORECASE)
    if product_type_match:
        entities["产品类型"] = product_type_match.group(1)
    payment_match = re.search(r"(信用卡|银行卡|借记卡|微信|支付宝|现金|对公转账|转账|分期|月结|货到付款)", customer_text)
    if payment_match:
        entities["支付方式"] = payment_match.group(1)
    quantity_match = re.search(r"(?<!\d)(\d{1,5}|[一二两三四五六七八九十几百]+)\s*(件|套|台|辆|份|箱|款|个)(?!人)", customer_text)
    if quantity_match:
        entities["数量"] = f"{quantity_match.group(1).replace('两', '2')}{quantity_match.group(2)}"
    order_match = re.search(r"(?:订单(?:号|编号)?|单号)\s*([A-Za-z0-9_-]{3,30})", customer_text, re.IGNORECASE)
    if order_match:
        entities["订单号"] = order_match.group(1)
    address_match = re.search(r"(?:收货地址|地址|寄到)\s*[:：]?\s*([^，。！？\n]{4,40})", customer_text)
    if address_match:
        entities["地址"] = address_match.group(1).strip()
    cuisine = [item for item in DINING_CUISINES if item in customer_text]
    if cuisine:
        entities["菜系/口味"] = "、".join(cuisine)
    restaurant_type = [item for item in DINING_TYPES if item in customer_text]
    if restaurant_type:
        entities["餐厅类型"] = "、".join(restaurant_type)
    service_match = re.search(r"(?:预约|安排|需要|想要)\s*([^，。！？\n]{2,18}?)(?:服务|吗|？|。|$)", customer_text)
    if service_match:
        entities["服务类型"] = service_match.group(1).strip()
    if _cue_hits(customer_text.lower(), "dining") and "地点" not in entities and "目的地" in entities:
        entities["地点"] = entities["目的地"]
    return entities


def extract_entity_records(text: str, dialogue: dict[str, Any] | None = None) -> dict[str, dict[str, str]]:
    """Return entity values with provenance for audit and role-confusion metrics."""
    return {key: {"value": value, "source_role": "customer"} for key, value in extract_entities(text, dialogue).items()}


def extract_travel_facts(text: str, dialogue: dict[str, Any] | None = None) -> dict[str, str]:
    entities = extract_entities(text, dialogue)
    return {
        output_key: entities[input_key]
        for input_key, output_key in (("目的地", "目的地"), ("出发地", "出发地"), ("人数", "出行人数"), ("时间", "出行时间"), ("预算", "预算范围"), ("菜系/口味", "游玩偏好"))
        if input_key in entities
    } | ({"游玩偏好": "、".join(cue for cue in TRAVEL_PREFERENCE_CUES if cue in customer_text_for_model(text, dialogue))} if any(cue in customer_text_for_model(text, dialogue) for cue in TRAVEL_PREFERENCE_CUES) else {})


def travel_output(customer_text: str, dialogue: dict[str, Any] | None = None, entities: dict[str, str] | None = None) -> dict[str, Any]:
    facts = extract_travel_facts(customer_text, dialogue)
    pieces = [f"{key}{value}" for key, value in facts.items()]
    demand = "旅游/出行/一日游需求"
    if pieces:
        demand += "：" + "；".join(pieces)
    else:
        demand += "：有明确游玩意向，目的地和行程细节待确认"
    missing = [("目的地", "目的地或游玩区域"), ("出行人数", "出行人数"), ("出行时间", "出行时间"), ("预算范围", "预算范围"), ("游玩偏好", "游玩偏好或交通方式")]
    questions = [question for key, question in missing if key not in facts]
    summary = "、".join(pieces) if pieces else "出游安排"
    if questions:
        reply = f"您好，收到您的出游想法（{summary}）。为了帮您整理合适的路线和方案，还需要了解：" + "、".join(questions) + "，方便补充一下吗？"
    else:
        questions = ["是否有必去景点或其他特殊安排"]
        reply = f"您好，已记录您的出行信息（{summary}）。我会据此整理路线和方案，您还有必去景点或其他特殊安排吗？"
    return {"需求": demand, "待确认问题": questions, "建议待办": ["确认行程细节", "根据现有信息推荐路线", "核对目的地开放和预约要求", "整理并发送出行方案"], "回复草稿": reply}


def dining_output(customer_text: str, dialogue: dict[str, Any] | None = None, entities: dict[str, str] | None = None) -> dict[str, Any]:
    entities = entities or extract_entities(customer_text, dialogue)
    pieces = []
    for key in ("地点", "人数", "时间", "菜系/口味", "餐厅类型", "预算"):
        if key in entities:
            pieces.append(f"{key}{entities[key]}")
    demand = "餐饮/用餐需求" + (("：" + "；".join(pieces)) if pieces else "：用餐安排待进一步确认")
    missing = [("地点", "用餐地点或餐厅类型"), ("人数", "用餐人数"), ("时间", "用餐时间"), ("菜系/口味", "菜系或口味偏好"), ("预算", "预算范围")]
    questions = [label for key, label in missing if key not in entities]
    summary = "、".join(pieces) if pieces else "用餐安排"
    reply = f"您好，收到您的用餐需求（{summary}）。为了帮您筛选合适的餐厅，还需要了解：" + "、".join(questions) + "，方便补充一下吗？" if questions else f"您好，已记录您的用餐信息（{summary}）。我会据此核实餐厅和订位情况，您还有忌口或特殊安排吗？"
    return {"需求": demand, "待确认问题": questions or ["忌口或特殊安排"], "建议待办": ["确认用餐条件", "按地点、人数和口味筛选餐厅", "核实营业时间和订位情况"], "回复草稿": reply}


def purchase_output(text: str, dialogue: dict[str, Any], entities: dict[str, str]) -> dict[str, Any]:
    """Merge a purchase request with facts supplied in later answer turns."""
    result = dict(INTENTS["purchase"])
    if not dialogue.get("is_dialogue"):
        return result
    facts = []
    for key in ("产品类型", "产品/型号", "数量", "预算", "地点", "地址", "支付方式"):
        if key in entities:
            facts.append(f"{key}{entities[key]}")
    if not facts:
        return result
    result["需求"] = "表达了采购意向，准备进一步下单：" + "；".join(facts)
    missing = []
    if not ("产品类型" in entities or "产品/型号" in entities) or "数量" not in entities:
        missing.append("产品规格与数量")
    if not ("地址" in entities or "地点" in entities):
        missing.append("收货地址")
    if "时间" not in entities:
        missing.append("期望到货时间")
    result["待确认问题"] = missing
    summary = "、".join(facts)
    if missing:
        result["回复草稿"] = f"您好，已记录您的采购意向（{summary}）。请补充" + "、".join(missing) + "，我先帮您核实库存与预计交期。"
    else:
        result["回复草稿"] = f"您好，已记录您的采购信息（{summary}）。我会先核实库存、交期和付款安排，确认后回复您。"
    return result


def auto_sales_output(text: str, dialogue: dict[str, Any], entities: dict[str, str]) -> dict[str, Any]:
    result = dict(INTENTS["auto_sales"])
    if not dialogue.get("is_dialogue"):
        return result
    facts = []
    for key in ("产品类型", "产品/型号", "数量", "预算", "地点", "支付方式"):
        if key in entities:
            facts.append(f"{key}{entities[key]}")
    if not facts:
        return result
    result["需求"] = "汽车/车辆选购意向：" + "；".join(facts)
    missing = []
    if "预算" not in entities:
        missing.append("预算范围")
    if "地点" not in entities:
        missing.append("主要用车场景")
    if "产品类型" not in entities:
        missing.append("偏好车型、能源和配置")
    if "时间" not in entities:
        missing.append("计划购车时间")
    result["待确认问题"] = missing or ["是否需要试驾或置换"]
    summary = "、".join(facts)
    result["回复草稿"] = f"您好，已记录您的购车意向（{summary}）。请补充" + "、".join(missing) + "，我再按条件筛选车型并核对报价、库存和试驾安排。" if missing else f"您好，已记录您的购车信息（{summary}）。我会先核对报价、库存和试驾安排，确认后回复您。"
    return result


def output_for_intent(intent: str, text: str, dialogue: dict[str, Any] | None = None, entities: dict[str, str] | None = None) -> dict[str, Any]:
    parsed = dialogue or parse_dialogue(text)
    extracted = entities or extract_entities(text, parsed)
    if intent == "travel":
        return travel_output(text, parsed, extracted)
    if intent == "dining":
        return dining_output(text, parsed, extracted)
    if intent == "purchase":
        return purchase_output(text, parsed, extracted)
    if intent == "auto_sales":
        return auto_sales_output(text, parsed, extracted)
    if intent == "no_intent":
        return dict(EMPTY_RESULT)
    return dict(INTENTS[intent])


def has_meaningful_text(text: str) -> bool:
    return bool(MEANINGFUL_CHAR_RE.search(text))


def matched_keyword_cues(text: str) -> list[str]:
    lower = text.lower()
    hits = [cue for cues in KEYWORD_CUES.values() for cue in cues if cue.lower() in lower]
    if re.search(r"玩(?!具)", lower) and "玩" not in hits:
        hits.append("玩")
    return list(dict.fromkeys(hits))


def _cue_hits(text: str, intent: str) -> list[str]:
    lower = text.lower()
    return [cue for cue in KEYWORD_CUES[intent] if cue.lower() in lower]


def _has_travel_evidence(text: str) -> bool:
    lower = text.lower()
    if any(marker in lower for marker in ("暂时没想好去哪里", "还没想好去哪里", "还没决定去哪", "没决定去哪里")) and not _cue_hits(lower, "travel"):
        return False
    if re.search(r"(?:不是|不算|并非|而不是)[^，。！？]{0,6}(?:旅游|旅行|出游|游玩|去玩)", lower):
        return False
    return bool(_cue_hits(lower, "travel") or re.search(r"(?:去|到|前往).{1,18}(?:玩|游|旅游|旅行|参观|景点|一日游|顺序|路线)", lower) or (any(cue in lower for cue in TRAVEL_TIME_CUES) and re.search(r"(?:去|到|前往)[\u3400-\u9fffA-Za-z0-9]{2,12}", lower)))


def _is_social_message(text: str) -> bool:
    compact = re.sub(r"[\s，。！？、:：,.!?;；]+", "", text.lower())
    if not compact:
        return True
    has_domain_cue = any(_cue_hits(compact, intent) for intent in STRONG_DOMAIN_ORDER)
    if has_domain_cue:
        return False
    social = tuple(cue for cue in KEYWORD_CUES["no_intent"] if len(cue) > 1 and cue != "你好")
    return ("你好" in compact and len(compact) <= 8) or any(cue in compact for cue in social)


def rule_intent(text: str, model_label: str | None = None) -> tuple[str | None, list[str], str]:
    """Apply high-precision domain rules before allowing the statistical model."""
    lower = text.lower()
    hits = matched_keyword_cues(text)
    if _is_social_message(text):
        return "no_intent", hits, "social_message"
    has_travel = _has_travel_evidence(lower)
    if any(cue in lower for cue in UNKNOWN_NO_INTENT_CUES) and not any(_cue_hits(lower, intent) for intent in STRONG_DOMAIN_ORDER if intent != "travel"):
        return "no_intent", hits, "unsupported_non_business_context"
    vague_markers = _cue_hits(lower, "vague") or any(marker in lower for marker in ("还没决定", "需求还不明确", "预算还没定"))
    generic_purchase = "想买东西" in lower or "想买" in lower and "具体" not in lower
    explicit_travel = bool(_cue_hits(lower, "travel"))
    committed_purchase = any(cue in lower for cue in ("还要买", "想买", "要买", "买一辆", "买一台", "买一部", "买一套", "我确定要买", "准备买", "确认采购", "已经决定买", "锁定", "给我留", "下单", "订购"))
    explicit_price_query = any(cue in lower for cue in ("多少钱", "什么价格", "什么价", "报价", "报个价", "单价", "价位", "核价", "报价单"))
    ticket_query = any(cue in lower for cue in ("门票", "预约", "开放时间", "余票", "入园", "入园票"))
    transport_query = any(cue in lower for cue in ("车票", "高铁", "租车", "租一辆车", "包车", "机场接送"))
    logistics_query = any(cue in lower for cue in ("发货", "出库", "配送", "物流", "到货", "几天", "派送"))
    auto_query = bool(_cue_hits(lower, "auto_sales")) or bool(re.search(r"(?:买|购买|推荐|了解).{0,8}车", lower))
    if committed_purchase and not explicit_price_query and not ticket_query and not transport_query and not logistics_query:
        if auto_query:
            return "auto_sales", hits, "committed_auto_purchase_context"
        return "purchase", hits, "committed_purchase_context"
    has_budget_value = bool(re.search(r"(?:预算|人均|每人)\s*(?:大约|大概|约|是|在)?\s*[0-9一二两三四五六七八九十几百千万]+", lower))
    if has_budget_value and any(cue in lower for cue in ("采购", "产品", "设备", "方案", "型号")) and not committed_purchase:
        return "price", hits, "budget_price_context"
    concrete_domain_signal = any(_cue_hits(lower, intent) for intent in STRONG_DOMAIN_ORDER if intent != "product_info")
    explicit_product = any(cue in lower for cue in ("产品", "设备", "摄像头", "软件", "系统", "型号", "参数", "规格", "功能", "夜视", "存储方式", "数据备份"))
    if vague_markers and not concrete_domain_signal and not explicit_product and not explicit_travel and not _cue_hits(lower, "dining") and (generic_purchase or "去哪里" in lower or "暂时没想好" in lower or "方案" in lower or "推荐" in lower or "介绍" in lower):
        return "vague", hits, "vague_context_fallback"
    for intent in STRONG_DOMAIN_ORDER:
        intent_hits = _cue_hits(lower, intent)
        if intent == "travel" and not has_travel:
            continue
        if intent == "attraction_ticket" and has_travel and not ticket_query:
            continue
        if intent == "attraction_ticket" and transport_query and not ticket_query:
            continue
        if intent == "software_sales" and _cue_hits(lower, "customization"):
            continue
        if intent == "transport" and "预约" in lower and ("商务用车" in lower or "服务" in lower):
            continue
        if intent == "auto_sales" and "预约" in lower and "商务用车" in lower:
            continue
        if intent == "product_info" and (has_travel or (vague_markers and not explicit_product)):
            continue
        if intent_hits:
            return intent, hits, f"{intent}_keyword_fallback"
    # A named destination plus a travel action is stronger than generic "我想去".
    if has_travel:
        return "travel", hits, "travel_context_rule"
    context_slots = extract_entities(text)
    if _cue_hits(lower, "vague") or any(key in context_slots for key in ("人数", "时间", "预算")):
        return "vague", hits, "vague_context_fallback"
    # The model can resolve an explicitly supported non-travel cue, but must not
    # turn generic words such as "我想" or "两个人" into travel.
    if model_label and model_label not in {"travel", "no_intent"}:
        if model_label in INTENTS and _cue_hits(lower, model_label):
            return model_label, hits, "model_with_domain_evidence"
    if model_label == "no_intent":
        return "no_intent", hits, "model_no_intent"
    return "no_intent", hits, "abstain_without_domain_evidence"


def tokenize(text: str) -> list[str]:
    """Build char n-grams plus phrase/domain features without third-party tokenizers."""
    compact = "".join(ch for ch in text.lower() if ch.isalnum() or "\u3400" <= ch <= "\u9fff")
    features: list[str] = []
    for width in (1, 2, 3):
        features.extend(f"{width}:{compact[i:i + width]}" for i in range(max(0, len(compact) - width + 1)))
    for intent, cues in KEYWORD_CUES.items():
        for cue in cues:
            if len(cue) >= 2 and cue.lower() in text.lower():
                features.append(f"phrase:{intent}:{cue}")
    if _has_travel_evidence(text):
        features.append("domain:travel")
    if _cue_hits(text.lower(), "dining"):
        features.append("domain:dining")
    if any(cue in text.lower() for cue in KEYWORD_CUES["logistics"]):
        features.append("domain:logistics")
    if any(cue in text.lower() for cue in KEYWORD_CUES["after_sales"]):
        features.append("domain:after_sales")
    return features


def load_model(path: Path = MODEL_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        model = json.load(stream)
    if model.get("format") not in {"char-ngram-multinomial-nb-v1", "char-ngram-multinomial-nb-v2"}:
        raise ValueError("Unsupported or invalid model format")
    if not model.get("classes") or not model.get("vocabulary_size"):
        raise ValueError("Model is missing trained classes or vocabulary")
    return model


def classify(text: str, model: dict[str, Any] | None) -> tuple[str | None, float]:
    if not model:
        return None, 0.0
    features = tokenize(text)
    if not features:
        return None, 0.0
    normalized_text = text.lower()
    has_business_cue = any(cue.lower() in normalized_text for cues in KEYWORD_CUES.values() for cue in cues if cue != "你好")
    content_length = sum(ch.isalnum() or "\u3400" <= ch <= "\u9fff" for ch in normalized_text)
    auto_signal = _cue_hits(normalized_text, "auto_sales") or re.search(r"(?:买|购买|推荐|了解).{0,8}车", normalized_text)
    if "auto_sales" in model.get("classes", ()) and auto_signal and any(cue in normalized_text for cue in ("买", "购车", "试驾", "预算")):
        return "auto_sales", 0.94
    if "software_sales" in model.get("classes", ()) and _cue_hits(normalized_text, "software_sales") and any(cue in normalized_text for cue in ("订阅", "部署", "收费", "演示", "上线", "需要一套")):
        return "software_sales", 0.92
    if "purchase" in model.get("classes", ()) and _cue_hits(normalized_text, "purchase") and not _cue_hits(normalized_text, "logistics"):
        return "purchase", 0.90
    if not has_business_cue and content_length < 6:
        return None, 0.0
    known_vocabulary = set(model.get("vocabulary", ()))
    known_count = sum(feature in known_vocabulary for feature in features)
    known_ratio = known_count / max(1, len(features))
    if not has_business_cue and known_ratio < float(model.get("min_known_feature_ratio", 0.03)):
        return None, known_ratio
    classes = model["classes"]
    vocab_size = model["vocabulary_size"]
    alpha = float(model["alpha"])
    log_scores: dict[str, float] = {}
    for label in classes:
        counts = model["token_counts"][label]
        denominator = model["token_totals"][label] + alpha * vocab_size
        class_prior = model["class_counts"][label] / model["training_size"]
        weight = float(model.get("class_weights", {}).get(label, 1.0))
        score = math.log(class_prior) + 0.35 * math.log(max(weight, 1e-9))
        for feature in features:
            if feature in counts:
                score += math.log((counts[feature] + alpha) / denominator)
            else:
                score += math.log(alpha / denominator)
        log_scores[label] = score
    ranked_scores: dict[str, float] = {}
    for label, score in log_scores.items():
        cue_matches = sum(cue in normalized_text for cue in KEYWORD_CUES.get(label, ()))
        cue_bonus = min(1.15, cue_matches * 0.28)
        if label == "dining" and _cue_hits(normalized_text, "dining"):
            cue_bonus += 0.55
        if label == "travel" and _has_travel_evidence(normalized_text):
            cue_bonus += 0.55
        ranked_scores[label] = score / max(1, len(features)) + cue_bonus
    ranked = sorted(ranked_scores.items(), key=lambda pair: pair[1], reverse=True)
    best_label, best_score = ranked[0]
    margin = best_score - ranked[1][1] if len(ranked) > 1 else 0.0
    confidence = 1.0 / (1.0 + math.exp(-min(60.0, margin * 8.0)))
    if confidence < float(model.get("abstain_threshold", 0.56)):
        return None, confidence
    return best_label, confidence


def analyze_text(text: str, model: dict[str, Any] | None) -> dict[str, Any]:
    dialogue = parse_dialogue(text)
    views = customer_text_views(text, dialogue)
    normalized = views["model"]
    entities = extract_entities(text, dialogue)
    if normalized:
        model_label, confidence = classify(normalized, model)
    else:
        model_label, confidence = "no_intent", 1.0
    if not normalized or not has_meaningful_text(normalized):
        final_label, rule_hits, rule = "no_intent", [], "empty_or_meaningless"
    else:
        final_label, rule_hits, rule = rule_intent(normalized, model_label)
    result = dict(EMPTY_RESULT) if final_label is None else output_for_intent(final_label, text, dialogue, entities)
    model_result = dict(EMPTY_RESULT) if model_label is None or model_label not in INTENTS else output_for_intent(model_label, text, dialogue, entities)
    return {
        "customer_messages": dialogue["customer_messages"],
        "agent_messages": dialogue["agent_messages"],
        "turns": dialogue["turns"],
        "is_dialogue": dialogue["is_dialogue"],
        "model_input": normalized,
        "recent_customer_message": views["recent"],
        "customer_summary": views["summary"],
        "primary_customer_messages": views["primary_messages"],
        "slot_answers": views["slot_answers"],
        "entities": entities,
        "entity_records": extract_entity_records(text, dialogue),
        "entity_sources": {key: "customer" for key in entities},
        "model_label": model_label,
        "model_confidence": confidence,
        "model_available": bool(model),
        "model_raw_output": model_result,
        "travel_facts": extract_travel_facts(text, dialogue) if final_label == "travel" else {},
        "rule_hits": rule_hits,
        "rule": rule,
        "final_label": final_label,
        "fallback_applied": final_label != model_label or result != model_result,
        "final_output": result,
    }


def result_for_text(text: str, model: dict[str, Any]) -> tuple[dict[str, Any], str | None, float]:
    analysis = analyze_text(text, model)
    return analysis["final_output"], analysis["final_label"], analysis["model_confidence"]


def parse_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{line_no}: {exc}") from exc
            rows.append(row)
    return rows


def output_intent(output: dict[str, Any]) -> str:
    demand = output.get("需求", "")
    if not isinstance(demand, str):
        return ""
    for prefix, intent in (("旅游/出行/一日游需求", "travel"), ("餐饮/用餐需求", "dining"), ("景区/门票", "attraction_ticket"), ("酒店/住宿", "hotel"), ("交通/接送", "transport"), ("表达了采购意向", "purchase"), ("汽车/车辆选购意向", "auto_sales"), ("咨询企业软件", "software_sales")):
        if demand.startswith(prefix):
            return intent
    return NEED_TO_INTENT.get(demand, "")
