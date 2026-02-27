import random
from enum import Enum, auto
from typing import List, Dict, Optional, Tuple
from collections import Counter

class Suit(Enum):
    SPADES = "♠"
    HEARTS = "♥"
    DIAMONDS = "♦"
    CLUBS = "♣"

class Rank(Enum):
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14

    def __str__(self):
        if self.value <= 10:
            return str(self.value)
        return {11: "J", 12: "Q", 13: "K", 14: "A"}[self.value]

class Card:
    def __init__(self, suit: Suit, rank: Rank):
        self.suit = suit
        self.rank = rank

    def __repr__(self):
        return f"{self.suit.value}{self.rank}"

    def to_dict(self):
        return {"suit": self.suit.value, "rank": str(self.rank), "value": self.rank.value}

class HandRank(Enum):
    HIGH_CARD = 1
    ONE_PAIR = 2
    TWO_PAIR = 3
    THREE_OF_A_KIND = 4
    STRAIGHT = 5
    FLUSH = 6
    FULL_HOUSE = 7
    FOUR_OF_A_KIND = 8
    STRAIGHT_FLUSH = 9
    ROYAL_FLUSH = 10

class GameState(Enum):
    WAITING = auto()
    PREFLOP = auto()
    FLOP = auto()
    TURN = auto()
    RIVER = auto()
    SHOWDOWN = auto()

class Player:
    def __init__(self, player_id: str, name: str, chips: int = 1000):
        self.player_id = player_id
        self.name = name
        self.chips = chips
        self.hand: List[Card] = []
        self.is_folded = False
        self.current_bet = 0
        self.is_all_in = False
        self.best_hand_rank: Optional[HandRank] = None
        self.best_hand_cards: List[Card] = []
        self.has_acted = False

    def to_dict(self, show_hand=False):
        data = {
            "id": self.player_id,
            "name": self.name,
            "chips": self.chips,
            "is_folded": self.is_folded,
            "current_bet": self.current_bet,
            "is_all_in": self.is_all_in,
            "has_acted": self.has_acted,
        }
        if show_hand:
            data["hand"] = [c.to_dict() for c in self.hand]
            data["best_rank"] = self.best_hand_rank.name if self.best_hand_rank else None
        else:
            data["hand"] = [{"suit": "?", "rank": "?"} for _ in self.hand] if self.hand else []
        return data

