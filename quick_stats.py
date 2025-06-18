#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Хурдан эдийн засгийн статистик
"""

import sqlite3
from pathlib import Path

def quick_economy_stats():
    """Хурдан эдийн засгийн статистик гаргах"""
    economy_db = Path(__file__).parent / "data" / "economy.db"
    
    if not economy_db.exists():
        print("❌ economy.db олдсонгүй!")
        return
    
    try:
        conn = sqlite3.connect(economy_db)
        cursor = conn.cursor()
        
        print("💰 MONGOLBOT ЭДИЙН ЗАСГИЙН ХУРДАН СТАТИСТИК")
        print("=" * 60)
        
        # Economy balance
        cursor.execute("""
            SELECT 
                COUNT(*) as users,
                AVG(balance) as avg_balance,
                SUM(balance) as total_balance,
                MIN(balance) as min_balance,
                MAX(balance) as max_balance
            FROM economy
        """)
        economy = cursor.fetchone()
        
        if economy and economy[0] > 0:
            print("💵 ХАЛААСНЫ МӨНГӨ:")
            print(f"   👥 Хэрэглэгч: {economy[0]:,}")
            print(f"   📊 Дундаж: {economy[1]:,.0f} ₮")
            print(f"   💎 Нийт: {economy[2]:,.0f} ₮")
            print(f"   📉 Хамгийн бага: {economy[3]:,.0f} ₮")
            print(f"   📈 Хамгийн их: {economy[4]:,.0f} ₮")
        
        # Bank balance
        cursor.execute("""
            SELECT 
                COUNT(*) as users,
                AVG(balance) as avg_balance,
                SUM(balance) as total_balance,
                MIN(balance) as min_balance,
                MAX(balance) as max_balance
            FROM bank
        """)
        bank = cursor.fetchone()
        if bank and bank[0] > 0:
            print("\n🏦 БАНКНЫ ДАНС:")
            print(f"   👥 Хэрэглэгч: {bank[0]:,}")
            print(f"   📊 Дундаж: {bank[1]:,.0f} ₮")
            print(f"   💎 Нийт: {bank[2]:,.0f} ₮")
            print(f"   📉 Хамгийн бага: {bank[3]:,.0f} ₮")
            print(f"   📈 Хамгийн их: {bank[4]:,.0f} ₮")
        
        # Savings (Хадгаламж) balance
        try:
            cursor.execute("""
                SELECT 
                    COUNT(*) as users,
                    AVG(balance) as avg_balance,
                    SUM(balance) as total_balance,
                    MIN(balance) as min_balance,
                    MAX(balance) as max_balance
                FROM savings
            """)
            savings = cursor.fetchone()
            
            if savings and savings[0] > 0:
                print("\n💰 ХАДГАЛАМЖ:")
                print(f"   👥 Хэрэглэгч: {savings[0]:,}")
                print(f"   📊 Дундаж: {savings[1]:,.0f} ₮")
                print(f"   💎 Нийт: {savings[2]:,.0f} ₮")
                print(f"   📉 Хамгийн бага: {savings[3]:,.0f} ₮")
                print(f"   📈 Хамгийн их: {savings[4]:,.0f} ₮")
        except sqlite3.OperationalError:
            print("\n💰 ХАДГАЛАМЖ: Хүснэгт олдсонгүй")
        
        # Loans (Зээл) balance
        try:
            cursor.execute("""
                SELECT 
                    COUNT(*) as users,
                    AVG(balance) as avg_balance,
                    SUM(balance) as total_balance,
                    MIN(balance) as min_balance,
                    MAX(balance) as max_balance
                FROM loans
            """)
            loans = cursor.fetchone()
            
            if loans and loans[0] > 0:
                print("\n💳 ЗЭЭЛ:")
                print(f"   👥 Зээлтэн: {loans[0]:,}")
                print(f"   📊 Дундаж зээл: {loans[1]:,.0f} ₮")
                print(f"   💸 Нийт зээл: {loans[2]:,.0f} ₮")
                print(f"   📉 Хамгийн бага: {loans[3]:,.0f} ₮")
                print(f"   📈 Хамгийн их: {loans[4]:,.0f} ₮")
        except sqlite3.OperationalError:
            print("\n💳 ЗЭЭЛ: Хүснэгт олдсонгүй")
        
        # Rewards статистик
        try:
            cursor.execute("""
                SELECT 
                    COUNT(*) as users,
                    AVG(streak) as avg_streak,
                    MAX(streak) as max_streak
                FROM rewards
            """)
            rewards = cursor.fetchone()
            
            if rewards and rewards[0] > 0:
                print("\n🎁 ШАГНАЛ СИСТЕМЭ:")
                print(f"   👥 Идэвхтэй хэрэглэгч: {rewards[0]:,}")
                print(f"   📊 Дундаж streak: {rewards[1]:.1f}")
                print(f"   🏆 Хамгийн урт streak: {rewards[2]}")
        except sqlite3.OperationalError:
            print("\n🎁 ШАГНАЛ: Хүснэгт олдсонгүй")
        
        # Top 5 баян хэрэглэгчид
        cursor.execute("""
            SELECT user_id, balance 
            FROM economy 
            ORDER BY balance DESC 
            LIMIT 5
        """)
        top_users = cursor.fetchall()
        
        if top_users:
            print("\n🏆 ТОП 5 БАЯН ХЭРЭГЛЭГЧИД:")
            for i, (user_id, balance) in enumerate(top_users, 1):
                print(f"   {i}. User ID: {user_id} - {balance:,.0f} ₮")
          # Нийт дүгнэлт - БҮХ мөнгийг нэгтгэх
        total_balance = 0
        total_users = economy[0] if economy and economy[0] else 0
        
        if economy:
            total_balance += economy[2] or 0
        if bank:
            total_balance += bank[2] or 0
        
        # Savings нэмэх
        try:
            cursor.execute("SELECT SUM(balance) FROM savings")
            savings_total = cursor.fetchone()[0] or 0
            total_balance += savings_total
        except:
            savings_total = 0
        
        # Loans хасах (зээл нь өр)
        try:
            cursor.execute("SELECT SUM(balance) FROM loans")
            loans_total = cursor.fetchone()[0] or 0
            total_balance -= loans_total  # Зээл нь хасах
        except:
            loans_total = 0
        
        avg_total = total_balance / total_users if total_users > 0 else 0
        
        print(f"\n📊 НИЙТ ДҮГНЭЛТ (БҮХ МӨНГӨ):")
        print(f"   💰 Халаас: {economy[2] if economy else 0:,.0f} ₮")
        print(f"   🏦 Банк: {bank[2] if bank else 0:,.0f} ₮")
        print(f"   💎 Хадгаламж: {savings_total:,.0f} ₮")
        print(f"   💸 Зээл (өр): -{loans_total:,.0f} ₮")
        print(f"   {'─' * 30}")
        print(f"   🌟 НИЙТ хөрөнгө: {total_balance:,.0f} ₮")
        print(f"   📈 Дундаж хөрөнгө: {avg_total:,.0f} ₮")
        print(f"   👥 Идэвхтэй хэрэглэгч: {total_users:,}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Алдаа гарлаа: {e}")

def check_all_tables():
    """Бүх хүснэгтүүдийг шалгах"""
    economy_db = Path(__file__).parent / "data" / "economy.db"
    
    if not economy_db.exists():
        print("❌ economy.db олдсонгүй!")
        return
    
    try:
        conn = sqlite3.connect(economy_db)
        cursor = conn.cursor()
        
        print("📋 ECONOMY.DB-н БҮХ ХҮСНЭГТҮҮД:")
        print("=" * 50)
        
        # Бүх хүснэгтүүдийг олох
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        for table_row in tables:
            table_name = table_row[0]
            print(f"\n📋 {table_name.upper()}:")
            
            # Хүснэгтийн бүтэц
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            print(f"   Багануud: {', '.join(column_names)}")
            
            # Өгөгдлийн тоо
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"   Өгөгдлийн тоо: {count:,}")
            
            # Жишээ өгөгдөл
            if count > 0:
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 2")
                samples = cursor.fetchall()
                for i, sample in enumerate(samples, 1):
                    print(f"   Жишээ {i}: {sample}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Алдаа гарлаа: {e}")

if __name__ == "__main__":
    print("🔍 MONGOLBOT ЭДИЙН ЗАСГИЙН ШИНЖИЛГЭЭ")
    print("=" * 60)
    
    # 1. Хурдан статистик
    quick_economy_stats()
    
    print("\n" + "=" * 60)
    
    # 2. Бүх хүснэгтүүдийн жагсаалт
    check_all_tables()
    check_all_tables()
