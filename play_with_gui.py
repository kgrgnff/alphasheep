"""
Runs games with an interactive GUI.

Use this for playing yourself, or watching other agents play.
Right now, only Player 0's agent can be specified, the others are RuleBasedAgents.
"""
import argparse
import logging
import os

from agents.reinforcment_learning.dqn_agent import DQNAgent
from agents.rule_based.rule_based_agent import RuleBasedAgent
from agents.dummy.static_policy_agent import StaticPolicyAgent
from simulator.controller.dealing_behavior import DealWinnableHand
from simulator.controller.dealing_behavior import DealExactlyFromYAMLFile
from simulator.controller.game_controller import GameController
from simulator.card_defs import Suit
from simulator.game_mode import GameMode, GameContract
from simulator.game_state import Player

from gui.gui import Gui, UserQuitGameException
from agents.dummy.random_card_agent import RandomCardAgent
from gui.gui_agent import GUIAgent
from utils.log_util import init_logging, get_class_logger, get_named_logger
from utils.config_util import load_config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--p0-agent", type=str,
                        choices=['static', 'rule', 'random', 'alphasheep', 'user'], required=True)
    parser.add_argument("--p1-agent", type=str,
                        choices=['static', 'rule', 'random', 'alphasheep', 'user'], required=False)
    parser.add_argument("--p2-agent", type=str,
                        choices=['static', 'rule', 'random', 'alphasheep', 'user'], required=False)
    parser.add_argument("--p3-agent", type=str,
                        choices=['static', 'rule', 'random', 'alphasheep', 'user'], required=False)
    parser.add_argument("--alphasheep-checkpoint",
                        help="Checkpoint for AlphaSheep, if --p0-agent=alphasheep.", required=False)
    parser.add_argument(
        "--agent-config", help="YAML file, containing agent specifications for AlphaSheep.", required=False)
    parser.add_argument(
         "--card-deck", help="YAML file, containing a predefined deck of cards for the card dealer.", required=False)
    args = parser.parse_args()
    agent0_choice = args.p0_agent
    agent1_choice = args.p1_agent
    agent2_choice = args.p2_agent
    agent3_choice = args.p3_agent
    as_checkpoint_path = args.alphasheep_checkpoint
    as_config_path = args.agent_config
    if agent0_choice == "alphasheep" and (not as_checkpoint_path or not as_config_path):
        raise ValueError(
            "Need to specify --alphasheep-checkpoint and --agent-config if --p0_agent=alphasheep.")

    # Init logging and adjust log levels for some classes.
    init_logging()
    logger = get_named_logger("{}.main".format(
        os.path.splitext(os.path.basename(__file__))[0]))
    # Log every single card.
    get_class_logger(GameController).setLevel(logging.DEBUG)
    # Log mouse clicks.
    get_class_logger(Gui).setLevel(logging.DEBUG)
    # Log decisions by the rule-based players.
    get_class_logger(RuleBasedAgent).setLevel(logging.DEBUG)
    get_class_logger(DealWinnableHand).setLevel(logging.DEBUG)

    # Create the agent for Player 0.
    if agent0_choice == "alphasheep":
        # Load config. We ignore the "training" and "experiment" sections, but we need "agent_config".
        logger.info(f'Loading config from "{as_config_path}"...')
        config = load_config(as_config_path)
        # Log Q-values.
        get_class_logger(DQNAgent).setLevel(logging.DEBUG)
        alphasheep_agent = DQNAgent(0, config=config, training=False)
        alphasheep_agent.load_weights(as_checkpoint_path)
        p0 = Player("0-AlphaSheep", agent=alphasheep_agent)
    elif agent0_choice == "user":
        p0 = Player("0-User", agent=GUIAgent(0))
    elif agent0_choice == "rule":
        p0 = Player("0-Hans", agent=RuleBasedAgent(0))
    elif agent0_choice == "static":
        p0 = Player("0-Static", agent=StaticPolicyAgent(0))
    else:
        p0 = Player("0-RandomGuy", agent=RandomCardAgent(0))

     # Create the agent for Player 1.
    if agent1_choice == "alphasheep":
        pass
    elif agent1_choice == "user":
        p1 = Player("1-Zenzi", agent=GUIAgent(1))
    elif agent1_choice == "rule":
        p1 = Player("1-Zensi", agent=RuleBasedAgent(1))
    elif agent1_choice == "static":
        p1 = Player("1-Static", agent=StaticPolicyAgent(1))
    else:
        p1 = Player("1-RandomGuy", agent=RandomCardAgent(1))

    # Create the agent for Player 2.
    if agent2_choice == "alphasheep":
        pass
    elif agent2_choice == "user":
        p2 = Player("2-Franz", agent=GUIAgent(2))
    elif agent2_choice == "rule":
        p2 = Player("2-Franz", agent=RuleBasedAgent(2))
    elif agent2_choice == "static":
        p2 = Player("2-Static", agent=StaticPolicyAgent(2))
    else:
        p2 = Player("2-RandomGuy", agent=RandomCardAgent(2))

    # Create the agent for Player 3.
    if agent3_choice == "alphasheep":
        pass
    elif agent3_choice == "user":
        p3 = Player("3-Andal", agent=GUIAgent(3))
    elif agent3_choice == "rule":
        p3 = Player("3-Andal", agent=RuleBasedAgent(3))
    elif agent3_choice == "static":
        p3 = Player("3-Static", agent=StaticPolicyAgent(3))
    else:
        p3 = Player("3-RandomGuy", agent=RandomCardAgent(3))

    players = [
        p0,
        p1,
        p2,
        p3,
    ]

    
    # Rig the game so Player 0 has the cards to play a Herz-Solo.
    # Also, force them to play it.

    #game_mode = GameMode(GameContract.suit_solo, trump_suit=Suit.herz, declaring_player_id=0)
    #game_mode = GameMode(GameContract.suit_solo, trump_suit=Suit.gras, declaring_player_id=0)
    game_mode = GameMode(GameContract.wenz, declaring_player_id=0)
    #game_mode = GameMode(GameContract.wenz, trump_suit=Suit.gras, declaring_player_id=0) # no farbwenz
    #game_mode = GameMode(GameContract.rufspiel, ruf_suit=Suit.herz, declaring_player_id=0)

    controller = GameController(players, dealing_behavior=DealWinnableHand(game_mode), forced_game_mode=game_mode)
    
    yamlfile = args.card_deck  # --card-deck .\gui\data\states\gui_deck.yaml
    #controller = GameController(players, dealing_behavior=DealExactlyFromYAMLFile(yamlfile), forced_game_mode=game_mode)
    
    ##controller.game_state.game_mode = game_mode # to instantaneously set the game mode

    # The GUI initializes PyGame and registers on events provided by the controller. Everything single-threaded.
    #
    # The controller runs the game as usual. Whenever the GUI receives an event, it can block execution, so the controller must wait
    # for the GUI to return control. Until then, it can draw stuff and wait for user input (mouse clicks, card choices, ...).
    logger.info("Starting GUI.")
    with Gui(controller.game_state) as gui:
        # Run an endless loop of single games.
        logger.info("Starting game loop...")
        ##logger.info(f"Gamestate mode {controller.forced_game_mode}")
        try:
            while True:
                controller.run_game()
        # Closing the window or pressing [Esc]
        except UserQuitGameException:
            logger.info("User quit game.")

    logger.info("Shutdown.")


if __name__ == '__main__':
    main()
