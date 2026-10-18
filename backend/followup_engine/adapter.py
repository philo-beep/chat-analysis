"""Conservative business facts; every evidence string is an exact input substring."""
from __future__ import annotations

import re

from .upstream_common import INTENTS, classify, rule_intent

SELLERS = ("商家", "乙方", "客服", "销售", "卖家", "seller", "merchant", "assistant")
CUSTOMERS = ("客户", "甲方", "顾客", "买家", "customer", "client", "buyer", "user")
NUMBER = r"(?:\d+(?:\.\d+)?|[一二两三四五六七八九十百千万]+)"
RANGE = r"\s*(?:到|至|-|~|～|—)\s*"
QUANTITY = re.compile(r"(?:大概|大约|约|预计|差不多|暂定)?\s*" + NUMBER + r"(?:" + RANGE + NUMBER + r")?\s*(?:左右|上下)?\s*件")
MONEY = re.compile(NUMBER + r"\s*(?:千|万)?(?:" + RANGE + NUMBER + r"\s*(?:千|万)?)?\s*(?:元|块)?(?:\s*(?:左右|上下))?")
DATE = re.compile(r"(?:(?:20\d{2})\s*年\s*)?\d{1,2}\s*月\s*\d{1,2}\s*[日号](?:\s*(?:之前|以前|前|当天))?|(?:下周末|本周末|这个周末|下周|本周|下个月|月底|月末|年底|明天|后天|今天|周[一二三四五六日天]|星期[一二三四五六日天])")
CORRECTION = re.compile(r"(?:改为|改成|改到|调整为|调整到|更正为|最终(?:确认|按|定为)|确定(?:按|为)|以.{0,15}为准)")
HESITATION = re.compile(r"(?:记得|好像|似乎|可能|是不是|应该是|吧|吗|是否|能否|可不可以|不确定|再确认|没确认)")


def customer_clauses(text: str) -> tuple[list[str], bool]:
    """Preserve substrings and exclude seller statements from confirmed facts."""
    clauses: list[str] = []
    has_roles = any(re.match(r"^\s*(?:\[|【)?(?:客户|甲方|顾客|买家|商家|乙方|客服|销售|卖家|customer|seller|merchant|assistant)", line, re.I) and re.search(r"[:：\]】]", line) for line in text.splitlines())
    current = "unknown" if has_roles else "customer"
    uncertain_role = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        label = None
        body = line
        bracket = re.match(r"^[\[【]([^\]】]+)[\]】]\s*(.*)$", line)
        colon = re.match(r"^([^：:\n]{1,45})[：:]\s*(.*)$", line)
        if bracket:
            label, body = bracket.groups()
        elif colon:
            candidate, rest = colon.groups()
            if candidate not in {"预算", "总预算", "单价预算", "数量", "面料", "交付时间", "设计"}:
                label, body = candidate, rest
        if label is not None:
            lower = label.lower()
            if any(role in lower for role in SELLERS):
                current = "seller"
            elif any(role in lower for role in CUSTOMERS):
                current = "customer"
            else:
                current = "unknown"
                uncertain_role = True
        if current == "customer":
            clauses.extend(part.strip() for part in re.split(r"[，。！？；\n]|→", body) if part.strip())
    return clauses, uncertain_role


def _quantity_value(raw: str) -> str:
    value = re.sub(r"\s+", "", raw).replace("大概", "约").replace("大约", "约")
    return re.sub(r"到|至|~|～|—", "-", value)


def _money_value(raw: str) -> str:
    value = re.sub(r"\s+", "", raw).replace("块", "元")
    value = re.sub(r"到|至|~|～|—", "-", value)
    ranges = {"三四千": "3000-4000元", "两三千": "2000-3000元", "四五千": "4000-5000元", "一两万": "10000-20000元"}
    for phrase, normalized in ranges.items():
        if phrase in value:
            return re.sub(re.escape(phrase) + r"元?", normalized, value)
    if "元" not in value:
        value = re.sub(r"(左右|上下)$", r"元\1", value) if value.endswith(("左右", "上下")) else value + "元"
    return value


