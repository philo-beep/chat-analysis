// 仅维护本机凭据；身份与权限始终以服务端 /me 的返回为准。
import { readonly, ref } from 'vue'

export const TOKEN_STORAGE_KEY = 'keyoushu.auth.token'

function readToken() {
  try { return localStorage.getItem(TOKEN_STORAGE_KEY) || '' } catch { return '' }
}

const token = ref(readToken())
const user = ref(null)
const version = ref(0)

export const currentUser = readonly(user)
export const sessionVersion = readonly(version)

export function getAuthToken() {
  return token.value
}

function persistToken(value) {
  try {
    if (value) localStorage.setItem(TOKEN_STORAGE_KEY, value)
    else localStorage.removeItem(TOKEN_STORAGE_KEY)
  } catch { /* 存储不可用时，本次页面会话仍可使用。 */ }
}

export function establishSession(data) {
  if (!data?.token || !data?.user?.id) throw new Error('登录响应不完整，请重试')
  token.value = data.token
  user.value = data.user
  version.value += 1
  persistToken(data.token)
}

export function restoreSessionUser(value, expectedToken) {
  if (token.value !== expectedToken || !expectedToken) return false
  if (!value?.id) throw new Error('用户信息响应不完整，请重试')
  user.value = value
  version.value += 1
  return true
}

export function clearSession(expectedToken) {
  // 旧请求的 401 不能清除后来登录的另一个账号。
  if (expectedToken !== undefined && token.value !== expectedToken) return false
  token.value = ''
  user.value = null
  version.value += 1
  persistToken('')
  return true
}
