import json
from datetime import datetime
import aiosqlite
from typing import Optional

from datetime import timedelta

def get_season_expiry(season: str, year: Optional[int] = None) -> Optional[str]:
    """
def get_season_expiry(season: str, year: Optional[int] = None) -> Optional[str]:
    :param season: "spring", "summer", "autumn", "winter"
    :param year: int (optional, default: this year)
    :return: str (YYYY-MM-DD) or None
    """
    # Монголын бүс: UTC+8
    now = datetime.utcnow() + timedelta(hours=8)
    if year is None:
        year = now.year
    # Монгол орны улирлын астрономийн дуусах огноо (жилийн өөрчлөлттэй)
    # Хавар: 3/21 - 6/20, Зун: 6/21 - 9/22, Намар: 9/23 - 12/20, Өвөл: 12/21 - 3/20
    # Дуусах өдөр нь тухайн улирлын сүүлийн өдөр
    if season == "spring":
        return f"{year}-06-20"
    elif season == "summer":
        return f"{year}-09-22"
    elif season == "autumn":
        return f"{year}-12-20"
    elif season == "winter":
        return f"{year+1}-03-20"
    else:
        return None

async def get_active_effects(conn: aiosqlite.Connection, user_id: int) -> dict:
    """
    Хэрэглэгчийн идэвхтэй effect-үүдийг inventory-оос уншина.
    :param conn: aiosqlite.Connection
    :param user_id: int
    :return: dict (effect_name: value)
    """
    effects = {}
    if not isinstance(conn, aiosqlite.Connection):
        raise TypeError("conn must be aiosqlite.Connection")
    try:
        async with conn.execute(
            "SELECT effects, expiry_date FROM user_inventory WHERE user_id = ? AND quantity > 0",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            now = datetime.now()
            for effects_json, expiry_date in rows:
                try:
                    eff = json.loads(effects_json)
                except Exception:
                    continue
                if expiry_date:
                    try:
                        expiry = datetime.strptime(expiry_date, "%Y-%m-%d %H:%M:%S")
                        if expiry < now:
                            continue
                    except Exception:
                        continue
                for k, v in eff.items():
                    # effect-үүдийг хамгийн их утгаар хадгална (shop_discount, cooldown_reduction, interest_multiplier)
                    if k in ["shop_discount", "cooldown_reduction", "interest_multiplier"]:
                        effects[k] = max(effects.get(k, 0), v)
                    else:
                        effects[k] = v
    except Exception as e:
        print(f"[shop_utils] get_active_effects error: {e}")
    return effects

async def is_rob_protected(conn: aiosqlite.Connection, user_id: int) -> bool:
    """
    Хэрэглэгч rob protection идэвхтэй эсэхийг шалгана.
    """
    effects = await get_active_effects(conn, user_id)
    return bool(effects.get("rob_protection", False))

async def is_hack_protected(conn: aiosqlite.Connection, user_id: int) -> bool:
    """
    Хэрэглэгч hack protection идэвхтэй эсэхийг шалгана.
    """
    effects = await get_active_effects(conn, user_id)
    return bool(effects.get("hack_protection", False))

async def get_auto_money(conn: aiosqlite.Connection, user_id: int) -> dict:
    """
    Хэрэглэгчийн auto_money effect-ийг авна.
    """
    effects = await get_active_effects(conn, user_id)
    if "auto_money" in effects:
        return {
            "amount": int(effects["auto_money"]),
            "interval_hours": int(effects.get("interval_hours", 6)),
            "expires": int(effects.get("duration_days", 0)) if effects.get("duration_days") else None
        }
    return {}

async def has_auto_claim_daily(conn: aiosqlite.Connection, user_id: int) -> bool:
    """
    Хэрэглэгчийн auto_claim_daily effect идэвхтэй эсэхийг шалгана.
    """
    effects = await get_active_effects(conn, user_id)
    return bool(effects.get("auto_claim_daily", False))

async def get_shop_discount(conn: aiosqlite.Connection, user_id: int) -> float:
    """
    Хэрэглэгчийн shop discount effect-ийг авна.
    """
    effects = await get_active_effects(conn, user_id)
    return float(effects.get("shop_discount", 0))

# --- Effect summary utility ---
async def get_effects_summary(conn: aiosqlite.Connection, user_id: int) -> str:
    """
    Хэрэглэгчийн идэвхтэй effect-үүдийг таньж, Монгол хэлээр тайлбарлан буцаана.
    """
    effects = await get_active_effects(conn, user_id)
    summary = []
    if effects.get("rob_protection"):
        summary.append("Хулгайгаас хамгаалалт идэвхтэй.")
    if effects.get("hack_protection"):
        summary.append("Хакерын хамгаалалт идэвхтэй.")
    if effects.get("auto_claim_daily"):
        summary.append("Өдөр бүрийн шагналыг автоматаар авч байна.")
    if effects.get("auto_money"):
        amount = effects.get("auto_money")
        interval = effects.get("interval_hours", 6)
        summary.append(f"{interval} цаг тутамд автоматаар {amount:,}₮ олж авна.")
    if effects.get("shop_discount", 0) > 0:
        percent = int(effects.get("shop_discount", 0) * 100)
        summary.append(f"Дэлгүүрийн бүх зүйлсийг {percent}% хямд үнээр авах боломжтой.")
    if effects.get("random_box"):
        uses = effects.get("uses", 1)
        summary.append(f"Санамсаргүй хайрцаг: {uses} удаа нээх боломжтой.")
    # Duration info
    if effects.get("duration_days"):
        summary.append(f"Үргэлжлэх хугацаа: {effects.get('duration_days')} хоног.")
    return "\n".join(summary) if summary else "Идэвхтэй effect алга."

# --- Effect comparison utility ---
async def compare_user_effects(conn: aiosqlite.Connection, user1_id: int, user2_id: int) -> str:
    """
    Хоёр хэрэглэгчийн идэвхтэй effect-үүдийг харьцуулж, Монгол хэлээр ялгаа, төстэйг тайлбарлана.
    """
    eff1 = await get_active_effects(conn, user1_id)
    eff2 = await get_active_effects(conn, user2_id)
    all_keys = set(eff1.keys()) | set(eff2.keys())
    summary = []
    for k in sorted(all_keys):
        v1 = eff1.get(k)
        v2 = eff2.get(k)
        if v1 == v2:
            if v1 is not None:
                summary.append(f"Ижил: {k} — {v1}")
        else:
            if v1 is not None and v2 is not None:
                summary.append(f"Ялгаа: {k} — Хэрэглэгч1: {v1}, Хэрэглэгч2: {v2}")
            elif v1 is not None:
                summary.append(f"Зөвхөн Хэрэглэгч1: {k} — {v1}")
            elif v2 is not None:
                summary.append(f"Зөвхөн Хэрэглэгч2: {k} — {v2}")
    # Hack protection special summary
    if eff1.get("hack_protection") and eff2.get("hack_protection"):
        summary.append("Ижил: Хакерын хамгаалалт идэвхтэй.")
    elif eff1.get("hack_protection"):
        summary.append("Зөвхөн Хэрэглэгч1: Хакерын хамгаалалт идэвхтэй.")
    elif eff2.get("hack_protection"):
        summary.append("Зөвхөн Хэрэглэгч2: Хакерын хамгаалалт идэвхтэй.")
    return "\n".join(summary) if summary else "Идэвхтэй effect-үүдийн ялгаа алга."

# --- Usage Example ---
#
# How to interact with shop effects from any cog:
#
# from cogs.utils.shop_utils import get_effects_summary
# from ..utils.db_helper import get_async_connection
#
# async def show_user_effects(ctx, user_id):
#     conn = await get_async_connection('economy')
#     summary = await get_effects_summary(conn, user_id)
#     await ctx.send(f"Таны идэвхтэй effect-үүд:\n{summary}")
