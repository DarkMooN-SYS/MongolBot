#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MongolBot өгөгдлийн сангийн шинжилгээ хийх скрипт
Ашиглалт: python db_analyzer.py
"""

import sqlite3
import os
import json
from datetime import datetime
from pathlib import Path

class MongolBotDBAnalyzer:
    def __init__(self):
        self.data_dir = Path("mongolbot/data")
        self.results = {}
        
    def find_database_files(self):
        """Бүх .db файлуудыг олох"""
        db_files = []
        if self.data_dir.exists():
            db_files.extend(list(self.data_dir.glob("*.db")))
        
        # Root дээрх .db файлууд
        root_files = list(Path(".").glob("*.db"))
        db_files.extend(root_files)
        
        return db_files
    
    def analyze_database(self, db_path):
        """Тодорхой өгөгдлийн сангийн бүтцийг шинжлэх"""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            db_name = db_path.name
            result = {"db_name": db_name, "tables": []}
            
            # Хүснэгтүүдийг олох
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            for table_row in tables:
                table_name = table_row[0]
                
                # Хүснэгтийн бүтэц
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                
                # Өгөгдлийн тоо
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                
                # Жишээ өгөгдөл
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
                sample = cursor.fetchall()
                
                table_info = {
                    "name": table_name,
                    "columns": [{"name": col[1], "type": col[2], "pk": bool(col[5])} for col in columns],
                    "count": count,
                    "sample": sample
                }
                
                result["tables"].append(table_info)
            
            conn.close()
            return result
            
        except Exception as e:
            print(f"❌ {db_path.name} шинжлэхэд алдаа: {e}")
            return None
    
    def analyze_economy_details(self):
        """Economy.db дэлгэрэнгүй шинжилгээ"""
        economy_db = self.data_dir / "economy.db"
        if not economy_db.exists():
            print("⚠️ economy.db олдсонгүй")
            return None
            
        try:
            conn = sqlite3.connect(economy_db)
            cursor = conn.cursor()
            analysis = {}
            
            # Economy balance статистик
            try:
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_users,
                        AVG(balance) as avg_balance,
                        SUM(balance) as total_balance,
                        MIN(balance) as min_balance,
                        MAX(balance) as max_balance
                    FROM economy
                """)
                economy_stats = cursor.fetchone()
                if economy_stats:
                    analysis["economy_balance"] = {
                        "total_users": economy_stats[0],
                        "avg_balance": round(economy_stats[1] or 0, 2),
                        "total_balance": economy_stats[2] or 0,
                        "min_balance": economy_stats[3] or 0,
                        "max_balance": economy_stats[4] or 0
                    }
            except:
                pass
            
            # Bank balance статистик
            try:
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_users,
                        AVG(balance) as avg_balance,
                        SUM(balance) as total_balance,
                        MIN(balance) as min_balance,
                        MAX(balance) as max_balance
                    FROM bank
                """)
                bank_stats = cursor.fetchone()
                if bank_stats:
                    analysis["bank_balance"] = {
                        "total_users": bank_stats[0],
                        "avg_balance": round(bank_stats[1] or 0, 2),
                        "total_balance": bank_stats[2] or 0,
                        "min_balance": bank_stats[3] or 0,
                        "max_balance": bank_stats[4] or 0
                    }
            except:
                pass
            
            # Top 10 баян хэрэглэгчид
            try:
                cursor.execute("""
                    SELECT user_id, balance 
                    FROM economy 
                    ORDER BY balance DESC 
                    LIMIT 10
                """)
                top_users = cursor.fetchall()
                analysis["top_users"] = [{"user_id": user[0], "balance": user[1]} for user in top_users]
            except:
                pass
            
            # Rewards статистик
            try:
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_users,
                        AVG(streak) as avg_streak,
                        MAX(streak) as max_streak
                    FROM rewards
                """)
                rewards_stats = cursor.fetchone()
                if rewards_stats:
                    analysis["rewards"] = {
                        "total_users": rewards_stats[0],
                        "avg_streak": round(rewards_stats[1] or 0, 2),
                        "max_streak": rewards_stats[2] or 0
                    }
            except:
                pass
                
            conn.close()
            return analysis
            
        except Exception as e:
            print(f"❌ Economy шинжилгээнд алдаа: {e}")
            return None
    
    def print_results(self):
        """Үр дүнг хэвлэх"""
        print("=" * 70)
        print("📊 MONGOLBOT ӨГӨГДЛИЙН САНГИЙН ТАЙЛАН")
        print("=" * 70)
        print(f"🕐 Огноо: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Хүснэгтүүдийн жагсаалт
        for db_name, db_data in self.results.items():
            if db_name == "economy_analysis":
                continue
                
            print(f"🗂️  {db_data['db_name'].upper()}")
            print("─" * 50)
            
            for table in db_data["tables"]:
                print(f"📋 {table['name']} ({table['count']:,} өгөгдөл)")
                columns = [col['name'] for col in table['columns']]
                print(f"   Багануud: {', '.join(columns)}")
                
                if table['sample']:
                    print(f"   Жишээ: {table['sample'][0] if table['sample'] else 'Хоосон'}")
                print()
        
        # Economy дэлгэрэнгүй статистик
        if "economy_analysis" in self.results:
            analysis = self.results["economy_analysis"]
            
            print("=" * 70)
            print("💰 ЭДИЙН ЗАСГИЙН ДЭЛГЭРЭНГҮЙ СТАТИСТИК")
            print("=" * 70)
            
            if "economy_balance" in analysis:
                stats = analysis["economy_balance"]
                print("💵 ХАЛААСНЫ МӨНГӨ (Economy):")
                print(f"   👥 Нийт хэрэглэгч: {stats['total_users']:,}")
                print(f"   📊 Дундаж баланс: {stats['avg_balance']:,.0f} ₮")
                print(f"   💎 Нийт мөнгө: {stats['total_balance']:,.0f} ₮")
                print(f"   📉 Хамгийн бага: {stats['min_balance']:,.0f} ₮")
                print(f"   📈 Хамгийн их: {stats['max_balance']:,.0f} ₮")
                print()
            
            if "bank_balance" in analysis:
                stats = analysis["bank_balance"]
                print("🏦 БАНКНЫ ДАНС:")
                print(f"   👥 Нийт хэрэглэгч: {stats['total_users']:,}")
                print(f"   📊 Дундаж баланс: {stats['avg_balance']:,.0f} ₮")
                print(f"   💎 Нийт мөнгө: {stats['total_balance']:,.0f} ₮")
                print(f"   📉 Хамгийн бага: {stats['min_balance']:,.0f} ₮")
                print(f"   📈 Хамгийн их: {stats['max_balance']:,.0f} ₮")
                print()
            
            if "rewards" in analysis:
                stats = analysis["rewards"]
                print("🎁 ШАГНАЛ СИСТЕМЭ:")
                print(f"   👥 Идэвхтэй хэрэглэгч: {stats['total_users']:,}")
                print(f"   📊 Дундаж streak: {stats['avg_streak']:.1f}")
                print(f"   🏆 Хамгийн урт streak: {stats['max_streak']}")
                print()
            
            # Нийт дүн тооцоо
            economy_total = analysis.get("economy_balance", {}).get("total_balance", 0)
            bank_total = analysis.get("bank_balance", {}).get("total_balance", 0)
            total_balance = economy_total + bank_total
            
            economy_users = analysis.get("economy_balance", {}).get("total_users", 0)
            avg_total = total_balance / economy_users if economy_users > 0 else 0
            
            print("=" * 50)
            print("📈 НИЙТ ДҮГНЭЛТ:")
            print(f"   💰 Нийт хөрөнгө: {total_balance:,.0f} ₮")
            print(f"   📊 Хэрэглэгч тутмын дундаж: {avg_total:,.0f} ₮")
            print(f"   👥 Идэвхтэй хэрэглэгч: {economy_users:,}")
            print()
            
            # Top хэрэглэгчид
            if "top_users" in analysis and analysis["top_users"]:
                print("🏆 ТОП 10 БАЯН ХЭРЭГЛЭГЧИД:")
                for i, user in enumerate(analysis["top_users"], 1):
                    print(f"   {i:2d}. User ID: {user['user_id']} - {user['balance']:,.0f} ₮")
                print()
    
    def save_results(self):
        """Үр дүнг файлд хадгалах"""
        # Reports фолдер үүсгэх
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = reports_dir / f"database_analysis_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        
        print(f"💾 Тайлан хадгалагдлаа: {filename}")
    
    def run_analysis(self):
        """Бүгдийг нэгэн зэрэг шинжлэх"""
        print("🔍 МонголБотын өгөгдлийн сан шинжилж байна...")
        print()
        
        # .db файлуудыг олох
        db_files = self.find_database_files()
        
        if not db_files:
            print("❌ .db файл олдсонгүй!")
            return
        
        print(f"📁 Олдсон өгөгдлийн сангийн файлууд: {len(db_files)}")
        
        # Бүх .db файлуудыг шинжлэх
        for db_file in db_files:
            try:
                result = self.analyze_database(db_file)
                if result:
                    self.results[result['db_name']] = result
                    print(f"✅ {result['db_name']} - {len(result['tables'])} хүснэгт")
                else:
                    print(f"❌ {db_file.name} - шинжлэх боломжгүй")
            except Exception as e:
                print(f"❌ {db_file.name} - алдаа: {e}")
        
        # Economy.db дэлгэрэнгүй шинжилгээ
        economy_analysis = self.analyze_economy_details()
        if economy_analysis:
            self.results["economy_analysis"] = economy_analysis
        
        print()
        self.print_results()
        self.save_results()

def main():
    """Үндсэн функц"""
    analyzer = MongolBotDBAnalyzer()
    analyzer.run_analysis()

if __name__ == "__main__":
    main()
