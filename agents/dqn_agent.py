import numpy as np
from collections import deque
from typing import Iterable, List
from tensorflow.python.keras import Sequential
from tensorflow.python.keras.layers import Dense
from tensorflow.python.keras.optimizers import Adam

from agents.agents import PlayerAgent
from game.card import Card, new_deck
from game.game_mode import GameMode
from log_util import get_class_logger


class DQNAgent(PlayerAgent):
    """
    First try: a cookie-cutter DQN implementation that tries to win, but can only ever see the current trick.

    Right now, it can only see its current cards and what is on the table. There is no history so in all probability, the agent
    should learn to play greedily. Or - who knows?

    In the long run, we'd like to extend the agent to deal with additional state, but for now we can experiment with this
    limited scenario.
    """

    def __init__(self):
        self.logger = get_class_logger(self)

        # In both states and actions, cards are encoded as one-hot vectors of size 32.
        # Providing indices to perform quick lookups: i->card->i
        self._cards = new_deck()
        self._card_indices = {card: i for i, card in enumerate(self._cards)}

        # State space: This is a tough one. For our first experiments, this contains the cards the player has in hand,
        # and the cards that are in the current trick on the table.
        # In the future, we might want to include:
        # - Number of the current trick
        # - Info about other players
        # - Info about the past... should we encode this into state, or should the agent (internally) keep some form of memory?
        #
        # For now let's be simple:
        # - The player has a one-hot vector(32) of the cards they have in hand.
        #       Putting this into a single vector because order is not important.
        # - The current trick may contain up to 3 previous cards; we encode these as 3 one-hot vectors(32).
        self._state_size = 32 + 3*32            # 128 card slots: state space << 2^128 (most are unreachable)

        # Action space: One action for every card.
        # Naturally, most actions will be disabled because the agent doesn't have the card or is not allowed to play it.
        self._action_size = 32

        # Discount and exploration rate
        self._gamma = 0.6
        self._epsilon = 0.1

        # Experience replay buffer for minibatch learning
        self.experience_buffer = deque(maxlen=2000)

        # Remember the state and action (card) played in the previous trick, so we can can judge it once we receive feedback.
        self._prev_state = None
        self._prev_action = None
        self._in_terminal_state = False

        # Create Q network (current state) and Target network (successor state). The networks are synced after every episode (game).
        self.q_network = self._build_model()
        self.target_network = self._build_model()
        self._align_target_model()
        self._batch_size = 32

        # Don't retrain after every single experience.
        # If we retrain every time, then the probability of a new experience actually being in the training batch is super low.
        # If we wait for more experiences to accumulate before retraining, we get more fresh data before doing (expensive) training.
        self._retrain_every_n = 16
        self._experiences_since_last_retrain = 0

    def _build_model(self):
        model = Sequential()
        # TODO: Is this state embedding (everything one-hot) suitable?
        model.add(Dense(256, activation='relu', input_shape=(self._state_size,)))
        model.add(Dense(128, activation='relu'))
        model.add(Dense(64, activation='relu'))
        model.add(Dense(self._action_size, activation='linear'))

        optimizer = Adam(lr=0.001)
        model.compile(loss='mse', optimizer=optimizer)
        return model

    def _align_target_model(self):
        self.target_network.set_weights(self.q_network.get_weights())

    def _receive_feedback(self, state, action, reward, next_state, terminated):
        # Store the experience into the buffer and retrain the network.

        self.experience_buffer.append((state, action, reward, next_state, terminated))

        self._experiences_since_last_retrain += 1
        if self._experiences_since_last_retrain < self._retrain_every_n:
            return

        if len(self.experience_buffer) < self._batch_size:
            return

        # Train one minibatch from the experience replay buffer.
        self._experiences_since_last_retrain = 0

        indices = np.random.choice(len(self.experience_buffer), size=self._batch_size)

        state_batch = np.empty(shape=(self._batch_size, self._state_size), dtype=np.int32)
        action_id_batch = np.empty(shape=self._batch_size, dtype=np.int32)
        reward_batch = np.empty(shape=self._batch_size, dtype=np.float32)
        next_state_batch = np.empty(shape=(self._batch_size, self._state_size), dtype=np.int32)
        terminated_batch = np.empty(shape=self._batch_size, dtype=np.bool)

        for i, index in enumerate(indices):
            state, action, reward, next_state, terminated = self.experience_buffer[index]
            state_batch[i, :] = state
            action_id_batch[i] = np.argmax(action)
            reward_batch[i] = reward
            next_state_batch[i, :] = next_state
            terminated_batch[i] = terminated

        q_curr = self.q_network.predict(state_batch)
        q_next = self.target_network.predict(next_state_batch)

        # Terminal state: the cumulative reward is exactly the observation.
        # Nonterminal state: the cumulative reward is the observation + expected future reward
        # TODO on Gamma: do we need this distinction? If we assign 1 at the end, then we are strictly episodic anyway.
        nonterminal_filter = (terminated_batch == 0)
        exp_reward = reward_batch.copy()
        exp_reward[nonterminal_filter] += self._gamma * np.amax(q_next, axis=1)[nonterminal_filter]

        # Update the Q-value for the actions that were picked. Leave the rest the same.
        q_target = q_curr.copy()
        q_target[np.arange(self._batch_size), action_id_batch] = exp_reward

        self.q_network.fit(state_batch, q_target, epochs=1, verbose=0)

    def play_card(self, cards_in_hand: Iterable[Card], cards_in_trick: List[Card], game_mode: GameMode):
        assert cards_in_trick is not None, "Empty list is allowed, None is not."
        if self._in_terminal_state:
            raise ValueError("Agent is in terminal state. Did you start a new game? Need to call notify_new_game() first.")

        # Encode the state. TODO: replace state and action with bool!
        state = np.zeros(shape=self._state_size, dtype=np.int32)
        for card in cards_in_hand:
            state[self._card_indices[card]] = 1
        for i, card in enumerate(cards_in_trick):
            state[(i+1)*32 + self._card_indices[card]] = 1

        # Save experience (previous action led to the current state).
        # Right now, we provide rewards only at the end of the game.
        if self._prev_action is not None:
            self._receive_feedback(state=self._prev_state, action=self._prev_action, reward=0, next_state=state, terminated=False)

        # Pick an action (a card).
        selected_card = None
        if np.random.rand() <= self._epsilon:
            # Explore: Select a random card (that is allowed).
            cards_in_hand = list(cards_in_hand)
            np.random.shuffle(cards_in_hand)
            for card in cards_in_hand:
                if game_mode.is_play_allowed(card, cards_in_hand=cards_in_hand, cards_in_trick=cards_in_trick):
                    selected_card = card
                    break
        else:
            # Exploit: Predict q-values for the current state and select the best action/card that is allowed.
            q_values = self.q_network.predict(state[np.newaxis, :])[0]
            i_best_actions = np.argsort(q_values)[::-1]
            for i_action in i_best_actions:
                card = self._cards[i_action]
                if card in cards_in_hand and game_mode.is_play_allowed(card, cards_in_hand=cards_in_hand, cards_in_trick=cards_in_trick):
                    selected_card = card
                    break

        if selected_card is None:
            raise ValueError("Could not find a valid card! Please debug. Sorry.")

        # Store the state and chosen action until the next call (in which we will receive feedback)
        selected_action = np.zeros(self._action_size, dtype=np.int32)
        selected_action[self._card_indices[selected_card]] = 1

        self._prev_state = state
        self._prev_action = selected_action

        return selected_card

    def notify_game_result(self, won: bool, own_score: int, partner_score: int = None):
        # Entering the terminal state (all cards have been played and the result is announced).

        assert self._prev_action is not None and self._prev_state is not None

        # No cards anywhere = all zeros
        state = np.zeros(self._state_size, dtype=np.int32)

        # TODO: we may want to increase reward based on total score. Something like that...?
        # reward = own_score if won else 0.
        reward = 1. if won else 0.

        # Add feedback, sync
        self._receive_feedback(state=self._prev_state, action=self._prev_action, reward=reward, next_state=state, terminated=True)
        self._align_target_model()          # The episode is over, sync the models.

    def notify_new_game(self):
        # Reset everything concerning the current game state.
        # Don't reset the models and experiences of course.
        # This call basically signals the begin of a new episode.

        self._prev_state = None
        self._prev_action = None
        self._in_terminal_state = False

    def save_weights(self, filepath, overwrite=True):
        self.q_network.save_weights(filepath, overwrite=overwrite)

    def load_weights(self, filepath):
        self.q_network.load_weights(filepath)
        self._align_target_model()
