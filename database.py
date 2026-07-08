# database.py
import motor.motor_asyncio
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

class Database:
    def __init__(self):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
        self.db = self.client['bigwin_database']
        
        self.history = self.db['game_history']
        self.predictions = self.db['predictions']
        self.settings = self.db['settings']
        self.users = self.db['users']
        self.bets = self.db['bets']
        self.active_sessions = self.db['active_sessions']
        self.sudo_users = self.db['sudo_users']
        self.user_sessions = self.db['user_sessions']
    
    async def init_indexes(self):
        await self.history.create_index("issue_number", unique=True)
        await self.predictions.create_index("issue_number", unique=True)
        await self.settings.create_index("key", unique=True)
        await self.users.create_index("user_id", unique=True)
        await self.bets.create_index([("user_id", 1), ("issue_number", 1)])
        await self.active_sessions.create_index("user_id", unique=True)
        await self.sudo_users.create_index("user_id", unique=True)
        await self.user_sessions.create_index([("user_id", 1), ("active", 1)])
    
    async def get_user(self, user_id: int) -> dict:
        user = await self.users.find_one({"user_id": user_id})
        if not user:
            user = {
                "user_id": user_id, "balance": 100000.0, "total_bets": 0,
                "total_wins": 0, "total_losses": 0, "total_wagered": 0.0,
                "total_won": 0.0, "profit": 0.0, "win_streak": 0,
                "lose_streak": 0, "best_streak": 0, "session_profit": 0.0,
                "profit_target": 30000.0, "created_at": datetime.now()
            }
            await self.users.insert_one(user)
        return user
    
    async def update_balance(self, user_id: int, amount: float, operation: str = "add") -> dict:
        user = await self.get_user(user_id)
        if operation == "add": new_balance = user["balance"] + amount
        elif operation == "subtract": new_balance = user["balance"] - amount
        elif operation == "set": new_balance = amount
        else: new_balance = user["balance"]
        await self.users.update_one({"user_id": user_id}, {"$set": {"balance": new_balance}})
        user["balance"] = new_balance
        return user
    
    async def update_session_profit(self, user_id: int, profit: float):
        await self.users.update_one({"user_id": user_id}, {"$inc": {"session_profit": profit}})
        return await self.get_user(user_id)
    
    async def reset_session_profit(self, user_id: int):
        await self.users.update_one({"user_id": user_id}, {"$set": {"session_profit": 0.0}})
    
    async def place_bet(self, user_id: int, issue_number: str, bet_amount: float, predicted_size: str, ai_mode: str) -> dict:
        user = await self.get_user(user_id)
        if user["balance"] < bet_amount:
            return {"success": False, "message": "လက်ကျန်ငွေ မလုံလောက်ပါ"}
        existing = await self.bets.find_one({"user_id": user_id, "issue_number": issue_number})
        if existing:
            return {"success": False, "message": "ဤ Period အတွက် လောင်းပြီးသားပါ"}
        await self.update_balance(user_id, bet_amount, "subtract")
        bet = {
            "user_id": user_id, "issue_number": issue_number, "bet_amount": bet_amount,
            "predicted_size": predicted_size, "ai_mode": ai_mode, "actual_size": None,
            "actual_number": None, "result": None, "payout": 0.0, "profit": 0.0,
            "created_at": datetime.now()
        }
        await self.bets.insert_one(bet)
        await self.users.update_one({"user_id": user_id}, {"$inc": {"total_bets": 1, "total_wagered": bet_amount}})
        return {"success": True, "balance": user['balance'] - bet_amount}
    
    async def settle_bets(self, issue_number: str, actual_size: str, actual_number: int) -> list:
        pending = await self.bets.find({"issue_number": issue_number, "result": None}).to_list(length=None)
        settled = []
        for bet in pending:
            user_id = bet["user_id"]
            is_win = (bet["predicted_size"] == actual_size)
            bet_amount = bet["bet_amount"]
            if is_win:
                payout = bet_amount * 1.96; profit = payout - bet_amount; result = "WIN"
                await self.users.update_one({"user_id": user_id}, {"$inc": {"total_wins": 1, "total_won": payout, "profit": profit, "win_streak": 1, "lose_streak": -1}})
                await self.update_session_profit(user_id, profit)
                await self.update_balance(user_id, payout, "add")
            else:
                payout = 0; profit = -bet_amount; result = "LOSE"
                await self.users.update_one({"user_id": user_id}, {"$inc": {"total_losses": 1, "profit": profit, "win_streak": -1, "lose_streak": 1}})
                await self.update_session_profit(user_id, profit)
            await self.bets.update_one({"_id": bet["_id"]}, {"$set": {"actual_size": actual_size, "actual_number": actual_number, "result": result, "payout": payout, "profit": profit, "settled_at": datetime.now()}})
            user = await self.get_user(user_id)
            if user["win_streak"] > user.get("best_streak", 0):
                await self.users.update_one({"user_id": user_id}, {"$set": {"best_streak": user["win_streak"]}})
            settled.append({**bet, "actual_size": actual_size, "actual_number": actual_number, "result": result, "payout": payout, "profit": profit})
        return settled
    
    async def get_user_bets(self, user_id: int, limit: int = 10) -> list:
        return await self.bets.find({"user_id": user_id}).sort("created_at", -1).limit(limit).to_list(length=limit)
    
    async def get_pending_bets_count(self, user_id: int) -> int:
        return await self.bets.count_documents({"user_id": user_id, "result": None})
    
    async def get_sudo_users(self) -> set:
        docs = await self.sudo_users.find({"active": True}).to_list(length=None)
        return {doc["user_id"] for doc in docs}
    
    async def add_sudo(self, user_id: int, added_by: int) -> bool:
        await self.sudo_users.update_one({"user_id": user_id}, {"$set": {"user_id": user_id, "active": True, "added_by": added_by, "added_at": datetime.now()}}, upsert=True)
        return True
    
    async def remove_sudo(self, user_id: int) -> bool:
        await self.sudo_users.update_one({"user_id": user_id}, {"$set": {"active": False, "removed_at": datetime.now()}})
        return True
    
    async def get_active_users(self) -> set:
        docs = await self.active_sessions.find({"active": True}).to_list(length=None)
        return {doc["user_id"] for doc in docs}
    
    async def activate_session(self, user_id: int, ai_mode: str):
        await self.active_sessions.update_one({"user_id": user_id}, {"$set": {"active": True, "activated_at": datetime.now(), "ai_mode": ai_mode}}, upsert=True)
        await self.reset_session_profit(user_id)
    
    async def deactivate_session(self, user_id: int):
        await self.active_sessions.update_one({"user_id": user_id}, {"$set": {"active": False, "stopped_at": datetime.now()}})
    
    async def get_user_session(self, user_id: int) -> dict:
        session = await self.user_sessions.find_one({"user_id": user_id})
        if not session:
            session = {"user_id": user_id, "active": False, "ai_mode": "pattern", "bet_sequence": [100, 300, 900, 2700, 8100], "profit_target": 30000.0, "created_at": datetime.now()}
            await self.user_sessions.insert_one(session)
        return session
    
    async def update_user_ai_mode(self, user_id: int, ai_mode: str):
        await self.user_sessions.update_one({"user_id": user_id}, {"$set": {"ai_mode": ai_mode}}, upsert=True)
        await self.active_sessions.update_one({"user_id": user_id, "active": True}, {"$set": {"ai_mode": ai_mode}})
    
    async def update_profit_target(self, user_id: int, target: float):
        await self.user_sessions.update_one({"user_id": user_id}, {"$set": {"profit_target": target}}, upsert=True)
        await self.users.update_one({"user_id": user_id}, {"$set": {"profit_target": target}})
    
    async def get_setting(self, key: str, default=None):
        doc = await self.settings.find_one({"key": key})
        return doc.get("value", default) if doc else default
    
    async def set_setting(self, key: str, value):
        await self.settings.update_one({"key": key}, {"$set": {"value": value}}, upsert=True)
    
    async def get_leaderboard(self, limit: int = 10) -> list:
        return await self.users.find().sort("balance", -1).limit(limit).to_list(length=limit)
    
    async def get_history(self, limit: int = 5000) -> list:
        return await self.history.find().sort("issue_number", -1).limit(limit).to_list(length=limit)
    
    async def add_history(self, issue_number: str, number: int, size: str):
        await self.history.update_one({"issue_number": issue_number}, {"$setOnInsert": {"number": number, "size": size}}, upsert=True)
    
    async def save_prediction(self, issue_number: str, predicted_size: str, ai_mode: str):
        await self.predictions.update_one({"issue_number": issue_number}, {"$set": {"predicted_size": predicted_size, "ai_mode": ai_mode}}, upsert=True)
    
    async def get_session_predictions(self, start_issue: str) -> list:
        return await self.predictions.find({"issue_number": {"$gte": start_issue}, "win_lose": {"$ne": None}}).sort("issue_number", -1).to_list(length=20)

db = Database()