def analyze(text: str, model: dict) -> dict:
    clauses, uncertain_role = customer_clauses(text)
    customer_text = "\n".join(clauses)
    # The original trained tokenizer and NB classifier participate in every call.
    model_label, _confidence = classify(customer_text, model)
    intent, _hits, _rule = rule_intent(customer_text, model_label)
    requirements: list[dict[str, str]] = []
    questions: list[str] = []
    candidates: dict[str, list[tuple[str, str, bool, bool]]] = {}

    def add(field: str, value: str, evidence: str) -> None:
        if evidence not in text:
            raise ValueError("事实证据无法在原文中找到")
        requirements.append({"field": field, "value": value, "evidence": evidence})

    def candidate(field: str, value: str, clause: str) -> None:
        candidates.setdefault(field, []).append((value, clause, bool(CORRECTION.search(clause)), bool(HESITATION.search(clause))))

    for clause in clauses:
        # Historical orders are not the current customer's order requirements.
        if re.search(r"订过|买过|购过|上次|去年|曾经|旧订单|之前.{0,12}(?:下单|订购|订了)", clause):
            continue
        quantities = list(QUANTITY.finditer(clause))
        # “40元一件” is a unit price, not an order for one item.
        quantities = [m for m in quantities if not (re.sub(r"\s+", "", m.group()) == "一件" and re.search(r"预算|单价|元|左右", clause[:m.start()]))]
        quantities = [m for m in quantities if not (re.sub(r"\s+", "", m.group()) == "一件" and re.search(r"运费|定金|单价|报价", clause[m.end():]))]
        quantities = [m for m in quantities if not re.search(r"(?:不要|不用|不是|不做|取消|先不做)\s*$", clause[:m.start()])]
        if quantities:
            chosen = quantities[-1] if CORRECTION.search(clause) else quantities[0]
            candidate("数量", _quantity_value(chosen.group()), clause)
        for category in ("文化衫", "T恤", "t恤", "团体服", "卫衣", "工作服"):
            if category in clause and not re.search(r"(?:不要|不用|不是|不做|不定制)\s*" + re.escape(category), clause) and not any(r["field"] == "品类" for r in requirements):
                add("品类", category, clause)
        for fabric in ("纯棉", "涤棉", "速干", "全棉", "聚酯纤维"):
            if fabric in clause and not re.search(r"(?:不要|不用|不是|不选|不想要)\s*" + fabric, clause):
                candidate("面料", fabric, clause)
        is_unit = bool(re.search(r"单价|每\s*件|一\s*件|元\s*/\s*件", clause))
        unit_budget = is_unit and not re.search(r"报价|运费|定金|已付|付了", clause)
        has_budget = "预算" in clause or unit_budget or (candidates.get("预算") and HESITATION.search(clause))
        if has_budget:
            money_source = clause.split("预算", 1)[1] if "预算" in clause else clause
            monetary = [m for m in MONEY.finditer(money_source) if not re.match(r"\s*(?:件|月|日|号)", money_source[m.end():])]
            monetary = [m for m in monetary if not re.search(r"(?:不是|不要|不按|取消)\s*$", money_source[:m.start()])]
            if monetary:
                chosen = monetary[-1] if CORRECTION.search(clause) else monetary[0]
                candidate("单价预算" if is_unit else "预算", _money_value(chosen.group()), clause)
        for date in DATE.finditer(clause):
            candidate("交付时间", date.group().strip(), clause)
        if "设计" in clause and re.search(r"需要|提供|帮.*设计|你们.*设计", clause):
            if re.search(r"(?:不需要|不用).{0,8}设计", clause) or re.search(r"你们不用设计", clause):
                design = "无需商家提供设计"
            elif re.search(r"(?:我|我们|客户|甲方).{0,8}提供.*设计|设计.{0,3}我.{0,3}提供", clause):
                design = "客户提供设计稿"
            else:
                design = "需要商家提供设计"
            candidate("设计", design, clause)

    for field, entries in candidates.items():
        corrections = [i for i, entry in enumerate(entries) if entry[2] and not entry[3]]
        active = entries[corrections[-1]:] if corrections else entries
        values = list(dict.fromkeys(entry[0] for entry in active))
        last = active[-1]
        if field == "设计" and set(values) <= {"无需商家提供设计", "客户提供设计稿"}:
            # Customer-provided artwork and no merchant design are compatible.
            active = [next((entry for entry in reversed(active) if entry[0] == "客户提供设计稿"), last)]
            last = active[0]
            values = [last[0]]
        if len(values) > 1 or last[3]:
            first_pos = text.find(active[0][1])
            last_pos = text.rfind(last[1]) + len(last[1])
            add(field, " / ".join(values) + "（待确认）", text[first_pos:last_pos])
            questions.append(f"请确认最终{field}（提到{'、'.join(values)}，尚未明确确认）")
        else:
            add(field, last[0], last[1])

    fields = {r["field"]: r["value"] for r in requirements}
    if "数量" not in fields:
        questions.append("请确认预计数量")
    if "预算" not in fields and "单价预算" not in fields:
        questions.append("请确认预算范围（总预算或每件预算）")
    dates = fields.get("交付时间", "")
    if not dates:
        questions.append("请确认期望收货时间")
    elif not re.search(r"20\d{2}\s*年", dates):
        if "月" in dates and re.search(r"\d", dates):
            questions.append("请确认交付日期的具体年份")
        else:
            questions.append(f"请确认“{dates}”对应的具体收货日期")
    questions.append("请确认尺码分布")
    if "设计" not in fields:
        questions.append("请确认印制图案及是否需要商家提供设计")
    if uncertain_role:
        questions.append("请确认截图中未标明角色的消息分别由客户还是商家发送")
    tasks = ["根据已记录需求核算报价，确认后再回复价格", "核实生产与物流可行时间"]
    if fields.get("设计") == "需要商家提供设计":
        tasks.insert(0, "根据客户要求准备初步设计方案供确认")
    elif intent in INTENTS and intent not in {"no_intent", "vague"} and not requirements:
        tasks = list(INTENTS[intent]["建议待办"])
    facts = "、".join(f"{r['field']}：{r['value']}" for r in requirements)
    reply = (f"收到，已记录{facts}。" if facts else "您好，可以先为您介绍定制方案。")
    reply += "还需确认：" + "；".join(questions) + "。具体报价和可行交期核实后再与您确认。"
    return {"requirements": requirements, "questions": questions, "tasks": tasks, "reply": reply, "is_sample": False}
