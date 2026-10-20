<script setup>


function alarmTypeText(type) {
    const typeMap = {
        HIGH_TEMP: "水温过高",
        LOW_TEMP: "水温过低",
        LOW_OXYGEN: "溶氧不足",
        ABNORMAL_PH: "pH异常",
        HIGH_AMMONIA: "氨氮偏高"
    }

    return typeMap[type] || type
}



import {
    ref,
    computed,
    onMounted,
    onUnmounted,
    nextTick
}
from "vue"


import MarkdownIt from "markdown-it"


import WaterCard from "./components/WaterCard.vue"

import WaterChart from "./components/WaterChart.vue"



import {
    chat,
    resetChatSession
}
from "./api/agent"



import {
    getWaterData,
    getFeedData,
    getAlarmData,
    getDeviceData,
    getFacilities,
    getWaterAlerts
} from "./api/farm"






const md = new MarkdownIt()





// =====================
// 养殖池
// =====================


const facilities=ref([])


const facilityId=ref(
"A001"
)







// =====================
// 数据
// =====================


const water=ref({

temperature:"--",

oxygen:"--",

ph:"--",

ammonia:"--"

})




const waterTrend=ref([])





const feeding=ref({

feed_amount:"--",

eat_rate:"--"

})





const alarm=ref({

alarm_count:0,

alarms:[]

})

const waterAlerts = ref({
    status: "loading",
    message: "正在检查水质数据",
    data_time: null,
    alerts: [],
    alarm_count: 0,
    new_alarm_count: 0
})




const device=ref({

devices:[]

})

// 设备卡片只展示每种设备的最新一条有效时间记录。
// 时间统一为 YYYY-MM-DD HH:mm:ss 时可以按字符串比较；
// 无时间的记录不会覆盖有时间的记录。
const latestDevices = computed(() => {
    const rows = Array.isArray(device.value?.devices) ? device.value.devices : []
    const latestByName = new Map()
    for (const row of rows) {
        if (!row || typeof row !== "object") continue
        const name = row.device_name || "未知设备"
        const time = String(row.update_time ?? row.record_time ?? "")
        const previous = latestByName.get(name)
        const previousTime = String(previous?.update_time ?? previous?.record_time ?? "")
        if (!previous || time > previousTime || time === previousTime) {
            latestByName.set(name, row)
        }
    }
    return Array.from(latestByName.values())
})

const feedingRecordTime = computed(() => {
    return feeding.value?.record_time || feeding.value?.time || null
})








// =====================
// RAG来源
// =====================


const sources=ref([])









// =====================
// 状态判断
// =====================


function waterStatus(type, value) {
    // 缺失数据不能直接当作 0
    if (
        value === null ||
        value === undefined ||
        value === "" ||
        value === "--"
    ) {
        return "暂无数据"
    }

    const v = Number(value)

    if (!Number.isFinite(v)) {
        return "暂无数据"
    }

    if (type === "temperature") {
        if (v > 30) return "⚠ 水温偏高"
        if (v < 20) return "⚠ 水温偏低"
        return "正常"
    }

    if (type === "oxygen") {
        if (v < 2) return "🔴 溶氧高风险"
        if (v < 3) return "⚠ 溶氧偏低"
        return "正常"
    }

    if (type === "ph") {
        if (v < 6.5 || v > 8.5) {
            return "⚠ pH异常"
        }
        return "正常"
    }

    if (type === "ammonia") {
        if (v >= 0.2) return "⚠ 氨氮偏高"
        return "正常"
    }

    return ""
}









// =====================
// 加载数据
// =====================


