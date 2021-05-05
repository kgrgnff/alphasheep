import yaml
from simulator.card_defs import Card, Pip, Suit, PIP_CODE, SUIT_CODE


def load_deck_from_yaml(filename):
	with open(filename, "r") as f:
		t = yaml.safe_load(f)
	# self.logger.debug(f"Loaded deck from file: {t}.")
	deck = []
	for c in t:
		suit = next(key for key, value in SUIT_CODE.items() if value == c[:1])
		pip = next(key for key, value in PIP_CODE.items() if value == c[1])
		deck.append(Card(suit, pip))
	return deck


def save_deck_as_yaml(deck, filename):
	a = []
	for i, c in enumerate(deck):
		a.append(c.code)
	
	with open(filename, "w") as f:
			yaml.safe_dump(a, f)
