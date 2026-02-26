import socketio
import uvicorn
import asyncio
import random
import logging
import os
from typing import List, Dict, Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from game_logic import PokerGame, GameState, Player, HandRank

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("poker_server")

app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 프론트엔드 정적 파일 경로 설정
FRONTEND_PATH = os.path.join(os.path.dirname(__file__), "../frontend")
IMAGE_PATH = os.path.join(FRONTEND_PATH, "image")
if not os.path.exists(IMAGE_PATH):
    os.makedirs(IMAGE_PATH, exist_ok=True)

app.mount("/image", StaticFiles(directory=IMAGE_PATH), name="image")

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
socket_app = socketio.ASGIApp(sio, app)

# 게임 인스턴스들을 관리하는 딕셔너리
rooms: Dict[str, PokerGame] = {}
player_to_room: Dict[str, str] = {}

@app.get("/")
async def get_index():
    return FileResponse(os.path.join(FRONTEND_PATH, "index.html"))

@sio.event
async def connect(sid, environ):
    logger.info(f"Client connected: {sid}")

@sio.event
async def disconnect(sid):
    if sid in player_to_room:
        room_id = player_to_room[sid]
        if room_id in rooms:
            game = rooms[room_id]
            game.remove_player(sid)
            await broadcast_game_state(room_id)
            if not game.players:
                del rooms[room_id]
        del player_to_room[sid]
    logger.info(f"Client disconnected: {sid}")

@sio.event
async def create_room(sid, data):
    room_id = f"room_{random.randint(1000, 9999)}"
    while room_id in rooms: room_id = f"room_{random.randint(1000, 9999)}"
    rooms[room_id] = PokerGame(room_id)
    rooms[room_id].host_id = sid
    return {"room_id": room_id}

@sio.event
async def join_room(sid, data):
    room_id = data.get("room_id")
    player_name = data.get("name", f"Player_{sid[:4]}")
    
    if room_id in rooms:
        game = rooms[room_id]
        if len(game.players) >= game.max_players:
            await sio.emit("error", {"message": "방이 가득 찼습니다."}, room=sid)
            return

        # 게임 중이어도 입장 가능 (game_logic에서 처리)
        game.add_player(sid, player_name)
        player_to_room[sid] = room_id
        await sio.enter_room(sid, room_id)
        await sio.emit("room_joined", {"room_id": room_id, "host_id": game.host_id}, room=sid)
        
        # 입장 메시지
        join_msg = f"[{player_name}]님이 입장했습니다."
        if game.state != GameState.WAITING:
            join_msg += " (다음 판부터 참여)"
            await sio.emit("error", {"message": "게임이 진행 중입니다. 관전 모드로 입장합니다."}, room=sid)
        
        game.logs.append(join_msg)
        await broadcast_game_state(room_id)
    else:
        await sio.emit("error", {"message": "존재하지 않는 방입니다."}, room=sid)

@sio.event
async def start_game(sid, data):
    room_id = player_to_room.get(sid)
    if not room_id or room_id not in rooms: return
    game = rooms[room_id]
    
    if game.host_id != sid:
        await sio.emit("error", {"message": "방장만 시작할 수 있습니다."}, room=sid)
        return

    if game.start_game():
        await broadcast_game_state(room_id)
        # 자동 진행을 위해 루프 시작 (간소화된 버전에서는 수동 진행/페이즈 넘김 버튼 사용 가능하지만, 여기선 타이머 대신 페이즈 진행 버튼 로직을 추가하거나 자동 진행)
        # 일단 시작 후에는 바로 broadcast
    else:
        await sio.emit("error", {"message": "플레이어가 부족합니다."}, room=sid)

@sio.event
async def next_phase(sid, data):
    """디버그/테스트용: 강제로 다음 페이즈로 넘김 (방장만)"""
    room_id = player_to_room.get(sid)
    if not room_id or room_id not in rooms: return
    game = rooms[room_id]
    if game.host_id == sid and game.state != GameState.WAITING:
        game.next_phase()
        await broadcast_game_state(room_id)

async def broadcast_game_state(room_id):
    if room_id not in rooms: return
    game = rooms[room_id]
    
    # 공통 상태
    common_state = {
        "room_id": game.room_id,
        "state": game.state.name,
        "pot": game.pot,
        "community_cards": [c.to_dict() for c in game.community_cards],
        "logs": game.logs[-5:],
        "host_id": game.host_id
    }
    
    for sid in game.players.keys():
        # 각 플레이어에게 개인화된 상태 전송 (자신의 패만 보임)
        players_data = []
        for pid, p in game.players.items():
            # 쇼다운 상태이거나 자기 자신일 때만 패 공개
            show_hand = (pid == sid) or (game.state == GameState.SHOWDOWN and not p.is_folded)
            players_data.append(p.to_dict(show_hand=show_hand))
            
        await sio.emit("game_state", {**common_state, "players": players_data}, room=sid)

if __name__ == "__main__":
    uvicorn.run(socket_app, host="0.0.0.0", port=8092)
