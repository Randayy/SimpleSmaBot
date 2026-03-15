BOT_TOKEN = "8578407218:AAGE5kM5El_nw0j8O83ErH4VJgMvxbm7rBc"

import json
import os
from fastapi import FastAPI, Request

app = FastAPI()

REG_JSON = "registered_accounts.json"
DEP_JSON = "deposited_accounts.json"


def load_list(path):
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []
    
def load_deposits():
    if not os.path.exists(DEP_JSON):
        return {}
    try:
        with open(DEP_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}
    

def save_deposits(data: dict):
    with open(DEP_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_list(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@app.get("/pocket/postback")
async def pocket_postback(request: Request):
    params = dict(request.query_params)
    print("POSTBACK RECEIVED:", params)

    event = params.get("event")         
    trader_id = params.get("traderid")  
    depo = params.get("depo")  

    if not trader_id or trader_id.startswith("{"):
        return "OK"

    trader_id = str(trader_id).strip()

    # реєстрація
    if event == "registration":
        accounts = load_list(REG_JSON)
        if trader_id not in accounts:
            accounts.append(trader_id)
            save_list(REG_JSON, accounts)
        print("REG ACCOUNTS:", accounts)

    # перший депозит
    if event == "first_deposit":
        deposits = load_deposits()
        # зберігаємо останню відому суму (або тільки перший депозит, як захочеш)
        deposits[trader_id] = str(depo) if depo is not None else "0"
        save_deposits(deposits)
        print("DEP ACCOUNTS:", deposits)
        print(f"deposited: trader_id={trader_id}, sum={depo}")

    return "OK"
    return "OK"
