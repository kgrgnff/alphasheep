from typing import List, Optional
from enum import Enum
import yaml
from itertools import chain

from simulator.player_agent import PlayerAgent
from simulator.game_mode import GameMode
from utils.event_util import Event


class Player:
    def __init__(self, name, agent: PlayerAgent):
        self.name = name
        self.agent = agent

        self.cards_in_hand = set()              # Unordered
        self.cards_in_scored_tricks = []        # Order of playing may be important

    def __str__(self):
        return "({})".format(self.name)


class GamePhase(Enum):
    pre_deal = 0                # Nothing happening
    dealing = 1,
    bidding = 2,
    playing = 3,
    post_play = 4,              # Time to determine the winner, cleanup, post-hoc analysis.


class GameState:
    """
    GameState is the main model class of the simulator. It is intended to be reused between games.
    - The GameController owns it (create, read, write)
    - The GUI only reads from it
    - Player agents don't have access to it (of course).
    """

    def __init__(self, players: List[Player], i_player_dealer):
        self.players = players
        self.i_player_dealer = i_player_dealer
        for player in players:
            assert len(player.cards_in_hand) == 0 and len(player.cards_in_scored_tricks) == 0, "Can only initialize with fresh players."

        # Starting pre-deal, where the game has not been declared.
        self.game_phase = GamePhase.pre_deal
        self.game_mode: Optional[GameMode] = None

        # Player who plays the first card of the trick.
        self.leading_player: Optional[Player] = None
        # Player who is next to play a card. The leading player starts and then the other 3 follow.
        # -1 it is nobody's turn, e.g game play hasn't started or if all 4 cards have been added to the trick but next round hasn't started etc.
        self.current_player_index = -1

        # During the playing phase, these are the cards that are "on the table", in order of playing.
        self.current_trick_cards = []

        # Observers (such as the GUI) can subscribe to this event.
        # This fires when anything (relevant) happened, like players playing cards.
        # We might add more events for a more exciting UI in the future.
        self.ev_changed = Event()

    def clear_after_game(self):
        self.game_phase = GamePhase.pre_deal
        self.game_mode = None
        self.leading_player = None
        self.current_trick_cards.clear()
        for p in self.players:
            p.cards_in_hand.clear()
            p.cards_in_scored_tricks.clear()

 
