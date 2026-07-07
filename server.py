import os
import json
import logging
import asyncio
import random
import math
from aiohttp import web

logging.basicConfig(level=logging.INFO)

# Faol WebSocket ulanishlari
sockets = set()

# O'yinchilar ma'lumotlar bazasi
# {ws: {id, nick, x, y, direction, is_working, tool, chat_msg, chat_time}}
players = {}

# Global uy qurilish bosqichi va pul zaxirasi (ko'p o'yinchilar uchun umumiy)
game_state = {
    "house_stage": 0,
    "shared_money": 0,
    "base_index": 0
}

async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    player_id = id(ws)
    players[ws] = {
        "id": player_id,
        "nick": f"Quruvchi_{player_id % 1000}",
        "x": 100,
        "y": 0,
        "direction": 1,
        "is_working": False,
        "tool": 0,
        "chat_msg": "",
        "chat_time": 0,
        "helmet": "yellow",
        "jetpack": 0,
        "skin": "standard",
        "is_sleeping": False
    }
    sockets.add(ws)
    logging.info(f"Yangi o'yinchi ulandi: {player_id}")

    # Ilk ulanishda o'yin holatini yuborish
    try:
        await ws.send_str(json.dumps({
            "type": "init",
            "your_id": player_id,
            "house_stage": game_state["house_stage"],
            "shared_money": game_state["shared_money"],
            "base_index": game_state["base_index"]
        }))

        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                data = json.loads(msg.data)
                action = data.get("action")

                if action == "init":
                    players[ws]["nick"] = data.get("nick", f"Quruvchi_{player_id % 1000}")
                    players[ws]["helmet"] = data.get("helmet", "yellow")
                    players[ws]["jetpack"] = data.get("jetpack", 0)
                    players[ws]["skin"] = data.get("skin", "standard")
                elif action == "move":
                    players[ws]["x"] = data.get("x", 100)
                    players[ws]["direction"] = data.get("direction", 1)
                    players[ws]["is_sleeping"] = data.get("is_sleeping", False)
                elif action == "work":
                    players[ws]["is_working"] = data.get("is_working", False)
                    players[ws]["tool"] = data.get("tool", 0)
                elif action == "chat":
                    players[ws]["chat_msg"] = data.get("msg", "")
                    players[ws]["chat_time"] = data.get("time", 0)
                elif action == "build_update":
                    # Uy qurilish bosqichi, pul yoki baza o'zgarganda global holatni yangilash
                    game_state["house_stage"] = data.get("house_stage", game_state["house_stage"])
                    game_state["shared_money"] = data.get("shared_money", game_state["shared_money"])
                    game_state["base_index"] = data.get("base_index", game_state["base_index"])

                # Barcha o'yinchilarga yangilangan holatni yuborish (broadcast)
                state_players = [p for p in players.values()]
                broadcast_data = json.dumps({
                    "type": "state",
                    "players": state_players,
                    "house_stage": game_state["house_stage"],
                    "shared_money": game_state["shared_money"],
                    "base_index": game_state["base_index"]
                })

                for client in list(sockets):
                    if not client.closed:
                        await client.send_str(broadcast_data)

            elif msg.type == web.WSMsgType.ERROR:
                logging.error(f"WebSocket xatolik: {ws.exception()}")
    finally:
        sockets.remove(ws)
        players.pop(ws, None)
        logging.info(f"O'yinchi chiqib ketdi: {player_id}")

        # Chiqib ketganini boshqalarga bildirish
        state_players = [p for p in players.values()]
        broadcast_data = json.dumps({
            "type": "state",
            "players": state_players,
            "house_stage": game_state["house_stage"],
            "shared_money": game_state["shared_money"],
            "base_index": game_state["base_index"]
        })
        for client in list(sockets):
            if not client.closed:
                await client.send_str(broadcast_data)

    return ws

async def leaderboard_api_handler(request):
    game = request.query.get("game", "global")
    users_file = os.path.join(os.path.dirname(__file__), "users.json")
    if os.path.exists(users_file):
        try:
            with open(users_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            players_list = []
            for uid, udata in data.items():
                name = udata.get("name", "Quruvchi")
                vip_status = udata.get("vip_status", False)
                referrals_count = udata.get("referrals_count", 0)
                
                if game == "global":
                    score = udata.get("points", 0)
                else:
                    high_scores = udata.setdefault("high_scores", {})
                    score = high_scores.get(game, 0)
                
                players_list.append({
                    "id": uid,
                    "name": name,
                    "vip_status": vip_status,
                    "referrals_count": referrals_count,
                    "score": score
                })
                
            sorted_players = sorted(
                players_list,
                key=lambda u: u.get("score", 0),
                reverse=True
            )
            return web.json_response(sorted_players[:100])
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)
    else:
        return web.json_response([], status=200)

