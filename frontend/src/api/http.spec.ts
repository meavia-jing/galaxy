import axios, { type AxiosResponse } from 'axios'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { apiGet, getAccessToken, http, refreshAccessToken, setAccessToken } from '@/api/http'

afterEach(() => {
  setAccessToken(null)
  http.defaults.adapter = undefined
  document.cookie = 'csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT'
})

describe('http 客户端', () => {
  it('[UNIT-FE-06][I02-T02] 并发调用只触发一次 refresh（单飞）', async () => {
    let release: (value: unknown) => void = () => undefined
    const pending = new Promise((resolve) => {
      release = resolve
    })
    const post = vi.spyOn(axios, 'post').mockReturnValue(pending as never)

    const first = refreshAccessToken()
    const second = refreshAccessToken()
    expect(post).toHaveBeenCalledTimes(1)

    release({ data: { data: { access: 'fresh-token' }, request_id: 'rid' } })

    await expect(Promise.all([first, second])).resolves.toEqual(['fresh-token', 'fresh-token'])
    expect(getAccessToken()).toBe('fresh-token')
  })

  it('[UNIT-FE-06][I02-T02] refresh 失败返回 null 且不缓存失败结果', async () => {
    const post = vi
      .spyOn(axios, 'post')
      .mockRejectedValueOnce(new Error('refresh down'))
      .mockResolvedValueOnce({ data: { data: { access: 'token-after-retry' }, request_id: 'r' } })

    await expect(refreshAccessToken()).resolves.toBeNull()
    await expect(refreshAccessToken()).resolves.toBe('token-after-retry')
    expect(post).toHaveBeenCalledTimes(2)
  })

  it('[UNIT-FE-07][I02-T02] 自动注入 X-CSRFToken 与 Bearer 头', async () => {
    document.cookie = 'csrftoken=csrf-abc'
    setAccessToken('access-1')

    let captured: Record<string, unknown> = {}
    http.defaults.adapter = async (config): Promise<AxiosResponse> => {
      const headers = config.headers as unknown as {
        get?: (name: string) => unknown
      } & Record<string, unknown>
      captured = {
        csrf: headers.get ? headers.get('X-CSRFToken') : headers['X-CSRFToken'],
        auth: headers.get ? headers.get('Authorization') : headers['Authorization'],
      }
      return {
        data: { data: { ok: true }, request_id: 'r1' },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      }
    }

    await apiGet('/users/me/')

    expect(captured.csrf).toBe('csrf-abc')
    expect(captured.auth).toBe('Bearer access-1')
  })
})
