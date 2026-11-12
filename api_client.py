import os, httpx
API_URL=os.getenv("API_URL","https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json?pageNo=1&pageSize=50")
async def fetch_history():
    async with httpx.AsyncClient(timeout=20,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"}) as client:
        response=await client.get(API_URL)
        response.raise_for_status()
        payload=response.json()
    if payload.get("code") != 0:
        raise RuntimeError(f"API returned code={payload.get('code')}: {payload.get('msg')}")
    rows=payload.get("data",{}).get("list",[])
    return rows
