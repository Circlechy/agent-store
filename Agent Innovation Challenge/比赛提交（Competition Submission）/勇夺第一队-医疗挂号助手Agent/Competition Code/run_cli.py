import asyncio
import os

from registration_agent.app import RegistrationApp

async def main():
    # Required env: API_BASE, API_KEY, MODEL_PROVIDER, MODEL_NAME
    for k in ("API_BASE", "API_KEY", "MODEL_PROVIDER", "MODEL_NAME"):
        if not os.getenv(k):
            print(f"Missing env var: {k}")

    app = RegistrationApp()
    session_id = app.new_session()

    user_query = input("请输入挂号需求：").strip()
    res = await app.step(session_id=session_id, payload={"user_query": user_query})

    while True:
        for m in list(res.get("messages") or []):
            t = str(m or "").strip()
            if t:
                print("\n" + t)
        if res.get("status") == "need_input":
            t = res.get("type")
            q = res.get("question", "")
            print("\n" + q + "\n")
            if t == "clarify":
                ans = input("请回答：").strip()
                res = await app.step(
                    session_id=session_id,
                    payload={"answer": ans},
                )
                continue
            if t == "doctor_time_select":
                opts = list(res.get("options") or [])
                print("\n=== 推荐医生（3选1）===")
                for i, d in enumerate(opts, 1):
                    hospital = d.get("hospital_name", d.get("hospital", "未提供"))
                    name = d.get("name", "未提供")
                    dept = f"{d.get('primary_department','')} / {d.get('secondary_department','')}"
                    time = d.get("appointment_time", "未提供")
                    print(f"{i}. {name} | {hospital} | {dept} | 建议时间: {time}")
                pick = input("请选择医生编号：").strip()
                try:
                    idx = int(pick) - 1
                except Exception:
                    idx = -1
                res = await app.step(session_id=session_id, payload={"selected_index": idx})
                continue
            if t == "time_select":
                doc = res.get("doctor") or {}
                slots = list(res.get("time_slots") or [])
                print("\n=== 可选坐诊时间 ===")
                print(f"医院: {doc.get('hospital_name', doc.get('hospital', '未提供'))}")
                print(f"医生: {doc.get('name', '未提供')}")
                for i, s in enumerate(slots, 1):
                    print(f"{i}. {s}")
                pick = input("请选择时间编号：").strip()
                try:
                    idx = int(pick) - 1
                except Exception:
                    idx = -1
                chosen = slots[idx] if 0 <= idx < len(slots) else ""
                res = await app.step(session_id=session_id, payload={"selected_time": chosen})
                continue

        if res.get("status") == "done":
            print("\n=== 最终推荐 ===")
            print(res.get("final_response", ""))
            return

        print("\n发生错误：", res)
        return


if __name__ == "__main__":
    asyncio.run(main())
