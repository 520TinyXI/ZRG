import sqlite3
import random
from datetime import datetime, timedelta
from pathlib import Path

# --- 静态游戏数据定义 ---
# 定义了所有可用的宠物类型及其基础属性、进化路径
PET_TYPES = {
    "碧波兽": {
        "attribute": "水",
        "description": "由纯净之水汇聚而成的元素精灵，性格温和，防御出众。",
        "initial_stats": {"attack": 8, "defense": 12},
        "evolutions": {
            1: {"name": "碧波兽", "evolve_level": 30},
            2: {"name": "瀚海蛟", "evolve_level": None}
        }
    },
    "烈焰": {
        "attribute": "火",
        "description": "体内燃烧着不灭之火的幼犬，活泼好动，攻击性强。",
        "initial_stats": {"attack": 12, "defense": 8},
        "evolutions": {
            1: {"name": "烈焰", "evolve_level": 30},
            2: {"name": "炽焰龙", "evolve_level": None}
        }
    },
    "莲莲草": {
        "attribute": "草",
        "description": "能进行光合作用的奇特猫咪，攻守均衡，喜欢打盹。",
        "initial_stats": {"attack": 10, "defense": 10},
        "evolutions": {
            1: {"name": "莲莲草", "evolve_level": 30},
            2: {"name": "百草王", "evolve_level": None}
        }
    },
    "碎裂岩": {
        "attribute": "土",
        "description": "坚如磐石的大地精灵，拥有极高的防御力。",
        "initial_stats": {"attack": 6, "defense": 14},
        "evolutions": {
            1: {"name": "碎裂岩", "evolve_level": 30},
            2: {"name": "岩脊守护者", "evolve_level": None}
        }
    },
    "金刚": {
        "attribute": "金",
        "description": "金属构成的战斗机器，攻击力极强。",
        "initial_stats": {"attack": 14, "defense": 6},
        "evolutions": {
            1: {"name": "金刚", "evolve_level": 30},
            2: {"name": "破甲金刚", "evolve_level": None}
        }
    }
}

# --- 静态游戏数据定义 (状态中文名映射) ---
STAT_MAP = {
    "exp": "经验值",
    "mood": "心情值",
    "satiety": "饱食度"
}

