import socketio
import uvicorn
import random
import logging
import os
from typing import Dict
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from game_logic import PokerGame, GameState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("poker_server")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_PATH = os.path.join(os.path.dirname(__file__), "../frontend")
IMAGE_PATH = os.path.join(FRONTEND_PATH, "image")
if not os.path.exists(IMAGE_PATH):
    os.makedirs(IMAGE_PATH, exist_ok=True)

app.mount("/image", StaticFiles(directory=IMAGE_PATH), name="image")

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
socket_app = socketio.ASGIApp(sio, app)

rooms: Dict[str, PokerGame] = {}
player_to_room: Dict[str, str] = {}

@app.get("/")
async def get_index():
    return FileResponse(os.path.join(FRONTEND_PATH, "index.html"))

async def broadcast_room_list():
    room_list = []
    for rid, game in rooms.items():
        room_list.append({
            "room_id": rid,
            "player_count": len(game.players),
            "max_players": game.max_players,
            "state": game.state.name,
            "host_name": game.players[game.host_id].name if game.host_id and game.host_id in game.players else "???",
        })
    await sio.emit("room_list", room_list)

@sio.event
async def connect(sid, environ):
    logger.info(f"Client connected: {sid}")
    room_list = []
    for rid, game in rooms.items():
        room_list.append({
            "room_id": rid,
            "player_count": len(game.players),
            "max_players": game.max_players,
            "state": game.state.name,
            "host_name": game.players[game.host_id].name if game.host_id and game.host_id in game.players else "???",
        })
    await sio.emit("room_list", room_list, room=sid)

@sio.event
async def disconnect(sid):
    if sid in player_to_room:
        room_id = player_to_room[sid]
        if room_id in rooms:
            game = rooms[room_id]
            was_current = game.get_current_player_id() == sid
            player_name = game.players[sid].name if sid in game.players else "???"
            game.remove_player(sid)

            if not game.players:
                del rooms[room_id]
            else:
                game.logs.append(f"[{player_name}]님이 퇴장했습니다.")
                if was_current and game.state not in (GameState.WAITING, GameState.SHOWDOWN):
                    await _check_and_advance(room_id)
                else:
                    await broadcast_game_state(room_id)
        del player_to_room[sid]
    await broadcast_room_list()
    logger.info(f"Client disconnected: {sid}")

@sio.event
async def list_rooms(sid):
    room_list = []
    for rid, game in rooms.items():
        room_list.append({
            "room_id": rid,
            "player_count": len(game.players),
            "max_players": game.max_players,
            "state": game.state.name,
            "host_name": game.players[game.host_id].name if game.host_id and game.host_id in game.players else "???",
        })
    await sio.emit("room_list", room_list, room=sid)

async def _check_and_advance(room_id: str):
    if room_id not in rooms:
        return
    game = rooms[room_id]
    if game.state in (GameState.WAITING, GameState.SHOWDOWN):
        return
    if game.is_betting_complete():
        active = [p for p in game.players.values() if not p.is_folded]
        if len(active) <= 1:
            game.resolve_winner()
        else:
            game.next_phase()
    await broadcast_game_state(room_id)

@sio.event
async def create_room(sid, data):
    room_id = f"room_{random.randint(1000, 9999)}"
    while room_id in rooms:
        room_id = f"room_{random.randint(1000, 9999)}"
    rooms[room_id] = PokerGame(room_id)
    rooms[room_id].host_id = sid
    await broadcast_room_list()
    return {"room_id": room_id}

@sio.event
async def join_room(sid, data):
    room_id = data.get("room_id")
    player_name = data.get("name", f"Player_{sid[:4]}")

    if room_id not in rooms:
        await sio.emit("error", {"message": "존재하지 않는 방입니다."}, room=sid)
        return

    game = rooms[room_id]
    if len(game.players) >= game.max_players:
        await sio.emit("error", {"message": "방이 가득 찼습니다. (최대 8명)"}, room=sid)
        return

    game.add_player(sid, player_name)
    player_to_room[sid] = room_id
    await sio.enter_room(sid, room_id)
    await sio.emit("room_joined", {"room_id": room_id, "host_id": game.host_id}, room=sid)

    join_msg = f"[{player_name}]님이 입장했습니다."
    if game.state != GameState.WAITING:
        join_msg += " (다음 판부터 참여)"

    game.logs.append(join_msg)
    await broadcast_game_state(room_id)
    await broadcast_room_list()

