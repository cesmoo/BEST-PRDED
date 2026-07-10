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
        self.users = self.db['users']
        self.bets = self.db['bets']
        self.active_sessions = self.db['active_sessions']
        self.sudo_users = self.db['sudo_users']
        self.user_sessions = self.db['user_sessions']
    
    async def init_indexes(self):
        await self.history.create_index("issue_number", unique=True)
        await self.users.create_index("user_id", unique=True)
        await self.bets.create_index([("user_id", 1), ("issue_number", 1)])
        await self.active_sessions.create_index("user_id", unique=True)
    
    async def get_user(self, user_id: int) -> dict:
        user = await self.users.find_one({"user_id": user_id})
        if not user:
            user = {
                "user_id": user_id, "balance": 100000.0, "total_bets": 0,
                "profit": 0.0, "session_profit": 0.0, "created_at": datetime.now()
            }
            await self.users.insert_one(user)
        return user
    
    async def update_balance(self, user_id: int, amount: float, operation: str = "add") -> dict:
        user = await self.get_user(user_id)
        if operation == "add": new_balance = user["balance"] + amount
        elif operation == "subtract": new_balance = user["balance"] - amount
        await self.users.update_one({"user_id": user_id}, {"$set": {"balance": new_balance}})
        user["balance"] = new_balance
        return user
    
    async def place_bet(self, user_id: int, issue_number: str, bet_amount: float, predicted_size: str, ai_mode: str):
        await self.update_balance(user_id, bet_amount, "subtract")
        bet = {
            "user_id": user_id, "issue_number": issue_number, "bet_amount": bet_amount,
            "predicted_size": predicted_size, "ai_mode": ai_mode, "actual_number": None, "result": None,
            "profit": 0.0, "created_at": datetime.now()
        }
        await self.bets.insert_one(bet)
    
    async def settle_bets(self, issue_number: str, actual_size: str, actual_number: int) -> list:
        pending = await self.bets.find({"issue_number": issue_number, "result": None}).to_list(length=None)
        settled = []
        for bet in pending:
            user_id = bet["user_id"]
            is_win = (bet["predicted_size"] == actual_size)
            bet_amount = bet["bet_amount"]
            
            if is_win:
                payout = bet_amount * 1.96
                profit = payout - bet_amount
                result = "WIN"
                await self.update_balance(user_id, payout, "add")
                await self.users.update_one({"user_id": user_id}, {"$inc": {"session_profit": profit}})
            else:
                payout = 0
                profit = -bet_amount
                result = "LOSE"
                await self.users.update_one({"user_id": user_id}, {"$inc": {"session_profit": profit}})
                
            await self.bets.update_one({"_id": bet["_id"]}, {"$set": {"actual_size": actual_size, "actual_number": actual_number, "result": result, "profit": profit}})
            settled.append({**bet, "actual_size": actual_size, "actual_number": actual_number, "result": result, "profit": profit})
        return settled
    
    async def get_user_bets(self, user_id: int, limit: int = 30) -> list:
        return await self.bets.find({"user_id": user_id}).sort("created_at", -1).limit(limit).to_list(length=limit)
    
    async def get_sudo_users(self) -> set:
        return set()
    
    async def get_active_users(self) -> set:
        docs = await self.active_sessions.find({"active": True}).to_list(length=None)
        return {doc["user_id"] for doc in docs}
    
    async def activate_session(self, user_id: int, ai_mode: str):
        await self.active_sessions.update_one({"user_id": user_id}, {"$set": {"active": True}}, upsert=True)
    
    async def deactivate_session(self, user_id: int):
        await self.active_sessions.update_one({"user_id": user_id}, {"$set": {"active": False}})
    
    async def get_user_session(self, user_id: int) -> dict:
        session = await self.user_sessions.find_one({"user_id": user_id})
        if not session:
            session = {"ai_mode": "ensemble", "bet_sequence": [100, 300, 900, 2700, 8100, 24300]}
        return session

    async def get_history(self, limit: int = 100) -> list:
        return await self.history.find().sort("issue_number", -1).limit(limit).to_list(length=limit)
    
    async def add_history(self, issue_number: str, number: int, size: str):
        await self.history.update_one({"issue_number": issue_number}, {"$setOnInsert": {"number": number, "size": size}}, upsert=True)

db = Database()
