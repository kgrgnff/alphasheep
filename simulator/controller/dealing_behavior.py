from abc import ABC, abstractmethod
from typing import Iterable, List

import numpy as np
import yaml

from simulator.card_defs import new_deck, Card, Suit, Pip
from simulator.game_mode import GameMode, GameContract
from utils.log_util import get_class_logger
from utils.file_util import load_deck_from_yaml

class DealingBehavior(ABC):
    """
    Base class for various kinds of (possibly biased) dealers.
    """

    # def __init__(self):
    #     """
    #     Init logging framework
    #     """
    #     self.logger = get_class_logger(self)
    #     self.logger.debug("Initializing dealing behavior.")

    @abstractmethod
    def deal_hands(self) -> List[Iterable[Card]]:
        """
        Deals 4 hands (one for each player) of 8 cards each.
        :return: list(4) of iterable(8). The list indices correspond to absolute player ids (are not rotated after games).
        """
        pass


class DealFairly(DealingBehavior):
    """
    Default / baseline dealer - randomly shuffles the deck and deals the cards.
    """

    def deal_hands(self) -> List[Iterable[Card]]:
        deck = new_deck()
        np.random.shuffle(deck)

        player_hands = [set(deck[i*8:(i+1)*8]) for i in range(4)]
        return player_hands


class DealWinnableHand(DealingBehavior):
    """
    This dealer is cheating - they always make sure that player X can play a specific game!
    """

    def __init__(self, game_mode: GameMode):
        assert game_mode.declaring_player_id is not None
        self._game_mode = game_mode
        self.logger = get_class_logger(self)
        self.logger.debug("Initializing deal winnable hand with game: " + str(game_mode))

    def deal_hands(self) -> List[Iterable[Card]]:
        deck = new_deck()

        # Repeat random shuffles until the player's cards are good enough.
        i = 0
        while True:
            np.random.shuffle(deck)
            player_hands = [set(deck[i * 8:(i + 1) * 8]) for i in range(4)]
            if self._are_cards_suitable(player_hands[self._game_mode.declaring_player_id], self._game_mode):
                return player_hands
            i += 1
            assert i < 2000

    def _are_cards_suitable(self, cards_in_hand, game_mode: GameMode):
        # Quick and dirty heuristic for deciding whether to play a solo.

        #if game_mode.contract != GameContract.suit_solo:
        #   raise NotImplementedError("Only Suit-solo is implemented at this time.")

        if game_mode.contract != GameContract.suit_solo and game_mode.contract != GameContract.wenz:
            raise NotImplementedError("Only Suit-solo and Wenz is implemented at this time.")

        if game_mode.contract == GameContract.suit_solo:
            # Needs 6 trumps and either good Obers or lots of Unters.
            if sum(1 for c in cards_in_hand if game_mode.is_trump(c)) >= 6:
                if sum(1 for c in cards_in_hand if c.pip == Pip.ober) >= 2:
                    return True
                elif sum(1 for c in cards_in_hand if c.pip == Pip.unter) >= 3:
                    return True
                elif Card(Suit.eichel, Pip.ober) in cards_in_hand:
                    return True
            return False

        if game_mode.contract == GameContract.wenz:
            unters = sum(1 for c in cards_in_hand if game_mode.is_trump(c))
            # With 4 Unters:
            if unters >= 4:
                #self.logger.debug("unters count: " + str(unters))
                #self.logger.debug("missing suits: " + str(self._missing_suits(cards_in_hand, game_mode)))
                # 2 missing suits
                if self._missing_suits(cards_in_hand, game_mode) >= 2:
                    # Is Sau doppelt besetzt, 2 weitere derselben Farbe
                    if self._count_suits_along_pip(cards_in_hand, game_mode, Pip.sau) >= 3:
                        return True
                    # at least king and 10
                    if self._are_pips_in_a_suit(cards_in_hand, Pip.koenig, Pip.zehn):
                        return True
            # With 3 Unters:
            if unters >= 3:
                # 2 missing suits
                #self.logger.debug("unters count: " + str(unters))
                #self.logger.debug("missing suits: " + str(self._missing_suits(cards_in_hand, game_mode)))
                if self._are_pips_in_a_suit(cards_in_hand, Pip.ober, Pip.ober):
                    return True
                if self._missing_suits(cards_in_hand, game_mode) >= 2:
                    # Is Sau doppelt besetzt, 2 weitere derselben Farbe
                    if self._count_suits_along_pip(cards_in_hand, game_mode, Pip.sau) >= 3:
                        return False
                    # at least king and 10
                    if self._are_pips_in_a_suit(cards_in_hand, Pip.koenig, Pip.zehn):
                        return False
            # With 2 Unters:
            if unters >= 2:
                pass
            return False

        if game_mode.contract == GameContract.geier:
            pass
        if game_mode.contract == GameContract.farbwenz:
            pass
        if game_mode.contract == GameContract.farbgeier:
            pass
        if game_mode.contract == GameContract.bettel:
            raise NotImplementedError("Sorry, can only deal for a Suit-solo or Wenz right now.")
        return False

    def _missing_suits(self, cards_in_hand, game_mode: GameMode) -> int:
        """
        Return the number of missing suits (Fehlfarben)
        """
        #return [Card(suit, pip) for suit in Suit for pip in Pip]
        i = 0
        for suit in Suit:
            if sum(1 for c in cards_in_hand if c.suit == suit and not game_mode.is_trump(c)) <= 0:
                i += 1
        return i

    def _are_pips_in_a_suit(self, cards_in_hand, pip1, pip2) -> bool:
        """
        Check wether pip1 and pip2 are together in a suit in the hand
        """
        for suit in Suit:
            if Card(suit, pip1) in cards_in_hand:
                if Card(suit, pip2) in cards_in_hand:
                    return True
        return False
    
    def _count_suits_along_pip(self, cards_in_hand, game_mode: GameMode, pip) -> int:
        """
        Return the number of non-trump cards of the same suit along with the card specified.
        """
        count = 0
        count_max = 0
        for suit in Suit:
            if Card(suit, pip) in cards_in_hand:
                count = sum(1 for c in cards_in_hand if c.suit == suit and not game_mode.is_trump(c))
                # too many Spatz in a suit ?
                if count > 2:
                    if sum(1 for c in cards_in_hand if c.suit == suit and c.pip == 0) > (count - 2):
                        count = 0
            count_max = count if count > count_max else count_max
            # one with pip
        return count_max


class DealExactly(DealingBehavior):
    """
    Deals exactly the specified cards. Use for sampling the same game multiple times.
    """
    def __init__(self, player_hands: List[Iterable[Card]]):
        assert len(player_hands) == 4 and not any(cards for cards in player_hands if len(list(cards)) != 8)
        self.player_hands = player_hands

    def deal_hands(self) -> List[Iterable[Card]]:
        # Create new list/sets to prevent modification
        return [set(cards) for cards in self.player_hands]


class DealExactlyFromYAMLFile(DealingBehavior):
    """
    Deals exactly the specified cards defined a YAML file. Use for sampling the same game multiple times.
    """

    def __init__(self, filename):
        self.logger = get_class_logger(self)
        self.logger.debug(
            "Initializing deal exactly with data from YAML file: " + str(filename))
        deck = load_deck_from_yaml(filename)
        self.player_hands = [set(deck[i * 8:(i + 1) * 8]) for i in range(4)]

    def deal_hands(self) -> List[Iterable[Card]]:
        # Create new list/sets to prevent modification
        return [set(cards) for cards in self.player_hands]