async function loadData(){

// 加载主动水质预警
try {
    const alertRes = await getWaterAlerts(facilityId.value)
    waterAlerts.value = alertRes.data
} catch (e) {
    console.error("主动预警加载失败", e)

    waterAlerts.value = {
        status: "error",
        message: "主动预警暂时不可用",
        alerts: [],
        alarm_count: 0,
        new_alarm_count: 0
    }
}





  

try{


let waterRes =
await getWaterData(
facilityId.value
)



water.value =
waterRes.data.latest
||
water.value



waterTrend.value =
waterRes.data.trend
||
[]





let feedRes =
await getFeedData(
facilityId.value
)


feeding.value =
feedRes.data.latest
||
feeding.value







let alarmRes =
await getAlarmData(
facilityId.value
)


alarm.value =
alarmRes.data
||
alarm.value







let deviceRes =
await getDeviceData(
facilityId.value
)


device.value =
deviceRes.data
||
device.value





console.log(
"刷新:",
facilityId.value
)


}


catch(e){

console.error(
"数据加载失败",
e
)

}


}








// =====================
// 自动刷新
// =====================


let timer=null



onMounted(() => {
    loadFacilities()
    loadData()

    timer = setInterval(() => {
        loadData()
    }, 30000)
})

onUnmounted(() => {
    clearInterval(timer)
    if (aiTimer !== null) clearInterval(aiTimer)
})

// =====================
// AI
// =====================


const question = ref("")
const loading = ref(false)
const elapsedSeconds = ref(0)
const lastQueryFacility = ref("")
const messages = ref([])
const chatContainer = ref(null)
let aiTimer = null
let messageSequence = 0

function scrollToLatest() {
    nextTick(() => {
        const el = chatContainer.value
        if (el) el.scrollTop = el.scrollHeight
    })
}

function startNewChat() {
    if (loading.value) return
    resetChatSession()
    messages.value = []
    question.value = ""
    elapsedSeconds.value = 0
    lastQueryFacility.value = ""
}

// 池号切换不应悄悄沿用上一池的对话上下文
function onFacilityChange() {
    startNewChat()
    loadData()
}

async function send() {
    const userQuestion = question.value.trim()
    if (!userQuestion || loading.value) return

    const currentFacility = facilityId.value
    const id = ++messageSequence
    const assistantMessage = {
        id: `assistant-${id}`,
        role: "assistant",
        text: "",
        sources: [],
        duration: null,
        facility: currentFacility,
        error: false,
        pending: true
    }

    messages.value.push({
        id: `user-${id}`,
        role: "user",
        text: userQuestion
    }, assistantMessage)
    const assistantEntry = messages.value[messages.value.length - 1]
    question.value = ""
    loading.value = true
    elapsedSeconds.value = 0
    lastQueryFacility.value = currentFacility
    scrollToLatest()

    const startTime = performance.now()
    if (aiTimer !== null) clearInterval(aiTimer)
    aiTimer = setInterval(() => {
        elapsedSeconds.value = Math.floor((performance.now() - startTime) / 1000)
    }, 1000)

    try {
        const res = await chat(userQuestion, currentFacility)
        const rawAnswer = res.data?.answer
        let text = ""
        if (typeof rawAnswer === "string") {
            text = rawAnswer
        } else if (rawAnswer && typeof rawAnswer.content === "string") {
            text = rawAnswer.content
        } else if (rawAnswer && typeof rawAnswer.answer === "string") {
            text = rawAnswer.answer
        } else {
            throw new Error("AI返回的数据格式异常")
        }

        const rawSources = Array.isArray(res.data?.sources)
            ? res.data.sources
            : rawAnswer?.sources
        assistantEntry.text = text
        assistantEntry.sources = Array.isArray(rawSources) ? rawSources : []
    } catch (e) {
        console.error("AI请求失败", e)
        const timedOut = e?.code === "ECONNABORTED" || e?.code === "ETIMEDOUT"
        assistantEntry.error = true
        assistantEntry.text = timedOut
            ? "AI分析请求超时，请稍后重试。"
            : e?.message === "AI返回的数据格式异常"
                ? "AI返回的数据格式异常，请检查后端响应。"
                : "AI服务暂时不可用，请检查后端服务或稍后重试。"
    } finally {
        assistantEntry.duration = (performance.now() - startTime) / 1000
        assistantEntry.pending = false
        loading.value = false
        if (aiTimer !== null) {
            clearInterval(aiTimer)
            aiTimer = null
        }
        scrollToLatest()
    }
}


