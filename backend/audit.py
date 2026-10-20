"""Minimal server-side access/feature counters; never store request bodies or tokens."""
import logging
import re
import time

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, ConfigDict, Field

import database


def init_schema(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS access_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at INTEGER NOT NULL, user_id INTEGER REFERENCES users(id),
        feature TEXT NOT NULL, path TEXT NOT NULL, method TEXT NOT NULL,
        status_code INTEGER NOT NULL, duration_ms INTEGER NOT NULL)""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_time ON access_events(created_at, id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_feature ON access_events(feature, created_at)")


def classify(path, method):
    if path == '/api/auth/login': return 'login'
    if path == '/api/auth/register': return 'register'
    if path == '/api/auth/logout': return 'logout'
    if path == '/api/usage/visit': return 'visit'
    if path == '/api/usage/copy': return 'copy_client'
    if path in ('/analyze', '/api/analyze'): return 'analysis'
    if re.fullmatch(r'/api/records/\d+/actions', path): return 'analysis_action'
    if re.fullmatch(r'/(api/)?records/\d+/export', path): return 'export'
    if re.fullmatch(r'/(api/)?records/\d+', path):
        return {'PUT': 'save', 'DELETE': 'record_delete'}.get(method, 'record_read')
    if path in ('/records', '/api/records'):
        return 'history_delete' if method == 'DELETE' else 'history'
    if path.startswith('/api/access-control/'): return 'access_control'
    if path.startswith('/api/admin/'): return 'admin_stats'
    if path.startswith('/api/calendar/'):
        if path.endswith('/completion'): return 'calendar_complete'
        if path.endswith('/from-record'): return 'calendar_import'
        return {'POST': 'calendar_create', 'PATCH': 'calendar_edit',
                'DELETE': 'calendar_delete'}.get(method, 'calendar_read')
    return None


async def record_request(request, call_next):
    started = time.monotonic()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        feature = classify(request.url.path, request.method)
        route = request.scope.get('route')
        path = getattr(route, 'path', None)
        if feature and path and request.method != 'OPTIONS':
            user = getattr(request.state, 'user', None)
            # Unmatched paths and query strings (which may contain secrets) never enter the log.
            try:
                from starlette.concurrency import run_in_threadpool
                await run_in_threadpool(_insert, user['id'] if user else None, feature, path,
                                        request.method, status, int((time.monotonic()-started)*1000))
            except Exception:
                logging.getLogger('keyoushu.backend').exception('访问统计写入失败')


def _insert(user_id, feature, path, method, status, duration):
    with database._connect() as conn:
        conn.execute('INSERT INTO access_events(created_at,user_id,feature,path,method,status_code,duration_ms) VALUES(?,?,?,?,?,?,?)',
                     (int(time.time()), user_id, feature, path, method, status, duration))


def routes():
    from auth import permission, require_user
    router = APIRouter(prefix='/api')

    class Visit(BaseModel):
        model_config = ConfigDict(extra='forbid')

    class Copy(BaseModel):
        model_config = ConfigDict(extra='forbid')
        record_id: int = Field(strict=True, gt=0)

    @router.post('/usage/visit')
    def visit(payload: Visit, user=Depends(require_user)):
        return {'code': 0, 'message': '访问已记录', 'data': None}

    @router.post('/usage/copy')
    def copy(payload: Copy, user=Depends(permission('records:read'))):
        if database.get_record(payload.record_id, owner_id=user['id'], include_all='records:all' in user['permissions']) is None:
            raise HTTPException(404,'记录不存在')
        return {'code':0,'message':'客户端复制事件已记录','data':None}

    @router.get('/admin/overview')
    def overview(days: int = Query(7, ge=1, le=90), user=Depends(permission('admin:stats'))):
        since = int(time.time()) - days*86400
        with database._connect() as conn:
            conn.execute('BEGIN')
            users = dict(conn.execute('SELECT COUNT(*) total, COALESCE(SUM(is_active),0) active FROM users').fetchone())
            records = {'total': conn.execute('SELECT COUNT(*) FROM records').fetchone()[0]}
            visits = dict(conn.execute("SELECT COUNT(*) total,COUNT(DISTINCT user_id) unique_users FROM access_events WHERE feature='visit' AND status_code BETWEEN 200 AND 299 AND created_at>=?", (since,)).fetchone())
            features = [dict(r) for r in conn.execute('''SELECT feature,COUNT(*) total,
                SUM(status_code BETWEEN 200 AND 299) succeeded,SUM(status_code NOT BETWEEN 200 AND 299) failed
                FROM access_events WHERE created_at>=? GROUP BY feature ORDER BY total DESC''', (since,))]
            daily = [dict(r) for r in conn.execute('''SELECT date(created_at,'unixepoch') date,
                SUM(feature='visit' AND status_code BETWEEN 200 AND 299) visits,
                SUM(feature!='visit') actions FROM access_events WHERE created_at>=? GROUP BY date ORDER BY date''', (since,))]
        return {'code':0,'message':'ok','data':{'users':users,'records':records,'visits':visits,'features':features,'daily':daily,
            'note':'统计从部署此版本后开始采集；日期采用 UTC，访问次数为已登录页面打开次数，独立用户按账号去重。'}}

    @router.get('/admin/events')
    def events(days: int = Query(7,ge=1,le=90), limit: int = Query(50,ge=1,le=200),
               offset: int = Query(0,ge=0), user=Depends(permission('admin:stats'))):
        since = int(time.time())-days*86400
        with database._connect() as conn:
            conn.execute('BEGIN')
            total = conn.execute('SELECT COUNT(*) FROM access_events WHERE created_at>=?',(since,)).fetchone()[0]
            items = [dict(r) for r in conn.execute('''SELECT e.*,u.username,(e.status_code BETWEEN 200 AND 299) success
                FROM access_events e LEFT JOIN users u ON u.id=e.user_id WHERE e.created_at>=?
                ORDER BY e.id DESC LIMIT ? OFFSET ?''',(since,limit,offset))]
        return {'code':0,'message':'ok','data':{'total':total,'items':items}}

    return router