class PetSystem:
    def __init__(self, plugin):
        self.plugin = plugin
        self.db_path = plugin.db_path
        
    def _init_database(self):
        """初始化数据库，创建宠物表。"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pets (
                    user_id INTEGER NOT NULL,
                    group_id INTEGER NOT NULL,
                    pet_name TEXT NOT NULL,
                    pet_type TEXT NOT NULL,
                    level INTEGER DEFAULT 1,
                    exp INTEGER DEFAULT 0,
                    mood INTEGER DEFAULT 100,
                    satiety INTEGER DEFAULT 80,
                    attack INTEGER DEFAULT 10,
                    defense INTEGER DEFAULT 10,
                    evolution_stage INTEGER DEFAULT 1,
                    last_fed_time TEXT,
                    last_walk_time TEXT,
                    last_duel_time TEXT,
                    money INTEGER DEFAULT 50,
                    last_updated_time TEXT,
                    PRIMARY KEY (user_id, group_id)
                )
            """)
            
            # 创建背包表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    user_id INTEGER NOT NULL,
                    group_id INTEGER NOT NULL,
                    item_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    PRIMARY KEY (user_id, group_id, item_name)
                )
            """)
            conn.commit()
            
    def _get_pet(self, user_id: str, group_id: str) -> dict | None:
        """
        根据ID获取宠物信息，并自动处理离线期间的状态衰减。
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 先从数据库获取原始数据
            cursor.execute("SELECT * FROM pets WHERE user_id = ? AND group_id = ?", (int(user_id), int(group_id)))
            row = cursor.fetchone()
            if not row:
                return None

            pet_dict = dict(row)
            now = datetime.now()

            # 初始化或获取上次更新时间
            last_updated_str = pet_dict.get('last_updated_time')
            if not last_updated_str:
                last_updated_time = now
                # 首次为新字段写入当前时间
                cursor.execute("UPDATE pets SET last_updated_time = ? WHERE user_id = ? AND group_id = ?",
                               (now.isoformat(), int(user_id), int(group_id)))
            else:
                last_updated_time = datetime.fromisoformat(last_updated_str)

            # 计算离线时间并应用衰减
            hours_passed = (now - last_updated_time).total_seconds() / 3600
            if hours_passed >= 1:
                hours_to_decay = int(hours_passed)
                satiety_decay = 3 * hours_to_decay  # 每小时降低3点饱食度
                mood_decay = 2 * hours_to_decay  # 每小时降低2点心情

                # 计算新值，确保不低于0
                new_satiety = max(0, pet_dict['satiety'] - satiety_decay)
                new_mood = max(0, pet_dict['mood'] - mood_decay)

                # 更新数据库
                cursor.execute(
                    "UPDATE pets SET satiety = ?, mood = ?, last_updated_time = ? WHERE user_id = ? AND group_id = ?",
                    (new_satiety, new_mood, now.isoformat(), int(user_id), int(group_id))
                )
                # 更新返回给程序的字典
                pet_dict['satiety'] = new_satiety
                pet_dict['mood'] = new_mood

            conn.commit()

            # 补全其他可能为空的时间戳
            pet_dict.setdefault('last_fed_time', now.isoformat())
            pet_dict.setdefault('last_walk_time', now.isoformat())
            pet_dict.setdefault('last_duel_time', now.isoformat())

            return pet_dict
            
    def _exp_for_next_level(self, level: int) -> int:
        """计算升到下一级所需的总经验。"""
        return int(10 * (level ** 1.5))
        
    def _check_level_up(self, user_id: str, group_id: str) -> list[str]:
        """
        检查并处理宠物升级，此函数现在返回一个包含升级消息的列表，而不是直接发送。
        接收str类型的ID。
        """
        level_up_messages = []
        while True:
            pet = self._get_pet(user_id, group_id)
            if not pet:
                break

            exp_needed = self._exp_for_next_level(pet['level'])
            if pet['exp'] >= exp_needed:
                new_level = pet['level'] + 1
                remaining_exp = pet['exp'] - exp_needed
                new_attack = pet['attack'] + random.randint(1, 2)
                new_defense = pet['defense'] + random.randint(1, 2)

                with sqlite3.connect(self.db_path) as conn:
                    # 在更新数据库时，将str转换为int
                    conn.execute(
                        "UPDATE pets SET level = ?, exp = ?, attack = ?, defense = ? WHERE user_id = ? AND group_id = ?",
                        (new_level, remaining_exp, new_attack, new_defense, int(user_id), int(group_id))
                    )
                    conn.commit()

                level_up_messages.append(f"🎉 恭喜！你的宠物「{pet['pet_name']}」升级到了 Lv.{new_level}！")
            else:
                break
        return level_up_messages
        
    async def adopt_pet(self, event: AstrMessageEvent, pet_name: str | None = None):
        """领养一只随机的初始宠物"""
        user_id, group_id = event.get_sender_id(), event.get_group_id()
        if not group_id:
            yield event.plain_result("该功能仅限群聊使用哦。")
            return

        if self._get_pet(user_id, group_id):
            yield event.plain_result("你在这个群里已经有一只宠物啦！发送 /我的宠物 查看。")
            return

        initial_pet_types = ["烈焰", "碧波兽", "莲莲草", "碎裂岩", "金刚"]
        type_name = random.choice(initial_pet_types)

        if not pet_name:
            pet_name = type_name

        pet_info = PET_TYPES[type_name]
        stats = pet_info['initial_stats']
        now = datetime.now()
        cooldown_expired_time_iso = (now - timedelta(hours=2)).isoformat()
        now_iso = now.isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO pets (user_id, group_id, pet_name, pet_type, attack, defense, 
                                     last_fed_time, last_walk_time, last_duel_time, money) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (int(user_id), int(group_id), pet_name, type_name, stats['attack'], stats['defense'],
                 now_iso, cooldown_expired_time_iso, cooldown_expired_time_iso, 50))
            conn.commit()

        yield event.plain_result(
            f"恭喜你，{event.get_sender_name()}！命运让你邂逅了「{pet_name}」({type_name})！\n发送 /我的宠物 查看它的状态吧。")
        
    async def my_pet_status(self, event: AstrMessageEvent):
        user_id, group_id = event.get_sender_id(), event.get_group_id()

        if not group_id:
            yield event.plain_result("该功能仅限群聊使用哦。")
            return

        pet = self._get_pet(user_id, group_id)
        if not pet:
            yield event.plain_result("你还没有宠物哦，快发送 /领养宠物 来选择一只吧！")
            return

        result = self.plugin.image_generator._generate_pet_status_image(pet, event.get_sender_name())
        if isinstance(result, Path):
            yield event.image_result(str(result))
        else:
            yield event.plain_result(result)
            
    async def evolve_pet(self, event: AstrMessageEvent):
        """让达到条件的宠物进化。"""
        user_id, group_id = event.get_sender_id(), event.get_group_id()
        if not group_id:
            return

        pet = self._get_pet(user_id, group_id)
        if not pet:
            yield event.plain_result("你还没有宠物哦。")
            return

        pet_type_info = PET_TYPES[pet['pet_type']]
        current_evo_info = pet_type_info['evolutions'][pet['evolution_stage']]

        evolve_level = current_evo_info['evolve_level']
        if not evolve_level:
            yield event.plain_result(f"「{pet['pet_name']}」已是最终形态，无法再进化。")
            return

        if pet['level'] < evolve_level:
            yield event.plain_result(f"「{pet['pet_name']}」需达到 Lv.{evolve_level} 才能进化。")
            return

        next_evo_stage = pet['evolution_stage'] + 1
        next_evo_info = pet_type_info['evolutions'][next_evo_stage]
        new_attack = pet['attack'] + random.randint(8, 15)
        new_defense = pet['defense'] + random.randint(8, 15)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE pets SET evolution_stage = ?, attack = ?, defense = ? WHERE user_id = ? AND group_id = ?",
                (next_evo_stage, new_attack, new_defense, int(user_id), int(group_id)))
            conn.commit()

        yield event.plain_result(
            f"光芒四射！你的「{pet['pet_name']}」成功进化为了「{next_evo_info['name']}」！各项属性都得到了巨幅提升！")