function formatNumber(v){


let n =
Number(v)


if(isNaN(n))

return "--"



return n.toFixed(2)


}






function renderMarkdown(v) {

    if (v === null || v === undefined || v === "") {
        return ""
    }

    // 正常字符串直接渲染
    if (typeof v === "string") {
        return md.render(v)
    }

    // 兼容嵌套回答对象
    if (
        typeof v === "object" &&
        typeof v.answer === "string"
    ) {
        return md.render(v.answer)
    }

    // 其他类型避免引发Vue渲染异常
    console.error("Markdown数据类型异常：", v)

    return "AI回答数据格式异常"
}


async function loadFacilities(){


let res =
await getFacilities()


facilities.value =
res.data.data


}



</script>






<template>


<div class="page">



<header>


<h1>
🐟 智慧鳝养 Agent
</h1>


<p>
智能养殖监控与AI决策系统
</p>





<div class="select-box">


当前养殖池：


<select

v-model="facilityId"

:disabled="loading"

@change="onFacilityChange"

>


<option

v-for="item in facilities"

:key="item.id"

:value="item.id"

>

{{item.name}}

</option>


</select>



</div>



</header>









<!-- 水质 -->
 <div class="water-meta">
    <span>
        最近监测时间：{{ water.time || "--" }}
    </span>

    <span
        v-if="waterAlerts.status === 'stale'"
        class="stale-text"
    >
        ⚠ 数据已过期
    </span>

    <span
        v-else-if="waterAlerts.status === 'success'"
        class="fresh-text"
    >
        ✓ 数据检测正常
    </span>
</div>

<div class="cards">



<WaterCard

title="水温"

:value="formatNumber(water.temperature)"

unit="℃"

:status="waterStatus('temperature',water.temperature)"

/>



<WaterCard

title="溶氧"

:value="formatNumber(water.oxygen)"

unit="mg/L"

:status="waterStatus('oxygen',water.oxygen)"

/>



<WaterCard

title="pH"

:value="formatNumber(water.ph)"

unit=""

:status="waterStatus('ph',water.ph)"

/>



<WaterCard

title="氨氮"

:value="formatNumber(water.ammonia)"

unit="mg/L"

:status="waterStatus('ammonia',water.ammonia)"

/>


</div>









<div class="business">


<div class="panel">

<h3>
🍚 投喂情况
</h3>


<p>
最近投喂：
{{formatNumber(feeding.feed_amount)}} kg
</p>


<p>
摄食率：
{{formatNumber(feeding.eat_rate)}} %
</p>
<p class="record-time">记录时间：{{ feedingRecordTime || "暂无记录时间" }}</p>


</div>





<div class="panel">

<h3>
⚙️设备状态
</h3>


<p

v-for="d in latestDevices"

:key="d.device_name"

>

{{d.device_name}}

:

{{d.status}}
<span class="record-time">（{{ d.update_time || d.record_time || "时间未知" }}）</span>

</p>
<p v-if="latestDevices.length === 0" class="record-time">暂无设备记录</p>



</div>






<div class="panel">
    <h3>🚨风险告警</h3>

    <!-- 主动水质预警 -->
    <h4>水质主动检测</h4>

    <p v-if="waterAlerts.status === 'loading'">
        正在检查水质数据……
    </p>

    <p
        v-else-if="waterAlerts.status === 'stale'"
        style="color: #d97706;"
    >
        ⚠️ 水质数据已过期，暂不生成实时预警
    </p>

    <p
        v-else-if="waterAlerts.status === 'invalid_time'"
        style="color: #dc2626;"
    >
        ⚠️ 水质数据时间异常
    </p>

    <p
        v-else-if="waterAlerts.status === 'error'"
        style="color: #dc2626;"
    >
        {{ waterAlerts.message || '主动预警暂时不可用' }}
    </p>

    <template v-else>
        <p>
            检测到异常：{{ waterAlerts.alarm_count }} 项
        </p>

        <div
            v-for="(item, index) in waterAlerts.alerts"
            :key="item.type + index"
        >
            <p>
                {{ item.level === 'HIGH' ? '🔴 高风险' : '🟠 中风险' }}
                · {{ alarmTypeText(item.type) }}
            </p>
            <p>{{ item.message }}</p>
        </div>

        <p v-if="waterAlerts.alerts.length === 0">
            ✅ 当前有效数据未发现配置规则中的异常
        </p>
    </template>

    <hr />

    <!-- 历史报警 -->
    <h4>历史报警记录</h4>

    <p>历史告警：{{ alarm.alarm_count }} 条</p>

  
