import axios from "axios"

const request = axios.create({
    baseURL: "http://127.0.0.1:8000"
})

// 查询投喂记录
export function getFeedData(id) {
    return request.get(`/farm/feed/${id}`)
}

// 查询历史报警
export function getAlarmData(id) {
    return request.get(`/farm/alarm/${id}`)
}

// 查询设备状态
export function getDeviceData(id) {
    return request.get(`/farm/device/${id}`)
}

// 查询水质数据
export function getWaterData(id) {
    return request.get(`/farm/water/${id}`)
}

// 查询养殖池列表
export function getFacilities() {
    return request.get("/farm/facilities")
}

// 新增：检测水质风险并获取主动预警
export function getWaterAlerts(id) {
    return request.get(`/farm/alerts/${id}`)
}