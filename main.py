from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
import csv

cred = credentials.Certificate("./serviceAccountKey.json")
firebase_admin.initialize_app(
    cred,
    {
        "databaseURL": "https://personal-finance-tracker-21752-default-rtdb.asia-southeast1.firebasedatabase.app"
    },
)

ref = db.reference("/users")

origins = [
    "http://localhost:8000",
    "http://localhost:3000",
    "https://personal-finance-tracker-web.vercel.app/",
    "http://personal-finance-tracker-web.vercel.app/"
]


class Cash(BaseModel):
    t: str
    title: str
    amount: str
    description: str
    category: str
    payment_mode: str
    date: str
    time: str
    marked: str

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def sortDate(data):
    return sorted(
        data,
        key=lambda item: datetime.strptime(
            str(item["date"] + " " + item["time"]), "%Y-%m-%d %H:%M:%S"
        ),
        reverse=True,
    )

@app.get("/")
def greet():
    return {"message": "Hello World"}

@app.put("/cash/{uid}/{currency}")
async def cash(uid: str, currency: str, cash: Cash):
    user_ref = ref.child(f"{uid}/logs")
    if cash.title == "":
        raise HTTPException(status_code=400, detail="Title cannot be empty.")
    if cash.amount == "":
        raise HTTPException(status_code=400, detail="Amount cannot be empty.")
    if cash.description == "":
        raise HTTPException(status_code=400, detail="Description cannot be empty.")
    if cash.category == "":
        raise HTTPException(status_code=400, detail="Category cannot be empty.")
    if cash.payment_mode == "":
        raise HTTPException(status_code=400, detail="Payment Mode cannot be empty.")
    else:
        today = datetime.today()
        cash.date = today.strftime("%Y-%m-%d")
        cash.time = today.strftime("%H:%M:%S")
        if currency == "USD":
            cash.amount = str(int(cash.amount)*80)
        elif currency == "EUR":
            cash.amount = str(int(cash.amount)*90)
        elif currency == "GBP":
            cash.amount = str(int(cash.amount)*105)
        cash.marked = "false"
        user_ref.push(cash.__dict__)


@app.get("/account_data/{uid}")
async def account_data(uid: str):
    user_ref = ref.child(f"{uid}/logs")
    full_data = user_ref.get()
    total_in = 0
    total_out = 0

    if full_data is not None:
        for i in full_data:
            if full_data[i]["t"] == "cashin":
                total_in += float(full_data[i]["amount"])
            elif full_data[i]["t"] == "cashout":
                total_out += float(full_data[i]["amount"])

        net_balance = total_in - total_out
        return {
            "net_balance": net_balance,
            "total_in": total_in,
            "total_out": total_out,
        }
    else:
        return {"status_code": 404, "data": "Opps.. No account data found"}


@app.get("/get_logs/{uid}")
async def get_logs(uid: str):
    user_ref = ref.child(f"{uid}/logs")
    full_data = user_ref.get()
    if full_data is not None:
        for i in full_data:
            full_data[i]["key"] = i
        sortedData = sortDate([full_data[i] for i in full_data])
        return sortedData
    else:
        return {"status_code": 404, "data": "Opps.. No logs found"}


@app.get("/get_flogs/{uid}/{filtertype}/{label}")
async def get_flogs(uid: str, filtertype: str, label: str):
    user_ref = ref.child(f"{uid}/logs")
    full_data = user_ref.get()
    if full_data is not None:
        for i in full_data:
            full_data[i]["key"] = i
        sortedData = sortDate([full_data[i] for i in full_data])
        filteredData = []
        if filtertype == "category":
            for i in sortedData:
                if i["category"] == label:
                    filteredData.append(i)
        elif filtertype == "payment_mode":
            for i in sortedData:
                if i["payment_mode"] == label:
                    filteredData.append(i)
        elif filtertype == "t":
            for i in sortedData:
                if i["t"] == label:
                    filteredData.append(i)
        elif filtertype == "marked":
            for i in sortedData:
                if i["marked"] == label:
                    filteredData.append(i)
        if filteredData == []:
            return {"status_code": 404, "data": "Opps.. No logs found"}
        return filteredData
    else:
        return {"status_code": 404, "data": "Opps.. No logs found"}

@app.put("/report_download/{uid}")
async def report_download(uid: str, request: Request):
    currentData = await request.json()
    keys = ["Date", "Time", "Type", "Title", "Amount", "Description", "Category", "Payment Mode", ""]
    values = [[str(i["date"]),i["time"],i["t"],i["title"],i["amount"],i["description"],i["category"],i["payment_mode"]] for i in currentData["data"]]

    file = open(f"{uid}.csv", "w", newline="")
    writer = csv.writer(file)
    writer.writerow(keys)
    writer.writerows(values)
    file.close()

    headers = {'Access-Control-Expose-Headers': 'Content-Disposition'}
    return FileResponse(f"{uid}.csv", filename=f"{uid}.csv", headers=headers)

@app.put("/set_goal/{uid}")
async def set_goal(uid:str, request: Request):
    currentData = await request.json()
    user_ref = ref.child(f"{uid}/goals")
    print(currentData)
    if currentData["goalName"] == "":
        raise HTTPException(status_code=400, detail="Title cannot be empty.")
    if currentData["goalAmount"] == "":
        raise HTTPException(status_code=400, detail="Amount cannot be empty.")
    else:
        user_ref.push(currentData)

@app.get("/get_goals/{uid}")
async def get_goals(uid:str):
    user_ref = ref.child(f"{uid}/goals")
    goals_dict = user_ref.get()
    if goals_dict is not None:
        for i in goals_dict:
            goals_dict[i]["key"] = i
        goals = [goals_dict[i] for i in goals_dict]
        return goals
    else:
        return {"status_code": 404, "data": "No goals found"}
    
@app.get("/remove_goal/{uid}/{key}")
async def remove_goal(uid:str, key: str):
    user_ref = ref.child(f"{uid}/goals/{key}")
    user_ref.set({})

@app.get("/bookmark/{uid}/{key}")
async def bookmark(uid:str, key: str):
    user_ref = ref.child(f"{uid}/logs/{key}")
    prev = user_ref.get()
    if prev["marked"] == "false":
        user_ref.update({"marked": "true"})
    elif prev["marked"] == "true":
        user_ref.update({"marked": "false"})