<p
    v-for="(a, index) in alarm.alarms"
    :key="a.time + a.type + index"
>
    🔴 {{ alarmTypeText(a.type) }}
</p>

    <p v-if="!alarm.alarms.length">
        暂无历史报警
    </p>
</div>



</div>









<div class="bottom">



<div class="chart-panel">


<h3>
水质变化趋势
</h3>


<WaterChart

:trend="waterTrend"

/>


</div>








<div class="chat">
    <div class="chat-header">
        <h3>AI智能分析助手</h3>
        <button type="button" class="new-chat-btn" :disabled="loading" @click="startNewChat">新会话</button>
    </div>

    <div ref="chatContainer" class="answer chat-history" role="log" aria-label="AI聊天记录">
        <div v-if="messages.length === 0" class="empty">
            请输入黄鳝养殖问题，让AI进行分析
        </div>
        <div v-for="item in messages" :key="item.id" class="message-row" :class="item.role">
            <div class="message-bubble" :class="{ 'message-error': item.error }">
                <div class="message-label">{{ item.role === 'user' ? '我' : 'AI助手' }}</div>
                <div v-if="item.pending" class="loading" role="status">
                    <p>正在分析 {{ item.facility }} 的业务数据，已等待 {{ elapsedSeconds }} 秒……</p>
                    <p v-if="elapsedSeconds >= 20" class="loading-hint">复杂分析可能需要更长时间，请勿重复提交。</p>
                </div>
                <div v-else-if="item.role === 'assistant'" class="markdown" v-html="renderMarkdown(item.text)"></div>
                <div v-else class="user-text">{{ item.text }}</div>
                <div v-if="!item.pending && item.role === 'assistant' && item.duration !== null" class="message-meta">
                    {{ item.facility }} · 耗时 {{ item.duration.toFixed(1) }} 秒
                </div>
                <div v-if="item.sources && item.sources.length" class="source">
                    <strong>知识库来源</strong>
                    <div v-for="(source, index) in item.sources" :key="index">
                        {{ String(source).split(/[\\/]/).pop() }}
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="input chat-input">
        <input v-model="question" @keyup.enter="send" :disabled="loading" placeholder="请输入养殖问题，按 Enter 发送" />
        <button type="button" @click="send" :disabled="loading || !question.trim()">
            {{ loading ? '分析中' : '发送' }}
        </button>
    </div>
</div>

</div>

</div>

</template>







<style scoped>

.water-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    margin: 10px 4px 0;
    font-size: 13px;
    color: #777;
}

.stale-text {
    color: #d97706;
    font-weight: 600;
}

.fresh-text {
    color: #16a34a;
    font-weight: 600;
}


.page{


width:1100px;

margin:auto;

padding:25px;

background:#f5f7fa;


}




header{

text-align:center;

}




h1{

font-size:36px;

}




.select-box{


font-size:20px;

margin-top:10px;


}



select{


padding:6px 20px;

border-radius:8px;


}




.cards{


display:grid;

grid-template-columns:
repeat(4,1fr);

gap:15px;

margin-top:25px;


}






.business{


display:grid;

grid-template-columns:
repeat(3,1fr);

gap:15px;

margin-top:20px;


}




.panel,
.chart-panel,
.chat{


background:white;

border-radius:18px;

padding:20px;


}






.bottom{


display:grid;

grid-template-columns:
1fr 1fr;

gap:20px;

margin-top:20px;


}






.input{


display:flex;

gap:10px;

}



