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

    def to_dict(self, show_hand=False):
        data = {
            "id": self.player_id,
            "name": self.name,
            "chips": self.chips,
            "is_folded": self.is_folded,
            "current_bet": self.current_bet,
            "is_all_in": self.is_all_in,
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

    def add_player(self, player_id: str, name: str):
        if player_id not in self.players and len(self.players) < self.max_players:
            player = Player(player_id, name)
            # 게임이 진행 중이면 이번 라운드에는 참여하지 않음 (Folded 상태로 대기)
            if self.state != GameState.WAITING:
                player.is_folded = True
                player.hand = [] # 카드는 없음
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
        # 칩이 0인 플레이어는 제외하거나 리필 로직이 필요하지만, 일단 참여는 시킴
        active_count = len([p for p in self.players.values() if p.chips > 0])
        if active_count < 2:
            return False
            
        self.state = GameState.PREFLOP
        self.reset_deck()
        self.community_cards = []
        self.pot = 0
        self.current_bet = 0
        
        # Reset player states
        active_players = list(self.players.values())
        for p in active_players:
            if p.chips > 0:
                p.hand = [self.deck.pop(), self.deck.pop()]
                p.is_folded = False
                p.current_bet = 0
                p.is_all_in = False
                p.best_hand_rank = None
                p.best_hand_cards = []
            else:
                p.is_folded = True # 칩이 없으면 강제로 폴드(관전)
                p.hand = []
        
        self.logs.append("게임이 시작되었습니다. 카드를 분배합니다.")
        return True

    def evaluate_hand(self, player: Player) -> Tuple[HandRank, List[int]]:
        # Combine hole cards and community cards
        all_cards = player.hand + self.community_cards
        if len(all_cards) < 5:
            return (HandRank.HIGH_CARD, []) # Should not happen at showdown

        # Sort by rank desc
        all_cards.sort(key=lambda x: x.rank.value, reverse=True)
        
        # Check Flush
        suits = [c.suit for c in all_cards]
        suit_counts = Counter(suits)
        flush_suit = next((s for s, c in suit_counts.items() if c >= 5), None)
        
        flush_cards = []
        if flush_suit:
            flush_cards = [c for c in all_cards if c.suit == flush_suit]
        
        # Check Straight
        unique_ranks = sorted(list(set(c.rank.value for c in all_cards)), reverse=True)
        straight_high = None
        
        # Special Ace case (A, 5, 4, 3, 2)
        if {14, 5, 4, 3, 2}.issubset(set(unique_ranks)):
             # If no higher straight, 5-high straight
             pass 

        for i in range(len(unique_ranks) - 4):
            if unique_ranks[i] - unique_ranks[i+4] == 4:
                straight_high = unique_ranks[i]
                break
                
        # Special check for A-5 straight (Wheel)
        if not straight_high and 14 in unique_ranks and 2 in unique_ranks and 3 in unique_ranks and 4 in unique_ranks and 5 in unique_ranks:
            straight_high = 5

        # Check Straight Flush
        if flush_suit and straight_high:
            sf_ranks = sorted([c.rank.value for c in flush_cards], reverse=True)
            # Logic for SF check simplified...
            
            # Re-check straight only within flush cards
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

        # Four of a Kind
        rank_counts = Counter(c.rank.value for c in all_cards)
        quads = [r for r, c in rank_counts.items() if c == 4]
        if quads:
            kicker = max(r for r in rank_counts if r != quads[0])
            return (HandRank.FOUR_OF_A_KIND, [quads[0], kicker])

        # Full House
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

        # Flush
        if flush_suit:
            return (HandRank.FLUSH, [c.rank.value for c in flush_cards[:5]])

        # Straight
        if straight_high:
            return (HandRank.STRAIGHT, [straight_high])

        # Three of a Kind
        if trips:
            kickers = sorted([r for r in rank_counts if r != trips[0]], reverse=True)[:2]
            return (HandRank.THREE_OF_A_KIND, [trips[0]] + kickers)

        # Two Pair
        if len(pairs) >= 2:
            pairs.sort(reverse=True)
            kicker = max([r for r in rank_counts if r not in pairs[:2]])
            return (HandRank.TWO_PAIR, pairs[:2] + [kicker])

        # One Pair
        if pairs:
            kickers = sorted([r for r in rank_counts if r != pairs[0]], reverse=True)[:3]
            return (HandRank.ONE_PAIR, [pairs[0]] + kickers)

        # High Card
        return (HandRank.HIGH_CARD, [c.rank.value for c in all_cards[:5]])

    def next_phase(self):
        if self.state == GameState.PREFLOP:
            self.state = GameState.FLOP
            self.deck.pop() # burn
            self.community_cards.extend([self.deck.pop() for _ in range(3)])
            self.logs.append("플롭(Flop) 카드가 공개되었습니다.")
        elif self.state == GameState.FLOP:
            self.state = GameState.TURN
            self.deck.pop() # burn
            self.community_cards.append(self.deck.pop())
            self.logs.append("턴(Turn) 카드가 공개되었습니다.")
        elif self.state == GameState.TURN:
            self.state = GameState.RIVER
            self.deck.pop() # burn
            self.community_cards.append(self.deck.pop())
            self.logs.append("리버(River) 카드가 공개되었습니다.")
        elif self.state == GameState.RIVER:
            self.state = GameState.SHOWDOWN
            self.resolve_winner()

    def resolve_winner(self):
        self.logs.append("쇼다운! 승자를 결정합니다.")
        best_rank_val = -1
        winners = []
        
        active_players = [p for p in self.players.values() if not p.is_folded]
        
        for p in active_players:
            rank_enum, kickers = self.evaluate_hand(p)
            p.best_hand_rank = rank_enum
            # Simple scoring: enum value * 1000000 + kickers weighted
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
        
        self.logs.append(f"승자: {winner_names} ({winners[0].best_hand_rank.name if winners else 'None'})")
        self.state = GameState.WAITING

