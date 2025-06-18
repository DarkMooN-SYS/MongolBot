#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MongolBot Extension Loader Test
Бүх extension-уудыг загварчлан шалгах скрипт
"""

import sys
import importlib
import traceback

# Extensions list - bot.py-с хуулсан
extensions = [
    # Economy Cogs
    'cogs.economy.bank',
    'cogs.economy.economy', 
    'cogs.economy.serverbank',
    'cogs.economy.vip',
    # Games Cogs
    'cogs.games.buh',
    'cogs.games.horseracing',
    'cogs.games.game',
    
    # Admin Cogs
    'cogs.admin.admin',
    'cogs.admin.owner',
    'cogs.admin.suggest',
    'cogs.admin.giveaway',
    'cogs.admin.fun',
    'cogs.admin.blacklist',
    'cogs.admin.birthday',
    'cogs.admin.report',
    
    # Utils Cogs
    'cogs.utils.support',
    'cogs.utils.help'
]

def test_extensions():
    """Extension-уудыг шалгах"""
    print("🔍 MongolBot Extension-уудыг шалгаж байна...\n")
    
    success_count = 0
    failed_count = 0
    failed_extensions = []
    
    for extension in extensions:
        try:
            # Модулыг импорт хийж үзэх
            module = importlib.import_module(extension)
            
            # setup функц байгаа эсэхийг шалгах
            if hasattr(module, 'setup'):
                print(f"✅ {extension} - OK")
                success_count += 1
            else:
                print(f"⚠️  {extension} - setup функц байхгүй")
                failed_count += 1
                failed_extensions.append(f"{extension} (setup функц байхгүй)")
                
        except ImportError as e:
            print(f"❌ {extension} - Import алдаа: {e}")
            failed_count += 1
            failed_extensions.append(f"{extension} (Import алдаа)")
            
        except Exception as e:
            print(f"🚨 {extension} - Алдаа: {e}")
            failed_count += 1
            failed_extensions.append(f"{extension} (Алдаа: {e})")
    
    print(f"\n📊 Үр дүн:")
    print(f"✅ Амжилттай: {success_count}")
    print(f"❌ Алдаатай: {failed_count}")
    print(f"📈 Бүгд: {len(extensions)}")
    
    if failed_extensions:
        print(f"\n❌ Алдаатай extension-ууд:")
        for ext in failed_extensions:
            print(f"   • {ext}")
    else:
        print(f"\n🎉 Бүх extension амжилттай!")
    
    return success_count, failed_count

if __name__ == "__main__":
    print("🤖 MongolBot Extension Тестийн систем")
    print("=" * 50)
    
    try:
        success, failed = test_extensions()
        
        if failed == 0:
            print(f"\n🌟 Бүх {success} extension бэлэн байна!")
            sys.exit(0)
        else:
            print(f"\n⚠️ {failed} extension-д алдаа байна. Шалгаад засна уу.")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n🚨 Тестийн системд алдаа гарлаа: {e}")
        traceback.print_exc()
        sys.exit(1)