input{


flex:1;

height:36px;

padding:0 10px;

}




button{


width:80px;

background:#409eff;

color:white;

border:none;

border-radius:6px;


}




.answer{

min-height:120px;

max-height:420px;

overflow:auto;

background:#fafafa;

padding:15px;

margin-top:15px;

border-radius:12px;

}

.empty{

height:80px;

display:flex;

align-items:center;

justify-content:center;

color:#aaa;

font-size:14px;

}



.markdown{

font-size:14px;

line-height:1.6;

}



.source{


margin-top:10px;

background:#eef7ff;

padding:10px;

color:#409eff;

}


.loading-hint {
    margin-top: 8px;
    font-size: 12px;
    color: #64748b;
}

.analysis-meta {
    margin: 8px 4px 0;
    color: #777;
    font-size: 12px;
}

button:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}


/* Step 21: 多轮聊天 */
.chat-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 12px;
}
.chat-header h3 { margin: 0; }
.new-chat-btn {
    width: auto;
    min-width: 70px;
    padding: 8px 12px;
    background: #edf5ff;
    color: #2563eb;
    border: 1px solid #cfe2ff;
    cursor: pointer;
}
.chat-history {
    height: 420px;
    max-height: 420px;
    min-height: 180px;
    overflow-y: auto;
    scroll-behavior: smooth;
}
.message-row { display: flex; margin: 12px 0; }
.message-row.user { justify-content: flex-end; }
.message-row.assistant { justify-content: flex-start; }
.message-bubble {
    max-width: 94%;
    min-width: 0;
    padding: 11px 13px;
    border-radius: 12px;
    background: #fff;
    border: 1px solid #e5e7eb;
    overflow-wrap: anywhere;
}
.message-row.user .message-bubble {
    max-width: 84%;
    background: #eaf3ff;
    border-color: #d7e8ff;
}
.message-label { font-size: 12px; color: #64748b; margin-bottom: 6px; font-weight: 600; }
.user-text { font-size: 14px; line-height: 1.6; white-space: pre-wrap; }
.message-meta { margin-top: 8px; color: #64748b; font-size: 12px; }
.message-error { border-color: #fecaca; }
.chat-input { margin-top: 12px; }
.chat-input input { min-width: 0; }
.chat-input button { cursor: pointer; }
.markdown :deep(p) { margin: 0 0 8px; }
.markdown :deep(p:last-child) { margin-bottom: 0; }
.markdown :deep(ul), .markdown :deep(ol) { padding-left: 20px; }
.markdown :deep(table) { display: block; overflow-x: auto; border-collapse: collapse; max-width: 100%; }
.markdown :deep(th), .markdown :deep(td) { border: 1px solid #e5e7eb; padding: 5px 8px; }
.markdown :deep(pre) { overflow-x: auto; padding: 8px; background: #f1f5f9; }
@media (max-width: 900px) {
    .page { width: auto; max-width: 1100px; padding: 15px; }
    .bottom { grid-template-columns: 1fr; }
    .cards { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .business { grid-template-columns: 1fr; }
}


/* Step 22：数据时间与紧凑聊天排版 */
.record-time { color: #64748b; font-size: 12px; line-height: 1.5; }
.chat-history { padding: 12px; }
.message-row { margin: 8px 0; }
.message-bubble { padding: 9px 12px; text-align: left; }
.message-row.assistant .message-bubble { max-width: 96%; }
.message-row.user .message-bubble { max-width: 82%; }
.message-label { text-align: left; margin-bottom: 3px; font-size: 11px; }
.user-text, .markdown { text-align: left; overflow-wrap: anywhere; }
.message-meta { text-align: right; margin-top: 5px; }
.markdown :deep(h1), .markdown :deep(h2), .markdown :deep(h3) { text-align: left; line-height: 1.4; margin: 10px 0 6px; }
.markdown :deep(ul), .markdown :deep(ol) { text-align: left; margin: 5px 0 9px; }
.markdown :deep(li) { margin: 3px 0; }
.markdown :deep(p) { text-align: left; }

</style>