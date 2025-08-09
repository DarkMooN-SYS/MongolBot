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
    Calculate tax based on the following progressive tax table:
    | Баланс (₮)     | Татварын хувь (%) |
    | ₮0–200M        | 0%                |
    | ₮200M–500M     | 2%                |
    | ₮500M–1B       | 4%                |
    | ₮1B–2B         | 6%                |
    | ₮2B–5B         | 8%                |
    | ₮5B+           | 12%               |
    """
    brackets = [
        (0, 200_000_000, 0.00),           # 0-200M: 0%
        (200_000_000, 500_000_000, 0.02), # 200M-500M: 2%
        (500_000_000, 1_000_000_000, 0.04), # 500M-1B: 4%
        (1_000_000_000, 2_000_000_000, 0.06), # 1B-2B: 6%
        (2_000_000_000, 5_000_000_000, 0.08), # 2B-5B: 8%
        (5_000_000_000, float('inf'), 0.12)   # 5B+: 12%
    ]
    
    if balance <= 0:
        return 0
    
    tax = 0
    for lower, upper, rate in brackets:
        if balance > lower:
            taxable = min(balance, upper) - lower
            tax += int(taxable * rate)
        if balance <= upper:
            break
    
    return max(0, tax)  # Ensure tax is never negative


async def tax_all_users():
    """
    Бүх хэрэглэгчийн баланс дээр татвар тооцоолж, economy.db-ээс хасна.
    """
    print("🏛️ Татварын тооцоо эхэллээ...")
    
    conn = await get_async_connection('economy')
    try:
        async with conn.execute("SELECT user_id FROM economy") as cursor:
            users = await cursor.fetchall()
        users = list(users)
        
        total_tax_collected = 0
        users_taxed = 0
        tax_breakdown = {
            'economy': 0,
            'bank': 0,  
            'savings': 0
        }
        
        for (user_id,) in users:
            try:
                # Тус бүрийн баланс авна
                bank_balance = await get_balance_from_table(user_id, "bank")
                savings_balance = await get_balance_from_table(user_id, "savings")
                economy_balance = await get_balance_from_table(user_id, "economy")
                
                user_total_tax = 0

                # Economy tax
                economy_tax = calculate_tax(economy_balance)
                if economy_tax > 0 and economy_balance >= economy_tax:
                    await conn.execute("UPDATE economy SET balance = balance - ? WHERE user_id = ?", (economy_tax, user_id))
                    total_tax_collected += economy_tax
                    user_total_tax += economy_tax
                    tax_breakdown['economy'] += economy_tax

                # Bank tax
                bank_tax = calculate_tax(bank_balance)
                if bank_tax > 0 and bank_balance >= bank_tax:
                    await conn.execute("UPDATE bank SET balance = balance - ? WHERE user_id = ?", (bank_tax, user_id))
                    total_tax_collected += bank_tax
                    user_total_tax += bank_tax
                    tax_breakdown['bank'] += bank_tax

                # Savings tax
                savings_tax = calculate_tax(savings_balance)
                if savings_tax > 0 and savings_balance >= savings_tax:
                    await conn.execute("UPDATE savings SET balance = balance - ? WHERE user_id = ?", (savings_tax, user_id))
                    total_tax_collected += savings_tax
                    user_total_tax += savings_tax
                    tax_breakdown['savings'] += savings_tax
                
                if user_total_tax > 0:
                    users_taxed += 1
                    
            except Exception as e:
                print(f"❌ Хэрэглэгч {user_id}-д татвар тооцоолохад алдаа гарлаа: {e}")
                continue
        
        await conn.commit()
        
        # Дэлгэрэнгүй тайлан
        print(f"✅ Татварын тооцоо амжилттай дууслаа!")
        print(f"📊 Нийт хэрэглэгч: {len(users)}")
        print(f"💰 Татвар төлсөн хэрэглэгч: {users_taxed}")
        print(f"💸 Нийт цуглуулсан татвар: {total_tax_collected:,}₮")
        print(f"📈 Дэлгэрэнгүй задаргаа:")
        print(f"   • Economy данс: {tax_breakdown['economy']:,}₮")
        print(f"   • Bank данс: {tax_breakdown['bank']:,}₮") 
        print(f"   • Savings данс: {tax_breakdown['savings']:,}₮")
        
    except Exception as e:
        print(f"❌ Татварын тооцоонд ерөнхий алдаа гарлаа: {e}")
    finally:
        await conn.close()

async def preview_tax_collection():
    """
    Татварын тооцооллыг урьдчилан үзүүлнэ (бодитоор хасахгүй).
    """
    print("🔍 Татварын урьдчилсан тооцоолол...")
    
    conn = await get_async_connection('economy')
    try:
        async with conn.execute("SELECT user_id FROM economy") as cursor:
            users = await cursor.fetchall()
        users = list(users)
        
        total_tax_preview = 0
        users_to_be_taxed = 0
        tax_breakdown = {
            'economy': 0,
            'bank': 0,  
            'savings': 0
        }
        wealth_distribution = {
            '0-200M': 0,
            '200M-500M': 0,
            '500M-1B': 0,
            '1B-2B': 0,
            '2B-5B': 0,
            '5B+': 0
        }
        
        for (user_id,) in users:
            try:
                bank_balance = await get_balance_from_table(user_id, "bank")
                savings_balance = await get_balance_from_table(user_id, "savings") 
                economy_balance = await get_balance_from_table(user_id, "economy")
                total_user_wealth = bank_balance + savings_balance + economy_balance
                
                # Баялгийн хуваарилалт (шинэ систем: 0-200M татваргүй)
                if total_user_wealth < 200_000_000:
                    wealth_distribution['0-200M'] += 1
                elif total_user_wealth < 500_000_000:
                    wealth_distribution['200M-500M'] += 1
                elif total_user_wealth < 1_000_000_000:
                    wealth_distribution['500M-1B'] += 1
                elif total_user_wealth < 2_000_000_000:
                    wealth_distribution['1B-2B'] += 1
                elif total_user_wealth < 5_000_000_000:
                    wealth_distribution['2B-5B'] += 1
                else:
                    wealth_distribution['5B+'] += 1
                
                user_total_tax = 0
                
                # Татварын тооцоолол
                economy_tax = calculate_tax(economy_balance)
                bank_tax = calculate_tax(bank_balance)
                savings_tax = calculate_tax(savings_balance)
                
                if economy_tax > 0 and economy_balance >= economy_tax:
                    total_tax_preview += economy_tax
                    user_total_tax += economy_tax
                    tax_breakdown['economy'] += economy_tax
                
                if bank_tax > 0 and bank_balance >= bank_tax:
                    total_tax_preview += bank_tax
                    user_total_tax += bank_tax
                    tax_breakdown['bank'] += bank_tax
                
                if savings_tax > 0 and savings_balance >= savings_tax:
                    total_tax_preview += savings_tax
                    user_total_tax += savings_tax
                    tax_breakdown['savings'] += savings_tax
                
                if user_total_tax > 0:
                    users_to_be_taxed += 1
                    
            except Exception as e:
                print(f"❌ Хэрэглэгч {user_id}-д тооцоолол хийхэд алдаа: {e}")
                continue
        
        print(f"📊 ТАТВАРЫН УРЬДЧИЛСАН ТАЙЛАН:")
        print(f"   👥 Нийт хэрэглэгч: {len(users)}")
        print(f"   💰 Татвар төлөх хэрэглэгч: {users_to_be_taxed}")
        print(f"   💸 Цуглуулагдах татвар: {total_tax_preview:,}₮")
        print(f"   📈 Данс тус бүрээр:")
        print(f"      • Economy: {tax_breakdown['economy']:,}₮")
        print(f"      • Bank: {tax_breakdown['bank']:,}₮")
        print(f"      • Savings: {tax_breakdown['savings']:,}₮")
        print(f"   🏛️ Баялгийн хуваарилалт:")
        for bracket, count in wealth_distribution.items():
            percentage = (count / len(users)) * 100 if users else 0
            print(f"      • {bracket}: {count} хэрэглэгч ({percentage:.1f}%)")
        
    except Exception as e:
        print(f"❌ Урьдчилсан тооцоололд алдаа гарлаа: {e}")
    finally:
        await conn.close()

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

def start_tax_loop(tax_interval_hours: int = 12, check_interval_minutes: int = 30):
    """
    Татварын давтагдах циклийг эхлүүлнэ.
    
    Args:
        tax_interval_hours: Татвар авах давтамж (цагаар) - default 12 цаг
        check_interval_minutes: Шалгах давтамж (минутаар) - default 30 минут
    """
    async def tax_loop():
        print(f"🚀 Татварын систем эхэллээ (татвар: {tax_interval_hours} цаг тутам, шалгах: {check_interval_minutes} минут тутам)")
        
        while True:
            try:
                last_date = await get_last_tax_date()
                now = datetime.datetime.now()
                
                if not last_date:
                    print("📅 Анхны татварын тооцоолол хийгдэх болно...")
                    await preview_tax_collection()  # Эхлээд урьдчилсан тооцоолол
                    await tax_all_users()
                    await set_last_tax_date()
                else:
                    time_since_last_tax = (now - last_date).total_seconds()
                    tax_interval_seconds = tax_interval_hours * 3600
                    
                    if time_since_last_tax >= tax_interval_seconds:
                        print(f"⏰ Татварын цаг болж ({tax_interval_hours} цаг өндөрлөө)")
                        await tax_all_users()
                        await set_last_tax_date()
                    else:
                        remaining_time = tax_interval_seconds - time_since_last_tax
                        hours = int(remaining_time // 3600)
                        minutes = int((remaining_time % 3600) // 60)
                        print(f"⏳ Дараагийн татвар: {hours}ц {minutes}м хүлээнэ үү")
                        
            except Exception as e:
                print(f"❌ Татварын циклд алдаа гарлаа: {e}")
            
            await asyncio.sleep(check_interval_minutes * 60)  # Минутыг секунд болгох
    
    asyncio.create_task(tax_loop())

# Bot-ыг ажиллуулах үед start_tax_loop() дуудаарай
# Жишээ: start_tax_loop(tax_interval_hours=24, check_interval_minutes=60)  # Өдөр тутам, цаг тутамд шалгах

def test_tax_calculations():
    """Татварын тооцооллыг шалгах тест функц"""
    test_cases = [
        (0, 0),                    # 0₮ → 0₮ татвар
        (50_000_000, 0),          # 50M₮ → 0₮ татвар  
        (100_000_000, 0),         # 100M₮ → 0₮ татвар (0-200M-ын 0%)
        (200_000_000, 0),         # 200M₮ → 0₮ татвар (0-200M-ын 0%)
        (300_000_000, 2_000_000), # 300M₮ → 2M₮ татвар (200M-300M-ын 2% = 100M * 2%)
        (500_000_000, 6_000_000), # 500M₮ → 6M₮ татвар (200M-500M-ын 2% = 300M * 2%)
        (1_000_000_000, 26_000_000), # 1B₮ → 26M₮ татвар (300M*2% + 500M*4% = 6M + 20M)
        (5_000_000_000, 326_000_000), # 5B₮ → 326M₮ татвар (6M+20M+60M+240M)
        (10_000_000_000, 926_000_000), # 10B₮ → 926M₮ татвар (6M+20M+60M+240M+600M)
    ]
    
    print("🧮 ТАТВАРЫН ТООЦООЛЛЫН ТЕСТ (Шинэ система: 0-200M = 0%):")
    print("=" * 50)
    
    for balance, expected in test_cases:
        calculated = calculate_tax(balance)
        status = "✅" if calculated == expected else "❌"
        print(f"{status} {balance:,}₮ → {calculated:,}₮ татвар (хүлээгдсэн: {expected:,}₮)")
        
        if calculated != expected:
            print(f"    ⚠️ Алдаа: {abs(calculated - expected):,}₮ ялгаа")
    
    print("=" * 50)

# Тест ажиллуулах: test_tax_calculations()
