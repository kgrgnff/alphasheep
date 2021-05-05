"""
Definitions for Card, Suit, Pip, etc.

WARN: DO NOT CHANGE THE ENUMS IN THIS FILE!
Changing the values might affect the ordering of the state/action space of agents, and will break compatibility with previously
saved model checkpoints.
"""

from enum import IntEnum


class Suit(IntEnum):
    schellen = 0
    herz = 1
    gras = 2
    eichel = 3

    def __str__(self):
        return str(self.name)


class Pip(IntEnum):
    sieben = 1
    acht = 2
    neun = 3
    unter = 4
    ober = 5
    koenig = 6
    zehn = 7
    sau = 8

    def __str__(self):
        return str(self.name)


class Card:
    def __init__(self, suit: Suit, pip: Pip):
        self.suit = suit
        self.pip = pip
        # in line as it is set only once, instead of self._get_code()
        self.code = SUIT_CODE[self.suit] + PIP_CODE[self.pip]

        # There are some performance problems doing enum lookups, apparently Python implements them in a bit of a convoluted way.
        # We often use Card as a dict key, so this has turned out to be a bit problematic. It turns out to be much faster
        # to just precalc a unique card ID instead of comparing suits and pips (Python 3.5).
        self._unique_hash = hash(Card) * 23 + self.suit.value * 23 + self.pip.value

    def __str__(self):
        return "({} {})".format(self.suit.name, self.pip.name)

    def __eq__(self, other):
        return isinstance(other, Card) and self._unique_hash == other._unique_hash

    def __hash__(self):
        return self._unique_hash

    # def _get_code(self) -> str:
    #     """ Returns a 2 chars short name for pip and suit. 
    #     (s)chellen, h(erz), g(ras), e(ichel) is appended as first char
    #     the second char represents the corresponding pip value from the PIP_CODE dict
    #     e.g. 9g, zs, kh, se
    #     """
    #     return self.suit.name[:1] + PIP_CODE[self.pip]

PIP_SCORES = {
    Pip.sieben: 0,
    Pip.acht: 0,
    Pip.neun: 0,
    Pip.unter: 2,
    Pip.ober: 3,
    Pip.koenig: 4,
    Pip.zehn: 10,
    Pip.sau: 11}

PIP_CODE = {
    Pip.sieben: '7',
    Pip.acht: '8',
    Pip.neun: '9',
    Pip.unter: 'u',
    Pip.ober: 'o',
    Pip.koenig: 'k',
    Pip.zehn: 'z',
    Pip.sau: 's'}

SUIT_CODE = {
    Suit.schellen: 's',
    Suit.herz: 'h',
    Suit.gras: 'g',
    Suit.eichel: 'e'}

# def get_code(card) -> str:
#     """ Returns a 2 chars short name for pip and suit. 
#     (s)chellen, h(erz), g(ras), e(ichel) is appended as first char
#     the second char represents the corresponding pip value from the PIP_CODE dict
#     e.g. 9g, zs, kh, se
#     """
#     return card.suit.name[:1] + PIP_CODE[card.pip]

def new_deck():
    """ Returns an ordered deck. """
    return [Card(suit, pip) for suit in Suit for pip in Pip]
