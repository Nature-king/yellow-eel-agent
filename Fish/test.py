
import requests
import time
import uuid

API_URL = "http://127.0.0.1:8000/agent/chat"
SESSION_ID = f"final_acceptance_{uuid.uuid4().hex[:8]}"

cases = [
    (
        "水质查询",
        "A001最新的溶氧是多少？"
    ),
    (
        "设备查询",
        "这个池的增氧机最新记录状态是什么？"
    ),
    (
        "综合分析",
        "请综合分析A001最新的水质、投喂和设备状态，并给出处理建议。"
    ),
    (
        "知识库问答",
        "黄鳝养殖中溶氧过低可能带来哪些风险？"
    ),
]

results = []

for name, question in cases:
    print(f"\n========== {name} ==========")

    start = time.perf_counter()

    try:
        response = requests.post(
            API_URL,
            json={
                "question": question,
                "facility_id": "A001",
                "session_id": SESSION_ID
            },
            timeout=300
        )

        elapsed = time.perf_counter() - start
        response.raise_for_status()

        data = response.json()
        answer = data.get("answer", "")

        if isinstance(answer, dict):
            answer = answer.get("content", "")

        passed = (
            isinstance(answer, str)
            and bool(answer.strip())
        )

        print("HTTP状态:", response.status_code)
        print("耗时:", round(elapsed, 2), "秒")
        print("回答长度:", len(answer))
        print("返回内容:")
        print(answer[:1000])

        results.append((name, passed, elapsed))

    except Exception as e:
        print("测试异常:", repr(e))
        results.append((name, False, 0))

print("\n========== 验收汇总 ==========")

for name, passed, elapsed in results:
    print(
        f"{name}: "
        f"{'接口初检通过' if passed else '失败'} "
        f"| {elapsed:.2f}秒"
    )

print(
    f"\n接口初检通过："
    f"{sum(item[1] for item in results)}/{len(results)}"
)

print("本轮Session ID:", SESSION_ID)