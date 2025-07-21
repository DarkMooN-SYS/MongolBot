import asyncio
import datetime
from typing import Optional
from ..utils.database import get_async_connection

async def get_balance_from_table(user_id: int, table: str) -> int:
    """Тухайн хэрэглэгчийн балансын мэдээллийг хүснэгтээс авна."""
    conn = await get_async_connection('economy')
    async with conn.execute(f"SELECT balance FROM {table} WHERE user_id=?", (user_id,)) as cursor:
        result = await cursor.fetchone()
    await conn.close()
    return int(result[0]) if result and result[0] is not None else 0

async def get_total_balance(user_id: int) -> int:
    """Хэрэглэгчийн bank, savings, economy бүх балансын нийлбэрийг авна."""
    bank_balance = await get_balance_from_table(user_id, "bank")
    savings_balance = await get_balance_from_table(user_id, "savings")
    user_balance = await get_balance_from_table(user_id, "economy")
    return bank_balance + savings_balance + user_balance

async def calculate_total_tax_for_user(user_id: int) -> int:
    """Хэрэглэгчийн нийт баланс дээр татвар тооцоолно."""
    total = await get_total_balance(user_id)
    return calculate_tax(total)

def calculate_tax(balance: int) -> int:
    """
    Calculate tax based on the following table:
    | Баланс (₮) | Татварын хувь (%) |
    | ₮0–200M    | 0%                |
    | ₮200M–500M | 4%                |
    | ₮500M–1B   | 6%                |
    | ₮1B–2B     | 8%                |
    | ₮2B+       | 20%                |
    """
    brackets = [
        (0, 100_000_000, 0.00),
        (100_000_000, 300_000_000, 0.04),
        (300_000_000, 500_000_000, 0.06),
        (500_000_000, 800_000_000, 0.08),
        (800_000_000, float('inf'), 0.2)
    ]
    tax = 0
    for lower, upper, rate in brackets:
        if balance > lower:
            taxable = min(balance, upper) - lower
            tax += int(taxable * rate)
    return tax


async def tax_all_users():
    """
    Бүх хэрэглэгчийн баланс дээр татвар тооцоолж, economy.db-ээс хасна.
    """
    conn = await get_async_connection('economy')
    async with conn.execute("SELECT user_id FROM economy") as cursor:
        users = await cursor.fetchall()
    users = list(users)
    total_tax = 0
    for (user_id,) in users:
        # Тус бүрийн баланс авна
        bank_balance = await get_balance_from_table(user_id, "bank")
        savings_balance = await get_balance_from_table(user_id, "savings")
        economy_balance = await get_balance_from_table(user_id, "economy")

        # Economy tax
        economy_tax = calculate_tax(economy_balance)
        if economy_tax > 0 and economy_balance >= economy_tax:
            await conn.execute("UPDATE economy SET balance = balance - ? WHERE user_id = ?", (economy_tax, user_id))
            total_tax += economy_tax

        # Bank tax
        bank_tax = calculate_tax(bank_balance)
        if bank_tax > 0 and bank_balance >= bank_tax:
            await conn.execute("UPDATE bank SET balance = balance - ? WHERE user_id = ?", (bank_tax, user_id))
            total_tax += bank_tax

        # Savings tax
        savings_tax = calculate_tax(savings_balance)
        if savings_tax > 0 and savings_balance >= savings_tax:
            await conn.execute("UPDATE savings SET balance = balance - ? WHERE user_id = ?", (savings_tax, user_id))
            total_tax += savings_tax
    await conn.commit()
    await conn.close()
    print(f"Татварын тооцоо дууслаа. {len(users)} хэрэглэгчид шалгав. Нийт хасагдсан: {total_tax:,}₮")

async def get_last_tax_date() -> Optional[datetime.datetime]:
    conn = await get_async_connection('economy')
    async with conn.execute("CREATE TABLE IF NOT EXISTS tax_log (id INTEGER PRIMARY KEY, last_date TEXT)"):
        pass
    async with conn.execute("SELECT last_date FROM tax_log WHERE id=1") as cursor:
        row = await cursor.fetchone()
    await conn.close()
    if row and row[0]:
        try:
            return datetime.datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None
    return None

async def set_last_tax_date():
    conn = await get_async_connection('economy')
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    await conn.execute("CREATE TABLE IF NOT EXISTS tax_log (id INTEGER PRIMARY KEY, last_date TEXT)")
    await conn.execute("INSERT OR REPLACE INTO tax_log (id, last_date) VALUES (1, ?)" , (now,))
    await conn.commit()
    await conn.close()

def start_tax_loop():
    async def tax_loop():
        while True:
            last_date = await get_last_tax_date()
            now = datetime.datetime.now()
            if not last_date or (now - last_date).total_seconds() >= 43200:
                await tax_all_users()
                await set_last_tax_date()
            await asyncio.sleep(3600)  # 1 цаг тутамд шалгана
    asyncio.create_task(tax_loop())

# Bot-ыг ажиллуулах үед start_tax_loop() дуудаарай
