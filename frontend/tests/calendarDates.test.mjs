import test from 'node:test'
import assert from 'node:assert/strict'
import { addDays, businessDate, daysBetween, dateNumber, startDate, urgencyLevel, itemColor, itemStatus, itemsOnDate, isAnomaly, monthBounds, monthCells, shiftMonth, ganttSegments, LEVEL_COLORS } from '../src/calendarDates.js'

const task = (extra = {}) => ({ id: 1, title: '排期测试', created_at: '2026-10-19T23:30:00+08:00', start_date: null, due_date: '2026-10-22', manual_level: null, completed: false, completed_at: null, ...extra })
test('日期运算不受本机时区影响，支持闰年与跨月，拒绝无效日期', () => {
  assert.equal(addDays('2024-02-28',1),'2024-02-29')
  assert.equal(addDays('2024-02-29',1),'2024-03-01')
  assert.equal(addDays('2026-12-31',1),'2027-01-01')
  assert.equal(daysBetween('2026-10-19','2026-10-22'),3)
  assert.ok(Number.isNaN(dateNumber('2026-02-29')))
  assert.equal(businessDate('2026-10-19T23:30:00Z'),'2026-10-20')
})
test('开始日只使用 AI 字段或业务时区创建日，不猜测 DDL', () => {
  assert.equal(startDate(task({ start_date:'2026-10-16' })),'2026-10-16')
  assert.equal(startDate(task()),'2026-10-19')
  assert.equal(startDate(task({ created_at:'2026-10-18T19:30:00Z' })),'2026-10-19')
})
test('自动等级覆盖全部边界，手动覆盖跨日期固定，恢复自动生效', () => {
  for (const [d,level] of [[-1,5],[0,5],[2,5],[3,4],[4,4],[5,3],[6,3],[7,2],[8,2],[9,1],[30,1]]) {
    assert.equal(urgencyLevel(task({ due_date:addDays('2026-10-19',d) }),'2026-10-19'),level)
  }
  assert.equal(urgencyLevel(task({manual_level:2}),'2026-10-21'),2)
  assert.equal(urgencyLevel(task({manual_level:2}),'2026-10-19'),2)
  assert.equal(urgencyLevel(task({manual_level:null}),'2026-10-19'),4)
})
test('进行区间包含开始与截止日，完成与无 DDL 不出现圆点', () => {
  const rows = [task(),task({id:2,completed:true}),task({id:3,due_date:null})]
  assert.equal(itemsOnDate(rows,'2026-10-18').length,0)
  assert.deepEqual(itemsOnDate(rows,'2026-10-19').map(t=>t.id),[1])
  assert.equal(itemsOnDate(rows,'2026-10-22').length,1)
  assert.equal(itemsOnDate(rows,'2026-10-23').length,0)
})
test('逾期优先于固定等级，完成优先于逾期；反向日期仅标记 DDL 当天', () => {
  const late=task({due_date:'2026-10-18',manual_level:5})
  assert.equal(itemColor(late,'2026-10-19'),LEVEL_COLORS.overdue)
  assert.equal(itemColor({...late,completed:true},'2026-10-19'),LEVEL_COLORS.completed)
  assert.equal(itemStatus(late,'2026-10-19'),'逾期')
  assert.equal(isAnomaly(late),true)
  assert.equal(itemsOnDate([late],'2026-10-18').length,1)
  assert.equal(itemsOnDate([late],'2026-10-19').length,0)
})
test('月历固定六周，周一起始，跨年与闰月正确', () => {
  assert.deepEqual(monthBounds('2024-02'),{first:'2024-02-01',last:'2024-02-29',next:'2024-03-01'})
  const cells=monthCells('2026-10')
  assert.equal(cells.length,42)
  assert.equal(cells[0],'2026-09-28')
  assert.equal(cells.at(-1),'2026-11-08')
  assert.equal(shiftMonth('2026-12',1),'2027-01')
  assert.equal(shiftMonth('2026-01',-1),'2025-12')
})
test('甘特图计划段与逾期虚线段按时间正向排列并裁剪至当前月份', () => {
  const late=task({start_date:'2026-09-29',due_date:'2026-10-15'})
  assert.deepEqual(ganttSegments(late,'2026-10-19','2026-10-01','2026-10-31'),[
    {from:'2026-10-01',to:'2026-10-15',overdue:false},
    {from:'2026-10-16',to:'2026-10-19',overdue:true},
  ])
  assert.equal(ganttSegments({...late,completed:true},'2026-10-19','2026-10-01','2026-10-31').length,1)
  assert.deepEqual(ganttSegments(task({due_date:'2026-10-18'}),'2026-10-19','2026-10-01','2026-10-31'),[])
})