@sio.event
async def start_game(sid, data):
    room_id = player_to_room.get(sid)
    if not room_id or room_id not in rooms:
        return
    game = rooms[room_id]

    if game.host_id != sid:
        await sio.emit("error", {"message": "방장만 시작할 수 있습니다."}, room=sid)
        return

    if game.start_game():
        await broadcast_game_state(room_id)
    else:
        await sio.emit("error", {"message": "플레이어가 부족합니다. (최소 2명)"}, room=sid)

@sio.event
async def player_action(sid, data):
    """콜/레이즈/폴드/체크/올인 처리"""
    room_id = player_to_room.get(sid)
    if not room_id or room_id not in rooms:
        return
    game = rooms[room_id]

    if game.state in (GameState.WAITING, GameState.SHOWDOWN):
        return

    if game.get_current_player_id() != sid:
        await sio.emit("error", {"message": "당신의 차례가 아닙니다."}, room=sid)
        return

    action = data.get("action")
    raise_to = int(data.get("raise_to", 0))

    betting_done = game.process_action(sid, action, raise_to)
    await broadcast_game_state(room_id)

    if betting_done:
        active = [p for p in game.players.values() if not p.is_folded]
        if len(active) <= 1:
            game.resolve_winner()
        else:
            game.next_phase()
        await broadcast_game_state(room_id)

@sio.event
async def send_message(sid, data):
    """채팅 메시지 브로드캐스트"""
    room_id = player_to_room.get(sid)
    if not room_id or room_id not in rooms:
        return
    player = rooms[room_id].players.get(sid)
    if not player:
        return
    message = str(data.get("message", "")).strip()[:200]
    if not message:
        return
    await sio.emit("chat_message", {
        "name": player.name,
        "message": message,
    }, room=room_id)

async def broadcast_game_state(room_id):
    if room_id not in rooms:
        return
    game = rooms[room_id]

    common_state = {
        "room_id": game.room_id,
        "state": game.state.name,
        "pot": game.pot,
        "community_cards": [c.to_dict() for c in game.community_cards],
        "logs": game.logs[-5:],
        "host_id": game.host_id,
        "current_player_id": game.get_current_player_id(),
        "current_bet": game.current_bet,
        "small_blind": game.small_blind,
        "big_blind": game.big_blind,
    }

    active_not_folded = [p for p in game.players.values() if not p.is_folded]
    non_allin_active = [p for p in active_not_folded if not p.is_all_in]
    allin_showdown = len(active_not_folded) >= 2 and len(non_allin_active) <= 1 and game.state not in (GameState.WAITING,)

    hand_rank_names = {
        "HIGH_CARD": "하이 카드", "ONE_PAIR": "원 페어", "TWO_PAIR": "투 페어",
        "THREE_OF_A_KIND": "트리플", "STRAIGHT": "스트레이트", "FLUSH": "플러쉬",
        "FULL_HOUSE": "풀 하우스", "FOUR_OF_A_KIND": "포카드",
        "STRAIGHT_FLUSH": "스트레이트 플러쉬", "ROYAL_FLUSH": "로얄 플러쉬",
    }

    for sid in game.players.keys():
        players_data = []
        for pid, p in game.players.items():
            show_hand = (
                (pid == sid)
                or (game.state == GameState.SHOWDOWN and not p.is_folded)
                or (allin_showdown and not p.is_folded)
            )
            pd = p.to_dict(show_hand=show_hand)

            if pid == sid and p.hand and not p.is_folded and game.state not in (GameState.WAITING,):
                rank_enum, _ = game.evaluate_hand(p)
                pd["my_hand_rank"] = hand_rank_names.get(rank_enum.name, rank_enum.name)

            players_data.append(pd)

        await sio.emit("game_state", {**common_state, "players": players_data}, room=sid)

if __name__ == "__main__":
    uvicorn.run(socket_app, host="0.0.0.0", port=4996)