class PokerGame:
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.players: Dict[str, Player] = {}
        self.deck: List[Card] = []
        self.community_cards: List[Card] = []
        self.pot = 0
        self.current_bet = 0
        self.state = GameState.WAITING
        self.dealer_index = 0
        self.current_player_index = 0
        self.host_id: Optional[str] = None
        self.max_players = 8
        self.logs: List[str] = []
        self.small_blind = 10
        self.big_blind = 20
        self.last_aggressor: Optional[str] = None

    def _active_players(self) -> List[Player]:
        """폴드하지 않고 칩이 있는 플레이어 목록 (입장 순서 유지)"""
        return [p for p in self.players.values() if not p.is_folded and p.chips > 0]

    def _betting_players(self) -> List[Player]:
        """배팅 행동이 가능한 플레이어 (폴드 안 했고, 올인 아니고, 칩 있음)"""
        return [p for p in self.players.values() if not p.is_folded and not p.is_all_in and p.chips > 0]

    def add_player(self, player_id: str, name: str):
        if player_id not in self.players and len(self.players) < self.max_players:
            player = Player(player_id, name)
            if self.state != GameState.WAITING:
                player.is_folded = True
                player.hand = []
                self.logs.append(f"{name}님이 관전 모드로 입장하셨습니다. 다음 게임부터 참여합니다.")
            self.players[player_id] = player
            if not self.host_id:
                self.host_id = player_id
            return True
        return False

    def remove_player(self, player_id: str):
        if player_id in self.players:
            del self.players[player_id]
            if self.host_id == player_id and self.players:
                self.host_id = list(self.players.keys())[0]

    def reset_deck(self):
        self.deck = [Card(s, r) for s in Suit for r in Rank]
        random.shuffle(self.deck)

    def start_game(self):
        active_count = len([p for p in self.players.values() if p.chips > 0])
        if active_count < 2:
            return False

        self.state = GameState.PREFLOP
        self.reset_deck()
        self.community_cards = []
        self.pot = 0
        self.current_bet = 0
        self.last_aggressor = None

        active_players = list(self.players.values())
        for p in active_players:
            if p.chips > 0:
                p.hand = [self.deck.pop(), self.deck.pop()]
                p.is_folded = False
                p.current_bet = 0
                p.is_all_in = False
                p.best_hand_rank = None
                p.best_hand_cards = []
                p.has_acted = False
            else:
                p.is_folded = True
                p.hand = []

        self._post_blinds()
        self.logs.append("게임이 시작되었습니다. 카드를 분배합니다.")
        return True

    def _post_blinds(self):
        active = self._active_players()
        n = len(active)
        if n < 2:
            return

        sb_idx = self.dealer_index % n
        bb_idx = (self.dealer_index + 1) % n

        sb_player = active[sb_idx]
        bb_player = active[bb_idx]

        # 스몰 블라인드
        sb_amount = min(self.small_blind, sb_player.chips)
        sb_player.chips -= sb_amount
        sb_player.current_bet = sb_amount
        if sb_player.chips == 0:
            sb_player.is_all_in = True
        self.pot += sb_amount

        # 빅 블라인드
        bb_amount = min(self.big_blind, bb_player.chips)
        bb_player.chips -= bb_amount
        bb_player.current_bet = bb_amount
        if bb_player.chips == 0:
            bb_player.is_all_in = True
        self.pot += bb_amount

        self.current_bet = max(sb_amount, bb_amount)

        # 블라인드는 강제 베팅이므로 has_acted=True, 단 BB는 raise 기회를 위해 False 유지
        sb_player.has_acted = True
        bb_player.has_acted = False  # BB는 모두 콜했을 때 check/raise 가능

        self.last_aggressor = bb_player.player_id

        # PREFLOP 배팅 시작 위치: UTG (BB 다음)
        self.current_player_index = (bb_idx + 1) % n

        self.logs.append(f"스몰 블라인드: {sb_player.name} ({sb_amount}칩), 빅 블라인드: {bb_player.name} ({bb_amount}칩)")

    def start_betting_round(self):
        """플롭/턴/리버 배팅 라운드 시작 (SB부터)"""
        active = self._active_players()
        n = len(active)
        if n == 0:
            return

        for p in active:
            p.has_acted = False
            p.current_bet = 0

        self.current_bet = 0
        self.last_aggressor = None

        # SB (dealer+1)부터 시작
        self.current_player_index = self.dealer_index % n

    def get_current_player_id(self) -> Optional[str]:
        """현재 배팅 차례인 플레이어 ID"""
        bet_players = self._betting_players()
        if not bet_players:
            return None
        idx = self.current_player_index % len(bet_players)
        return bet_players[idx].player_id

    def is_betting_complete(self) -> bool:
        """모든 배팅 가능한 플레이어가 같은 금액을 베팅했는지"""
        bet_players = self._betting_players()
        if not bet_players:
            return True
        # 모두 행동했고 모두 같은 금액이어야 함
        all_acted = all(p.has_acted for p in bet_players)
        all_equal = all(p.current_bet == self.current_bet for p in bet_players)
        return all_acted and all_equal

    def process_action(self, player_id: str, action: str, raise_to: int = 0) -> bool:
        """
        플레이어 행동 처리. 배팅 라운드가 끝났으면 True 반환.
        action: 'fold' | 'check' | 'call' | 'raise' | 'allin'
        raise_to: raise 시 올릴 총 베팅 금액
        """
        player = self.players.get(player_id)
        if not player or player.is_folded or player.is_all_in:
            return False

        bet_players = self._betting_players()

        if action == 'fold':
            player.is_folded = True
            player.has_acted = True
            self.logs.append(f"{player.name}님이 폴드했습니다.")

        elif action == 'check':
            if player.current_bet != self.current_bet:
                return False  # 체크 불가
            player.has_acted = True
            self.logs.append(f"{player.name}님이 체크했습니다.")

        elif action == 'call':
            diff = self.current_bet - player.current_bet
            diff = min(diff, player.chips)
            player.chips -= diff
            player.current_bet += diff
            self.pot += diff
            if player.chips == 0:
                player.is_all_in = True
                self.logs.append(f"{player.name}님이 올인(콜)했습니다. ({diff}칩)")
            else:
                self.logs.append(f"{player.name}님이 콜했습니다. ({diff}칩)")
            player.has_acted = True

        elif action == 'raise':
            min_raise = self.current_bet + self.big_blind
            if raise_to < min_raise:
                raise_to = min_raise
            raise_to = min(raise_to, player.current_bet + player.chips)
            diff = raise_to - player.current_bet
            player.chips -= diff
            player.current_bet = raise_to
            self.pot += diff
            self.current_bet = raise_to
            if player.chips == 0:
                player.is_all_in = True
            player.has_acted = True
            self.last_aggressor = player_id
            # 다른 배팅 가능 플레이어들은 다시 행동해야 함
            for p in bet_players:
                if p.player_id != player_id:
                    p.has_acted = False
            self.logs.append(f"{player.name}님이 레이즈했습니다. (총 {raise_to}칩)")

        elif action == 'allin':
            diff = player.chips
            player.current_bet += diff
            player.chips = 0
            player.is_all_in = True
            self.pot += diff
            if player.current_bet > self.current_bet:
                self.current_bet = player.current_bet
                self.last_aggressor = player_id
                for p in bet_players:
                    if p.player_id != player_id:
                        p.has_acted = False
            player.has_acted = True
            self.logs.append(f"{player.name}님이 올인했습니다. ({diff}칩)")

        # 다음 배팅 플레이어로 이동
        self._advance_player()

        return self.is_betting_complete()

    def _advance_player(self):
        """다음 배팅 가능한 플레이어로 인덱스 이동"""
        bet_players = self._betting_players()
        if not bet_players:
            return
        self.current_player_index = (self.current_player_index + 1) % len(bet_players)

    def evaluate_hand(self, player: Player) -> Tuple[HandRank, List[int]]:
        all_cards = player.hand + self.community_cards
        if len(all_cards) < 5:
            return (HandRank.HIGH_CARD, [])

        all_cards.sort(key=lambda x: x.rank.value, reverse=True)

        suits = [c.suit for c in all_cards]
        suit_counts = Counter(suits)
        flush_suit = next((s for s, c in suit_counts.items() if c >= 5), None)

        flush_cards = []
        if flush_suit:
            flush_cards = [c for c in all_cards if c.suit == flush_suit]

        unique_ranks = sorted(list(set(c.rank.value for c in all_cards)), reverse=True)
        straight_high = None

        for i in range(len(unique_ranks) - 4):
            if unique_ranks[i] - unique_ranks[i+4] == 4:
                straight_high = unique_ranks[i]
                break

        if not straight_high and 14 in unique_ranks and 2 in unique_ranks and 3 in unique_ranks and 4 in unique_ranks and 5 in unique_ranks:
            straight_high = 5

        if flush_suit and straight_high:
            sf_ranks = sorted([c.rank.value for c in flush_cards], reverse=True)
            sf_unique = sorted(list(set(sf_ranks)), reverse=True)
            sf_high = None
            for i in range(len(sf_unique) - 4):
                if sf_unique[i] - sf_unique[i+4] == 4:
                    sf_high = sf_unique[i]
                    break
            if not sf_high and 14 in sf_unique and 2 in sf_unique and 3 in sf_unique and 4 in sf_unique and 5 in sf_unique:
                sf_high = 5

            if sf_high:
                if sf_high == 14: return (HandRank.ROYAL_FLUSH, [14])
                return (HandRank.STRAIGHT_FLUSH, [sf_high])

        rank_counts = Counter(c.rank.value for c in all_cards)
        quads = [r for r, c in rank_counts.items() if c == 4]
        if quads:
            kicker = max(r for r in rank_counts if r != quads[0])
            return (HandRank.FOUR_OF_A_KIND, [quads[0], kicker])

        trips = [r for r, c in rank_counts.items() if c == 3]
        pairs = [r for r, c in rank_counts.items() if c == 2]

        if trips:
            trips.sort(reverse=True)
            top_trip = trips[0]
            if len(trips) > 1:
                return (HandRank.FULL_HOUSE, [top_trip, trips[1]])
            if pairs:
                pairs.sort(reverse=True)
                return (HandRank.FULL_HOUSE, [top_trip, pairs[0]])

        if flush_suit:
            return (HandRank.FLUSH, [c.rank.value for c in flush_cards[:5]])

        if straight_high:
            return (HandRank.STRAIGHT, [straight_high])

        if trips:
            kickers = sorted([r for r in rank_counts if r != trips[0]], reverse=True)[:2]
            return (HandRank.THREE_OF_A_KIND, [trips[0]] + kickers)

        if len(pairs) >= 2:
            pairs.sort(reverse=True)
            kicker = max([r for r in rank_counts if r not in pairs[:2]])
            return (HandRank.TWO_PAIR, pairs[:2] + [kicker])

        if pairs:
            kickers = sorted([r for r in rank_counts if r != pairs[0]], reverse=True)[:3]
            return (HandRank.ONE_PAIR, [pairs[0]] + kickers)

        return (HandRank.HIGH_CARD, [c.rank.value for c in all_cards[:5]])

    def next_phase(self):
        if self.state == GameState.PREFLOP:
            self.state = GameState.FLOP
            self.deck.pop()
            self.community_cards.extend([self.deck.pop() for _ in range(3)])
            self.logs.append("플롭(Flop) 카드가 공개되었습니다.")
            self.start_betting_round()
        elif self.state == GameState.FLOP:
            self.state = GameState.TURN
            self.deck.pop()
            self.community_cards.append(self.deck.pop())
            self.logs.append("턴(Turn) 카드가 공개되었습니다.")
            self.start_betting_round()
        elif self.state == GameState.TURN:
            self.state = GameState.RIVER
            self.deck.pop()
            self.community_cards.append(self.deck.pop())
            self.logs.append("리버(River) 카드가 공개되었습니다.")
            self.start_betting_round()
        elif self.state == GameState.RIVER:
            self.state = GameState.SHOWDOWN
            self.resolve_winner()

    def resolve_winner(self):
        self.logs.append("쇼다운! 승자를 결정합니다.")
        best_rank_val = -1
        winners = []

        active_players = [p for p in self.players.values() if not p.is_folded]

        # 폴드로 인해 한 명 남은 경우
        if len(active_players) == 1:
            winner = active_players[0]
            winner.chips += self.pot
            self.logs.append(f"승자: {winner.name} (나머지 모두 폴드, +{self.pot}칩)")
            self.state = GameState.WAITING
            self.dealer_index = (self.dealer_index + 1) % max(1, len(self._active_players()))
            return

        for p in active_players:
            rank_enum, kickers = self.evaluate_hand(p)
            p.best_hand_rank = rank_enum
            score = rank_enum.value * 10000000000
            for i, k in enumerate(kickers):
                score += k * (100**(4-i))

            if score > best_rank_val:
                best_rank_val = score
                winners = [p]
            elif score == best_rank_val:
                winners.append(p)

        winner_names = ", ".join([w.name for w in winners])
        win_amount = self.pot // len(winners)
        for w in winners:
            w.chips += win_amount

        self.logs.append(f"승자: {winner_names} ({winners[0].best_hand_rank.name if winners else 'None'}, +{win_amount}칩)")
        self.state = GameState.WAITING
        self.dealer_index = (self.dealer_index + 1) % max(1, len(list(self.players.values())))