async def submit_score_handler(request):
    try:
        req_data = await request.json()
        user_id = str(req_data.get("user_id"))
        name = req_data.get("name", "O'yinchi")
        game = req_data.get("game")
        score = int(req_data.get("score", 0))
        
        if not user_id or not game:
            return web.json_response({"error": "Missing params"}, status=400)
            
        users_file = os.path.join(os.path.dirname(__file__), "users.json")
        data = {}
        if os.path.exists(users_file):
            try:
                with open(users_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
                
        user_data = data.setdefault(user_id, {
            "name": name,
            "points": 0,
            "vip_status": False,
            "referrals_count": 0,
            "helmet_color": "yellow",
            "high_scores": {}
        })
        
        if "high_scores" not in user_data:
            user_data["high_scores"] = {}
            
        high_scores = user_data["high_scores"]
        old_score = high_scores.get(game, 0)
        
        if score > old_score:
            high_scores[game] = score
            # Earning point conversion
            points_reward = int(score / 10)
            user_data["points"] = user_data.get("points", 0) + points_reward
            
        if name != "O'yinchi":
            user_data["name"] = name
            
        with open(users_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            
        return web.json_response({"status": "ok", "new_high": score > old_score})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

# --- SURVIVAL MULTIPLAYER MULTIPLAYER GAME STATE ---
survival_sockets = set()
survival_players = {}
survival_bullets = []
survival_loot = []
next_bullet_id = 1
next_loot_id = 1

def spawn_initial_loot():
    global next_loot_id
    loot_types = ['shotgun', 'rifle', 'shield', 'medkit']
    for _ in range(40):
        survival_loot.append({
            "id": next_loot_id,
            "type": random.choice(loot_types),
            "x": random.randint(50, 1950),
            "y": random.randint(50, 1950)
        })
        next_loot_id += 1

async def respawn_player_delayed(player):
    await asyncio.sleep(3.0)
    player["x"] = random.randint(100, 1900)
    player["y"] = random.randint(100, 1900)
    player["hp"] = 100
    player["shield"] = 0
    player["weapon"] = "pistol"
    player["ammo"] = 999

async def survival_game_loop():
    global next_bullet_id, next_loot_id
    spawn_initial_loot()
    while True:
        try:
            # 1. Update bullets
            for b in list(survival_bullets):
                b["x"] += b["vx"]
                b["y"] += b["vy"]
                b["life"] -= 1
                
                # Check collision with other players
                hit_player = None
                hit_ws = None
                for ws, p in survival_players.items():
                    if p["id"] == b["owner_id"] or p["hp"] <= 0:
                        continue
                    dist = math.hypot(p["x"] - b["x"], p["y"] - b["y"])
                    if dist < 22:  # player radius (20) + bullet radius (2)
                        hit_player = p
                        hit_ws = ws
                        break
                        
                if hit_player:
                    damage = 20
                    if hit_player["shield"] > 0:
                        hit_player["shield"] -= damage
                        if hit_player["shield"] < 0:
                            hit_player["hp"] += hit_player["shield"]
                            hit_player["shield"] = 0
                    else:
                        hit_player["hp"] -= damage
                        
                    if hit_player["hp"] <= 0:
                        hit_player["hp"] = 0
                        killer_name = "Kiber"
                        
                        # Add score/kills to shooter
                        for p in survival_players.values():
                            if p["id"] == b["owner_id"]:
                                p["kills"] += 1
                                killer_name = p["name"]
                                break
                                
                        # Send kill message
                        kill_msg = json.dumps({
                            "type": "kill",
                            "killer": killer_name,
                            "victim": hit_player["name"]
                        })
                        for client in list(survival_sockets):
                            try: await client.send_str(kill_msg)
                            except: pass
                            
                        asyncio.create_task(respawn_player_delayed(hit_player))
                        
                    if b in survival_bullets:
                        survival_bullets.remove(b)
                elif b["life"] <= 0 or b["x"] < 0 or b["x"] > 2000 or b["y"] < 0 or b["y"] > 2000:
                    if b in survival_bullets:
                        survival_bullets.remove(b)
                        
            # 2. Check player loot pickup
            for ws, p in survival_players.items():
                if p["hp"] <= 0:
                    continue
                for item in list(survival_loot):
                    dist = math.hypot(p["x"] - item["x"], p["y"] - item["y"])
                    if dist < 25:
                        if item["type"] == "medkit":
                            p["hp"] = min(100, p["hp"] + 40)
                        elif item["type"] == "shield":
                            p["shield"] = min(100, p["shield"] + 50)
                        else:
                            p["weapon"] = item["type"]
                            p["ammo"] = 30 if item["type"] == "shotgun" else 60
                            
                        if item in survival_loot:
                            survival_loot.remove(item)
                            
                        # Respawn new loot
                        survival_loot.append({
                            "id": next_loot_id,
                            "type": random.choice(['shotgun', 'rifle', 'shield', 'medkit']),
                            "x": random.randint(50, 1950),
                            "y": random.randint(50, 1950)
                        })
                        next_loot_id += 1
                        
            # 3. Broadcast state
            if survival_sockets:
                players_list = [p for p in survival_players.values()]
                state_data = json.dumps({
                    "type": "state",
                    "players": players_list,
                    "bullets": survival_bullets,
                    "loot": survival_loot
                })
                for client in list(survival_sockets):
                    if not client.closed:
                        try: await client.send_str(state_data)
                        except: pass
                        
            await asyncio.sleep(0.033)  # ~30 Hz
        except Exception as e:
            logging.error(f"Error in survival loop: {e}")
            await asyncio.sleep(0.1)

async def survival_websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    player_id = id(ws)
    survival_players[ws] = {
        "id": player_id,
        "name": f"Jangchi_{player_id % 1000}",
        "x": random.randint(100, 1900),
        "y": random.randint(100, 1900),
        "angle": 0,
        "hp": 100,
        "shield": 0,
        "weapon": "pistol",
        "ammo": 999,
        "kills": 0
    }
    survival_sockets.add(ws)
    logging.info(f"Survival player connected: {player_id}")
    
    try:
        await ws.send_str(json.dumps({
            "type": "init",
            "your_id": player_id,
            "map_width": 2000,
            "map_height": 2000
        }))

        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                data = json.loads(msg.data)
                action = data.get("action")

                if action == "init":
                    survival_players[ws]["name"] = data.get("name", f"Jangchi_{player_id % 1000}")
                elif action == "update":
                    p = survival_players[ws]
                    if p["hp"] > 0:
                        p["x"] = data.get("x", p["x"])
                        p["y"] = data.get("y", p["y"])
                        p["angle"] = data.get("angle", p["angle"])
                elif action == "shoot":
                    p = survival_players[ws]
                    if p["hp"] > 0 and p["ammo"] > 0:
                        if p["weapon"] != "pistol":
                            p["ammo"] -= 1
                        angle = data.get("angle", p["angle"])
                        global next_bullet_id
                        
                        if p["weapon"] == "shotgun":
                            # 3 spread bullets
                            for dev in [-0.15, 0, 0.15]:
                                a = angle + dev
                                survival_bullets.append({
                                    "id": next_bullet_id,
                                    "owner_id": player_id,
                                    "x": p["x"] + math.cos(a) * 25,
                                    "y": p["y"] + math.sin(a) * 25,
                                    "vx": math.cos(a) * 12,
                                    "vy": math.sin(a) * 12,
                                    "life": 45
                                })
                                next_bullet_id += 1
                        else:
                            # Single bullet (pistol or rifle)
                            survival_bullets.append({
                                "id": next_bullet_id,
                                "owner_id": player_id,
                                "x": p["x"] + math.cos(angle) * 25,
                                "y": p["y"] + math.sin(angle) * 25,
                                "vx": math.cos(angle) * 14,
                                "vy": math.sin(angle) * 14,
                                "life": 60
                            })
                            next_bullet_id += 1
            elif msg.type == web.WSMsgType.ERROR:
                pass
    finally:
        survival_sockets.remove(ws)
        survival_players.pop(ws, None)
        logging.info(f"Survival player disconnected: {player_id}")
    return ws

async def start_background_tasks(app):
    app['survival_loop'] = asyncio.create_task(survival_game_loop())

async def cleanup_background_tasks(app):
    app['survival_loop'].cancel()
    await app['survival_loop']

app = web.Application()
app.on_startup.append(start_background_tasks)
app.on_cleanup.append(cleanup_background_tasks)

app.router.add_get('/ws', websocket_handler)
app.router.add_get('/ws/survival', survival_websocket_handler)
app.router.add_get('/api/leaderboard', leaderboard_api_handler)
app.router.add_post('/api/submit_score', submit_score_handler)

# Loyiha papkasini static fayllar sifatida ulash
app.router.add_static('/', path=os.path.dirname(__file__), show_index=True)

if __name__ == '__main__':
    web.run_app(app, port=8000)
