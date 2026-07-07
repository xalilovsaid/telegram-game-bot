import os
import json
import logging
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

app = web.Application()
app.router.add_get('/ws', websocket_handler)
app.router.add_get('/api/leaderboard', leaderboard_api_handler)
app.router.add_post('/api/submit_score', submit_score_handler)

# Loyiha papkasini static fayllar sifatida ulash
app.router.add_static('/', path=os.path.dirname(__file__), show_index=True)

if __name__ == '__main__':
    web.run_app(app, port=8000)
