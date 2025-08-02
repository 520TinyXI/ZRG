import sqlite3
import random
from datetime import datetime, timedelta

# 引入宠物类型数据
from .pet_system import PET_TYPES

class BattleSystem:
    def __init__(self, plugin):
        self.plugin = plugin
        self.db_path = plugin.db_path
        
    def _get_attribute_multiplier(self, attacker_attr: str, defender_attr: str) -> float:
        """根据攻击方和防御方的属性，计算伤害倍率。"""
        effectiveness = {
            "金": "木",  # 金克木
            "木": "土",  # 木克土
            "土": "水",  # 土克水
            "水": "火",  # 水克火
            "火": "金"   # 火克金
        }
        if effectiveness.get(attacker_attr) == defender_attr:
            return 1.2  # 克制，伤害加成20%
        if effectiveness.get(defender_attr) == attacker_attr:
            return 0.8  # 被克制，伤害减少20%
        return 1.0  # 无克制关系
        
    def _run_battle(self, pet1: dict, pet2: dict) -> tuple[list[str], str]:
        """执行两个宠物之间的对战，集成属性克制逻辑。"""
        log = []
        p1_hp = pet1['level'] * 10 + pet1['satiety']
        p2_hp = pet2['level'] * 10 + pet2['satiety']
        p1_name = pet1['pet_name']
        p2_name = pet2['pet_name']

        # 获取双方属性
        p1_attr = PET_TYPES[pet1['pet_type']]['attribute']
        p2_attr = PET_TYPES[pet2['pet_type']]['attribute']

        log.append(
            f"战斗开始！\n「{p1_name}」(Lv.{pet1['level']} {p1_attr}系) vs 「{p2_name}」(Lv.{pet2['level']} {p2_attr}系)")

        turn = 0
        while p1_hp > 0 and p2_hp > 0:
            turn += 1
            log.append(f"\n--- 第 {turn} 回合 ---")

            # 宠物1攻击
            multiplier1 = self._get_attribute_multiplier(p1_attr, p2_attr)
            base_dmg_to_p2 = max(1, int(pet1['attack'] * random.uniform(0.8, 1.2) - pet2['defense'] * 0.5))
            final_dmg_to_p2 = int(base_dmg_to_p2 * multiplier1)
            p2_hp -= final_dmg_to_p2

            log.append(f"「{p1_name}」发起了攻击！")
            if multiplier1 > 1.0:
                log.append("效果拔群！")
            elif multiplier1 < 1.0:
                log.append("效果不太理想…")
            log.append(f"对「{p2_name}」造成了 {final_dmg_to_p2} 点伤害！(剩余HP: {max(0, p2_hp)})")

            if p2_hp <= 0:
                break

            # 宠物2攻击
            multiplier2 = self._get_attribute_multiplier(p2_attr, p1_attr)
            base_dmg_to_p1 = max(1, int(pet2['attack'] * random.uniform(0.8, 1.2) - pet1['defense'] * 0.5))
            final_dmg_to_p1 = int(base_dmg_to_p1 * multiplier2)
            p1_hp -= final_dmg_to_p1

            log.append(f"「{p2_name}」进行了反击！")
            if multiplier2 > 1.0:
                log.append("效果拔群！")
            elif multiplier2 < 1.0:
                log.append("效果不太理想…")
            log.append(f"对「{p1_name}」造成了 {final_dmg_to_p1} 点伤害！(剩余HP: {max(0, p1_hp)})")

        winner_name = p1_name if p1_hp > 0 else p2_name
        log.append(f"\n战斗结束！胜利者是「{winner_name}」！")
        return log, winner_name
        
    async def walk_pet(self, event: AstrMessageEvent):
        """带宠物散步，触发随机事件或PVE战斗"""
        from astrbot.api.event import AstrMessageEvent
        
        user_id, group_id = event.get_sender_id(), event.get_group_id()
        if not group_id:
            return

        pet = self.plugin.pet_system._get_pet(user_id, group_id)
        if not pet:
            yield event.plain_result("你还没有宠物，不能去散步哦。")
            return

        now = datetime.now()
        last_walk = datetime.fromisoformat(pet['last_walk_time'])
        if now - last_walk < timedelta(minutes=5):
            yield event.plain_result(f"刚散步回来，让「{pet['pet_name']}」休息一下吧。")
            return

        final_reply = []
        
        # 70%概率触发随机事件，30%概率遭遇野生宠物
        if random.random() < 0.7:
            # 随机事件奖励
            reward_types = ['exp', 'mood', 'satiety']
            reward_type = random.choice(reward_types)
            reward_value = random.randint(5, 20)
            money_gain = random.randint(1, 10)
            
            # 生成有趣的事件描述
            events = [
                f"{pet['pet_name']}在草丛中发现了一些闪闪发光的道具，心情大好！",
                f"{pet['pet_name']}遇到了友善的NPC，获得了一些经验和金钱。",
                f"{pet['pet_name']}在小溪边喝了些水，感觉饱食度增加了。",
                f"{pet['pet_name']}在花丛中打了个滚，心情变得很好。",
                f"{pet['pet_name']}找到了一个隐藏的宝箱，里面有一些奖励！"
            ]
            event_desc = random.choice(events)
            
            reward_type_chinese = {"exp": "经验值", "mood": "心情值", "satiety": "饱食度"}.get(reward_type, reward_type)
            final_reply.append(f"奇遇发生！\n{event_desc}\n你的宠物获得了 {reward_value} 点{reward_type_chinese}！")
            if money_gain > 0:
                final_reply.append(f"意外之喜！你在路边捡到了 ${money_gain}！")

            with sqlite3.connect(self.db_path) as conn:
                update_query = (
                    f"UPDATE pets SET "
                    f"{reward_type} = {'MIN(100, ' + reward_type + ' + ?)' if reward_type != 'exp' else (reward_type + ' + ?')}, "
                    f"money = money + ?, "
                    f"last_walk_time = ? "
                    f"WHERE user_id = ? AND group_id = ?"
                )
                conn.execute(update_query, (reward_value, money_gain, now.isoformat(), int(user_id), int(group_id)))
                conn.commit()

            if reward_type == 'exp':
                final_reply.extend(self.plugin.pet_system._check_level_up(user_id, group_id))
        else:
            # 遭遇野生宠物PVE战斗
            npc_level = max(1, pet['level'] + random.randint(-1, 1))
            npc_type_name = random.choice(list(PET_TYPES.keys()))
            npc_stats = PET_TYPES[npc_type_name]['initial_stats']
            npc_pet = {
                "pet_name": f"野生的{npc_type_name}",
                "pet_type": npc_type_name,
                "level": npc_level,
                "attack": npc_stats['attack'] + npc_level,
                "defense": npc_stats['defense'] + npc_level,
                "satiety": 100
            }

            battle_log, winner_name = self._run_battle(pet, npc_pet)
            final_reply.extend(battle_log)

            exp_gain = 0
            money_gain = 0
            if winner_name == pet['pet_name']:
                exp_gain = npc_level * 5 + random.randint(1, 5)
                money_gain = random.randint(5, 15)
                final_reply.append(f"\n胜利了！你获得了 {exp_gain} 点经验值和 ${money_gain} 赏金！")
            else:
                exp_gain = 1
                final_reply.append(f"\n很遗憾，你的宠物战败了，但也获得了 {exp_gain} 点经验。")

            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE pets SET exp = exp + ?, money = money + ?, last_walk_time = ? WHERE user_id = ? AND group_id = ?",
                    (exp_gain, money_gain, now.isoformat(), int(user_id), int(group_id)))
                conn.commit()
            final_reply.extend(self.plugin.pet_system._check_level_up(user_id, group_id))

        yield event.plain_result("\n".join(final_reply))
        
    async def duel_pet(self, event: AstrMessageEvent):
        """与其他群友的宠物进行对决"""
        from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
        from astrbot.core.message.components import At
        
        user_id, group_id = event.get_sender_id(), event.get_group_id()
        if not group_id:
            yield event.plain_result("该功能仅限群聊使用哦。")
            return

        # 获取@信息
        at_info = None
        for seg in event.get_messages():
            if isinstance(seg, At) and str(seg.qq) != event.get_self_id():
                at_info = str(seg.qq)
                break

        if not at_info:
            yield event.plain_result("请@一位你想对决的群友。用法: /对决 @某人")
            return

        challenger_pet = self.plugin.pet_system._get_pet(user_id, group_id)
        if not challenger_pet:
            yield event.plain_result("你还没有宠物，无法发起对决。")
            return

        target_id = at_info
        if user_id == target_id:
            yield event.plain_result("不能和自己对决哦。")
            return

        target_pet = self.plugin.pet_system._get_pet(target_id, group_id)
        if not target_pet:
            yield event.plain_result(f"对方还没有宠物呢。")
            return

        now = datetime.now()

        # 检查挑战者自己的CD
        last_duel_challenger = datetime.fromisoformat(challenger_pet['last_duel_time'])
        if now - last_duel_challenger < timedelta(minutes=30):
            remaining = timedelta(minutes=30) - (now - last_duel_challenger)
            yield event.plain_result(f"你的对决技能正在冷却中，还需等待 {str(remaining).split('.')[0]}。")
            return

        # 检查被挑战者的CD
        last_duel_target = datetime.fromisoformat(target_pet['last_duel_time'])
        if now - last_duel_target < timedelta(minutes=30):
            remaining = timedelta(minutes=30) - (now - last_duel_target)
            yield event.plain_result(
                f"对方的宠物正在休息，还需等待 {str(remaining).split('.')[0]} 才能接受对决。")
            return

        battle_log, winner_name = self._run_battle(challenger_pet, target_pet)

        money_gain = 20
        if winner_name == challenger_pet['pet_name']:
            winner_id, loser_id = user_id, target_id
            winner_exp = 10 + target_pet['level'] * 2
            loser_exp = 5 + challenger_pet['level']
        else:
            winner_id, loser_id = target_id, user_id
            winner_exp = 10 + challenger_pet['level'] * 2
            loser_exp = 5 + target_pet['level']

        final_reply = list(battle_log)
        final_reply.append(
            f"\n对决结算：胜利者获得了 {winner_exp} 点经验值和 ${money_gain}，参与者获得了 {loser_exp} 点经验值。")

        with sqlite3.connect(self.db_path) as conn:
            # 为双方都设置冷却时间
            conn.execute("UPDATE pets SET last_duel_time = ? WHERE user_id = ? AND group_id = ?",
                         (now.isoformat(), int(user_id), int(group_id)))
            conn.execute("UPDATE pets SET last_duel_time = ? WHERE user_id = ? AND group_id = ?",
                         (now.isoformat(), int(target_id), int(group_id)))

            # 为胜利者增加金钱
            conn.execute("UPDATE pets SET money = money + ? WHERE user_id = ? AND group_id = ?",
                         (money_gain, int(winner_id), int(group_id)))

            # 发放经验
            conn.execute("UPDATE pets SET exp = exp + ? WHERE user_id = ? AND group_id = ?",
                         (winner_exp, int(winner_id), int(group_id)))
            conn.execute("UPDATE pets SET exp = exp + ? WHERE user_id = ? AND group_id = ?",
                         (loser_exp, int(loser_id), int(group_id)))
            conn.commit()

        final_reply.extend(self.plugin.pet_system._check_level_up(winner_id, group_id))
        final_reply.extend(self.plugin.pet_system._check_level_up(loser_id, group_id))

        yield event.plain_result("\n".join(final_reply))