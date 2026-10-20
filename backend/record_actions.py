"""Transactional user decisions for expanded analysis, using existing calendar tasks."""

import copy
import hashlib
import json

import calendar_store
import database


_ENTRY_STATES = {"questions": ("status", "confirmed_answer"),
                 "ddl_tasks": ("status", "calendar_task_id"),
                 "suggested_tasks": ("status", "task_item_id")}


def _content(entry):
    if not isinstance(entry, dict):
        return entry
    return {key: value for key, value in entry.items()
            if key not in {"status", "confirmed_answer", "calendar_task_id", "task_item_id"}}


def preserve_action_states(previous, submitted):
    """Ordinary edits cannot forge acceptance IDs or undo newer server decisions."""
    result = copy.deepcopy(submitted)
    result.pop("action_states", None)
    if previous.get('analysis_version') == 2:
        if result.get('ddl_tasks') is None or result.get('suggested_tasks') is None:
            _fail(409, '新版分析内容不能降级，请重新打开这份聊天')
        result['analysis_version'] = 2
    # Start dates are supplied by the model/backend, never edited by a browser.
    old_ddls = previous.get('ddl_tasks') or []
    for index, entry in enumerate(result.get('ddl_tasks') or []):
        if index >= len(old_ddls) or entry.get('start_date') != old_ddls[index].get('start_date'):
            _fail(422, '开始日期由分析结果提供，不能修改')
    for field, names in _ENTRY_STATES.items():
        old = previous.get(field, []) or []
        entries = result.get(field, []) or []
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            for name in names:
                entry.pop(name, None)
            if index < len(old) and _content(entry) == _content(old[index]) and isinstance(old[index], dict):
                for name in names:
                    if name in old[index]:
                        entry[name] = old[index][name]
    # Old tasks remain string[]; their operation state lives alongside the array.
    states = {}
    old_tasks, new_tasks = previous.get("tasks", []), result.get("tasks", [])
    for index, text in enumerate(new_tasks):
        state = (previous.get("action_states") or {}).get(str(index))
        if index < len(old_tasks) and old_tasks[index] == text and state:
            states[str(index)] = state
    if states or previous.get('analysis_version') == 2:
        result["action_states"] = states
    return result


def _fail(status, message):
    raise calendar_store.CalendarError(status, message)


def apply_action(user, record_id, payload):
    """Return public result and optional task; all writes share one transaction."""
    action, index = payload["action"], payload["index"]
    with database._connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        # User decisions modify their own record; broad admin read access is not ownership.
        row = conn.execute("SELECT result FROM records WHERE id=? AND owner_id=?", (record_id, user["id"])).fetchone()
        if row is None:
            _fail(404, "来源聊天不存在或不能修改")
        try:
            result = json.loads(row["result"])
        except (json.JSONDecodeError, TypeError):
            _fail(409, "来源聊天数据无法读取")
        expected = dict(payload.get('expected_result') or {})
        expected.pop('id', None)
        if expected != result:
            _fail(409, "这份聊天已有更新，请重新打开后操作")
        if not isinstance(result, dict):
            _fail(409, '来源聊天数据无法读取')
        if action == "add_ddl_task":
            field = "ddl_tasks"
        elif action in {"accept_suggestion", "ignore_suggestion"}:
            field = payload.get("kind") or "suggested_tasks"
            if field not in {"tasks", "suggested_tasks"}:
                _fail(422, "请选择有效的建议来源")
        elif action == "confirm_question":
            field = "questions"
        else:
            _fail(422, "不支持的操作")
        entries = result.get(field, [])
        if not isinstance(entries, list) or index < 0 or index >= len(entries):
            _fail(409, "内容已更新，请刷新后重试")
        entry = entries[index]
        title = entry if isinstance(entry, str) else entry.get("question" if field == "questions" else "title")
        if not isinstance(title, str) or not title.strip():
            _fail(422, "不能操作空白事项")
        if field == "tasks":
            state = result.setdefault("action_states", {}).setdefault(str(index), {"status": "pending", "task_item_id": None})
        else:
            if isinstance(entry, str):
                entry = {"question": entry, "initial_guess": "未知", "related_ddl_index": None}
                entries[index] = entry
            state = entry
        task = None
        if action == "confirm_question":
            answer = payload.get("answer")
            if not isinstance(answer, str) or not answer.strip():
                _fail(422, "请填写确认后的答案")
            state.update(status="confirmed", confirmed_answer=answer.strip())
        elif action == "ignore_suggestion":
            if state.get("status") == "accepted":
                _fail(409, "建议已采纳；如需移除，请在待办池中删除")
            state.update(status="ignored")
        else:
            signature = json.dumps(_content(entry), ensure_ascii=False, sort_keys=True)
            # Same key as the legacy importer prevents duplicate legacy rows.
            key = (f"{record_id}:{index}:" + hashlib.sha256(entry.encode()).hexdigest()
                   if field == "tasks" else f"analysis:{record_id}:{field}:{index}:" + hashlib.sha256(signature.encode()).hexdigest())
            existing = conn.execute("SELECT * FROM task_items WHERE owner_id=? AND source_task_key=?", (user["id"], key)).fetchone()
            if existing:
                task = calendar_store.serialize(existing)
            else:
                task_title = title.strip()
                notes = (entry.get("source_quote", "") if field == "ddl_tasks" else entry.get("reason", "") if isinstance(entry, dict) else "")
                if len(task_title) > 200:
                    notes = task_title + ("\n" + notes if notes else "")
                task = calendar_store._insert(conn, user["id"], {
                    "title": task_title[:200], "notes": notes,
                    "due_date": entry["ddl_date"] if field == "ddl_tasks" else None,
                    "start_date": entry.get("start_date") if field == "ddl_tasks" else None,
                }, source_record_id=record_id, source_task_key=key)
            if field == "ddl_tasks":
                state.update(status="added", calendar_task_id=task["id"])
            else:
                state.update(status="accepted", task_item_id=task["id"])
        result.pop("customer_profile", None)
        conn.execute("UPDATE records SET result=?,updated_at=? WHERE id=? AND owner_id=?",
                     (json.dumps(result, ensure_ascii=False), calendar_store.now().isoformat(timespec="seconds"), record_id, user["id"]))
        # Read public record only after the transaction commits.
    return {"record": database.get_record(record_id, owner_id=user['id'], include_all=False), "item": task}
