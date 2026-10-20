
import axios from "axios"

const request = axios.create({
    baseURL: "http://127.0.0.1:8000",
    timeout: 300000
})

// 当前浏览器页面的会话ID
let sessionId = createSessionId()

function createSessionId() {
    if (typeof crypto !== "undefined" && crypto.randomUUID) {
        return crypto.randomUUID()
    }

    return `${Date.now()}_${Math.random().toString(36).slice(2)}`
}

// 开启新会话时调用
export function resetChatSession() {
    sessionId = createSessionId()
    return sessionId
}

export function chat(query, facilityId) {
    return request.post("/agent/chat", {
        question: query,
        facility_id: facilityId,
        session_id: sessionId
    })
}