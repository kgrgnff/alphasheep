from utils.file_util import load_deck_from_yaml
from utils.file_util import save_deck_as_yaml
from typing import Callable

import os
import random

import pygame
import pygame.freetype
import pygame_gui
from pygame.locals import *

from simulator.card_defs import new_deck, PIP_SCORES, Pip, Suit, Card
from simulator.game_state import GameState, GamePhase
from gui.assets import get_card_img_path
from gui.card_display import sort_for_gui
from gui.gui_agent import GUIAgent

from utils.log_util import get_class_logger

SCREEN_WIDTH, SCREEN_HEIGHT = 1280, 800
#SCREEN_WIDTH, SCREEN_HEIGHT = 1600, 1000
#SCREEN_WIDTH, SCREEN_HEIGHT = 1920, 1200
CARD_OFFSET = 30  # how much cards should overlap
TEXT_OFFSET = 10
TEXT_WARNING_DIM = (450, 38)
TEXT_SURF_DIM = (200, 160)
TEXT_FONT_FACE = 'fira_code'  # https://github.com/tonsky/FiraCode
TEXT_FONT_FACE_SIZE = 4
TEXT_FONT_SIZE_ANNOTATIONS = 14.0


#TEXT_BOX_MARGIN = 10
MARGIN = 30 # margin from screen borders
MARGIN_3 = 20 # extra margin for player 3

INDEX_KEY_CODE_MAP = {
    pygame.K_1: 0,
    pygame.K_2: 1,
    pygame.K_3: 2,
    pygame.K_4: 3,
    pygame.K_5: 4,
    pygame.K_6: 5,
    pygame.K_7: 6,
    pygame.K_8: 7}

PIP_KEY_CODE_MAP = {
    pygame.K_7: '7',
    pygame.K_8: '8',
    pygame.K_9: '9',
    pygame.K_z: 'z',
    pygame.K_u: 'u',
    pygame.K_o: 'o',
    pygame.K_k: 'k',
    pygame.K_s: 's'}

SUIT_KEY_CODE_MAP = {
    pygame.K_s: 's', 
    pygame.K_h: 'h', 
    pygame.K_g: 'g', 
    pygame.K_e: 'e'}

class UserQuitGameException(Exception):
    """
    Named exception that happens when the user closes the window. This will bubble up to the controller and (likely) terminate.
    """


class Gui:
    """
    GUI that draws the current GameState using PyGame.

    Receives events (typically from GameController), upon which it can block the event call until the user has performed a specific action.
    Only works in single-threaded environments for now.

    All coordinates are currently hardcoded in absolute pixels. Contributions welcome!
    """

    def _set_resolution(self):
        #self._screen = pygame.display.set_mode(self._resolution)
        self._screen = pygame.display.set_mode(self._resolution, HWSURFACE | DOUBLEBUF | RESIZABLE)
        theme = os.path.join(os.path.join(os.path.dirname(
            os.path.realpath(__file__)), "data/themes"), "pygame_default.json")
        self._pygame_gui_manager = pygame_gui.UIManager(self._resolution, theme)
        # ui_manager.add_font_paths("Montserrat",
        #                           "data/fonts/Montserrat-Regular.ttf",..
        self._pygame_gui_manager.preload_fonts([
                                #   {'name': 'fira_code', 'point_size': 14,
                                #       'style': 'regular'},
                                #  {'name': 'fira_code',
                                #      'point_size': 14, 'style': 'bold'},
                                {'name': 'fira_code', 'html_size': 6, 'style': 'regular'},
                                {'name': 'fira_code', 'html_size': 6, 'style': 'bold'},
                                #{'name': 'fira_code', 'html_size': 4, 'style': 'regular'}, # regular font is already being preloaded
                                {'name': 'fira_code', 'html_size': 4, 'style': 'bold'},
                                  ])

    def __init__(self, game_state: GameState):
        self.game_state = game_state
        self.logger = get_class_logger(self)

        pygame.init()
        self._resolution = (SCREEN_WIDTH, SCREEN_HEIGHT)
        
        self._screen = None
        self._card_assets = None
        self._fps_clock = pygame.time.Clock()
       
        #pygame.freetype.init()
        #pygame.font.init()
        #self._font_large = pygame.font.SysFont('comicsans', 15)
        
        # Latest click - these values survive only for one draw call. During the draw call they are set, and afterwards read.
        self._clicked_pos = None
        self._clicked_card = None
        # selection of card by two char code, e.g. ks for king schellen
        #self._select_by_code = False
        self._select_by_code_first_char = ''

        # Show warning if a GUI user tried to play a wrong card etc.
        self._warning_message = ''

        # Subscribe to events of the controller
        self.game_state.ev_changed.subscribe(self.on_game_state_changed)

        # If a player agent is the GUIAgent, register a callback that blocks until the user selects a card.
        ##assert not any(isinstance(p.agent, GUIAgent) for p in self.game_state.players[1:]), "Only Player 0 can have a GUIAgent."
        def select_card_callback(reset_clicks=False):
            if reset_clicks:
                self._clicked_pos = None
            self._clicked_card = None
            self.wait_and_draw_until(
                lambda: self._clicked_card is not None)
            return self._clicked_card

        if isinstance(self.game_state.players[0].agent, GUIAgent):
            self.game_state.players[0].agent.register_gui_callback(
                select_card_callback)
        if isinstance(self.game_state.players[1].agent, GUIAgent):
            self.game_state.players[1].agent.register_gui_callback(
                select_card_callback)
        if isinstance(self.game_state.players[2].agent, GUIAgent):
            self.game_state.players[2].agent.register_gui_callback(
                select_card_callback)
        if isinstance(self.game_state.players[3].agent, GUIAgent):
            self.game_state.players[3].agent.register_gui_callback(
                select_card_callback)


    def _init_pygame_gui_elements(self):
        self._resolution_dropdown = pygame_gui.elements.UIDropDownMenu(relative_rect=pygame.Rect(
            (30, 30), (100, 40)),
            manager=self._pygame_gui_manager,
            options_list=[
                '1920x1200', '1600x1000', '1280x800'],
            starting_option='1280x800')
        self._load_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(
            (30, 70),(100, 40)),
            manager=self._pygame_gui_manager,
            text='Load')
        self._load_button.disable() # load not fully implemented
        self._save_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(
            (30, 110),(100, 40)),
            manager=self._pygame_gui_manager,
            text='Save')
        self.p_text_surf_ui = [pygame_gui.elements.UITextBox(relative_rect=pygame.Rect(
            self._player_text_topleft[i], TEXT_SURF_DIM),
            manager=self._pygame_gui_manager,  html_text='') for i in range(4)]
        self.p_warning_textbox = pygame_gui.elements.UITextBox(relative_rect=pygame.Rect(
            (MARGIN, self._resolution[1] - MARGIN - TEXT_WARNING_DIM[1]), TEXT_WARNING_DIM),
            manager=self._pygame_gui_manager,  html_text='')
       

    def __enter__(self):
        # Show PyGame window. Assets can only be loaded after this.
        #self._screen = pygame.display.set_mode(self._resolution)
        self._set_resolution()
       
        pygame.display.set_caption("Interactive Sheephead")

        font_size = TEXT_FONT_SIZE_ANNOTATIONS
        self._font_face_text = TEXT_FONT_FACE
        self._font_face_text_size = TEXT_FONT_FACE_SIZE
    
        if self._resolution[0] >= 1920 or self._resolution[1] >= 1200:
            self._card_offset = CARD_OFFSET + 20
            self._card_assets = {card: pygame.transform.scale(pygame.image.load(
                get_card_img_path(card)).convert_alpha(), (145, 255)) for card in new_deck()}
            #self._font_face_text_size = 4
            #p_text_surf_dims =
            #font_size = 24
        elif self._resolution[0] >= 1600 or self._resolution[1] >= 1000:
            self._card_offset = CARD_OFFSET + 10
            self._card_assets={card: pygame.transform.scale(pygame.image.load(
                get_card_img_path(card)).convert_alpha(), (126, 221)) for card in new_deck()}
        else:
            self._card_assets = {card: pygame.image.load(
                get_card_img_path(card)).convert_alpha() for card in new_deck()}
            #self._card_assets = {card: pygame.transform.scale(pygame.image.load(
            #    get_card_img_path(card)).convert_alpha(), (97, 170)) for card in new_deck()}
            self._card_offset = CARD_OFFSET

        self._font = pygame.freetype.SysFont('Courier New', font_size) # only for annotaions
        self._font.antialiased = True

        # self._font_large = pygame.freetype.SysFont('Courier New', font_size_large)
        # self._font_large.antialiased = True
        # self._font_large.strong = True
        # self._font.render_to(self._screen, (10, 10), "v01.beta", fgcolor="#000000FF")
        self._card_dims = self._card_assets[Card(Suit.schellen, Pip.sieben)].get_rect()[2:]
        # Every player has a "Card surface" onto which their cards are drawn.
        # This card surface is then rotated and translated into position.
        p_card_surf_dims = (self._card_dims[0] + 7 * self._card_offset, self._card_dims[1])
        p_text_surf_dims = TEXT_SURF_DIM
    
        self._player_card_surfs = [pygame.Surface(p_card_surf_dims, pygame.SRCALPHA) for _ in range(4)]

        hrw = int(self._resolution[0]/2)
        hrh = int(self._resolution[1]/2)
        hcw = int(p_card_surf_dims[0]/2)
        ch = p_card_surf_dims[1]
        rw = self._resolution[0]
        rh = self._resolution[1]

        self._player_text_topleft = [
            (hrw + hcw + TEXT_OFFSET, rh - ch - MARGIN),\
            (MARGIN, hrh + hcw + TEXT_OFFSET),
            (hrw + hcw + TEXT_OFFSET, MARGIN),
            (rw - ch - MARGIN - MARGIN_3, hrh + hcw + TEXT_OFFSET)]
        self._player_card_topleft = [
            (hrw - hcw, rh - ch - MARGIN),\
            (MARGIN, hrh - hcw),\
            (hrw - hcw, MARGIN),\
            (rw - ch - MARGIN - MARGIN_3, hrh - hcw)]

        # Surface in the middle, containing the "cards on the table".
        self._middle_trick_surf = pygame.Surface((300, 270), pygame.SRCALPHA)
        self._middle_trick_surfs = [pygame.Surface(
            (300, 300), pygame.SRCALPHA) for _ in range(4)]

        self._trick_coord_left = hrw - hcw - 30 # 480
        self._trick_coord_top = hrh - ch/2 - 50 # 260
        self._trick_coords = [  # coordinates of the 4 cards of one trick in the middle of the table
            (100, 100),
            (40, 50),
            (100, 0),
            (160, 50)
        ]
        self._trick_rotations = [
            0,
            0,
            0,
            0
        ]

        bg_path = os.path.join(os.path.join(os.path.dirname(os.path.realpath(__file__)), "data/images"), "bg.jpg")
        self._background = pygame.transform.scale(pygame.image.load(bg_path), self._resolution)
        #self._background = pygame.Surface(self.resolution)
        #self._background.fill(pygame.Color('#000000'))

        self._init_pygame_gui_elements()


    def __exit__(self, exc_type, exc_val, exc_tb):
        # Unsubscribe all events and callbacks
        if isinstance(self.game_state.players[0].agent, GUIAgent):
            self.game_state.players[0].agent.unregister_callback()
        self.game_state.ev_changed.unsubscribe(self.on_game_state_changed)

        # Quit PyGame (and hide window).
        pygame.quit()


    def _allowed_card(self, selected_card, player_index):
        if not self.game_state.game_mode.is_play_allowed(selected_card,
                                    cards_in_hand=self._player_cards[player_index],
                                    cards_in_trick=self.game_state.current_trick_cards):
            self._warning_message = "{} is not allowed!".format(selected_card)
        else:
            self._warning_message = ""


    def _draw_player_cards(self):
        # Sort each player's cards before displaying. This is only for viewing in the GUI and does not affect the Player object.
        # NOTE: this is recalculated on every draw and kinda wasteful. Might want to do lazy-updating if we need UI performance.
        #self.logger.debug(f"Game mode: {self.game_state.game_mode}")
        self._player_cards = [sort_for_gui(cards, game_mode=self.game_state.game_mode) for cards in
                        (player.cards_in_hand for player in self.game_state.players)]

        # Draw each player's cards onto their respective card surfaces.
        for i_player in range(4):
            self._player_card_surfs[i_player].fill((0, 0, 0, 0))
            for i_card, card in enumerate(self._player_cards[i_player]):
                self._player_card_surfs[i_player].blit(self._card_assets[card], (i_card*self._card_offset, 0))

        # Finally, draw the card surfaces onto the board.
        self._screen.blit(self._player_card_surfs[0], self._player_card_topleft[0])                                    # 0: Bottom
        self._screen.blit(pygame.transform.rotate(self._player_card_surfs[1], 270), self._player_card_topleft[1])      # 1: Left
        self._screen.blit(pygame.transform.rotate(self._player_card_surfs[2], 180), self._player_card_topleft[2])      # 2: Top
        self._screen.blit(pygame.transform.rotate(self._player_card_surfs[3], 90), self._player_card_topleft[3])       # 3: Right

        # Register if a previous mouse click was on top of Player 0's cards.
        # In the future, let's stop using hardcoded Pixels and do some semblance of a scene graph.
        # Unfortunately, PyGame doesn't seem to support a transform stack so let's stay with this for now. Should we move to OpenGL?
        if self.game_state.game_phase == GamePhase.playing:
            if self.game_state.current_player_index == 0 and self.game_state.players[0].agent.__class__.__name__ == "GUIAgent":
                if self._clicked_pos is not None and self._player_card_surfs[0].get_rect().move(self._player_card_topleft[0]).collidepoint(*self._clicked_pos):
                    rect = pygame.Rect(*self._player_card_topleft[0], *self._card_dims)
                    n_cards = len(self._player_cards[0])
                    clicked_card = None
                    for i in reversed(range(n_cards)):
                        test_rect = rect.move(i * self._card_offset, 0)           # moving from right to left
                        if test_rect.collidepoint(*self._clicked_pos):
                            clicked_card = self._player_cards[0][i]
                            break
                    if clicked_card:
                        self._allowed_card(clicked_card, 0)
                        self._clicked_card = clicked_card
                        #self.logger.debug(f"Player 9 clicked on {clicked_card}")
            if self.game_state.current_player_index == 1 and self.game_state.players[1].agent.__class__.__name__ == "GUIAgent":
                if self._clicked_pos is not None and \
                    pygame.transform.rotate( \
                        self._player_card_surfs[1], 270).get_rect().move(self._player_card_topleft[1]).collidepoint(*self._clicked_pos):
                    s = pygame.Surface(self._card_dims)
                    rect = pygame.transform.rotate(s, 270).get_rect().move(self._player_card_topleft[1])
                    n_cards = len(self._player_cards[1])
                    clicked_card = None
                    for i in reversed(range(n_cards)):               # move from bottom to top
                        test_rect = rect.move(0, i * self._card_offset)
                        if test_rect.collidepoint(*self._clicked_pos):
                            clicked_card = self._player_cards[1][i]
                            break
                    if clicked_card:
                        self._allowed_card(clicked_card, 1)
                        self._clicked_card = clicked_card
                        #self.logger.debug(f"Player 1 clicked on {clicked_card}")
            if self.game_state.current_player_index == 2 and self.game_state.players[2].agent.__class__.__name__ == "GUIAgent":
                if self._clicked_pos is not None and self._player_card_surfs[2].get_rect().move(self._player_card_topleft[2]).collidepoint(*self._clicked_pos):
                #if self._clicked_pos is not None and pygame.transform.rotate(
                #       self._player_card_surfs[2], 180).get_rect().move(self._player_card_topleft[2]).collidepoint(*self._clicked_pos):
                    s = pygame.Surface(self._card_dims)
                    #rect = pygame.transform.rotate(s, 180).get_rect().move(
                    #    self._player_card_topleft[2][0] + 7 * self._card_offset, self._player_card_topleft[2][1])
                    rect = s.get_rect().move(self._player_card_topleft[2][0] + 7 * self._card_offset, self._player_card_topleft[2][1])
                    n_cards = len(self._player_cards[2])
                    clicked_card = None
                    for i in reversed( range(n_cards)):
                        test_rect = rect.move(-i * self._card_offset, 0)           # move from left to right
                        if test_rect.collidepoint(*self._clicked_pos):
                            clicked_card = self._player_cards[2][i]
                            break
                    if clicked_card:
                        self._allowed_card(clicked_card, 2)
                        self._clicked_card = clicked_card
                        #self.logger.debug(f"Player 2 clicked on {clicked_card}")
            if self.game_state.current_player_index == 3 and self.game_state.players[3].agent.__class__.__name__ == "GUIAgent":
                if self._clicked_pos is not None and \
                    pygame.transform.rotate( \
                        self._player_card_surfs[3], 90).get_rect().move(self._player_card_topleft[3]).collidepoint(*self._clicked_pos):
                    s = pygame.Surface(self._card_dims)
                    rect = pygame.transform.rotate(s, 90).get_rect().move(
                        self._player_card_topleft[3][0], self._player_card_topleft[3][1] + 7 * self._card_offset)
                    n_cards = len(self._player_cards[3])
                    clicked_card = None
                    for i in reversed(range(n_cards)):                       # move from top to bottom
                        test_rect = rect.move(0, -i * self._card_offset)
                        # pygame.draw.rect(self._screen, pygame.Color(0, 0, 0), test_rect)
                        # pygame.display.flip()
                        # pygame.time.wait(200)
                        if test_rect.collidepoint(*self._clicked_pos):
                            # pygame.draw.rect(self._screen, pygame.Color(0, 0, 0), test_rect)
                            # pygame.display.flip()
                            # pygame.time.wait(500)
                            clicked_card = self._player_cards[3][i]
                            break
                    if clicked_card:
                        self._allowed_card(clicked_card, 3)
                        self._clicked_card = clicked_card
                        #self.logger.debug(f"Player 3 clicked on {clicked_card}")

        # More Player 0 craziness: render internal values next to cards, if available.
        if self.game_state.leading_player is not None:
            i_leader = self.game_state.players.index(self.game_state.leading_player)
            if len(self.game_state.current_trick_cards) == (0 - i_leader) % 4 + 1:
                # Only draw when Player 0 has just played a card.

                vals = self.game_state.players[0].agent.internal_card_values()
                if vals is not None:
                    col_normal = pygame.Color(0, 0, 0, 255)  # pygame.Color("#000000")
                    col_invalid = pygame.Color(85, 85, 85, 255)  # pygame.Color("#555555")

                    # Render the values of all cards in the player's hand.
                    for i, card in enumerate(self._player_cards[0]):
                        val = vals.get(card, None)
                        if val is not None:
                            # Change color depending on whether the card is allowed.
                            tmp_hand = list(self.game_state.players[0].cards_in_hand_in_hand) + [self.game_state.current_trick_cards[-1]]
                            tmp_trick = self.game_state.current_trick_cards[:-1]
                            color = col_normal
                            if not self.game_state.game_mode.is_play_allowed(card, cards_in_hand=tmp_hand, cards_in_trick=tmp_trick):
                                color = col_invalid
                            x = 477 + i * self._card_offset
                            y = 585 if i % 2 == 0 else 570
                            self._font.render_to(self._screen, (x, y), f"{val:.3f}", fgcolor=color)

                    # Also render the value of the card that was played
                    val = vals.get(self.game_state.current_trick_cards[-1], None)
                    if val is not None:
                        self._font.render_to(self._screen, (618, 538), f"{val:.3f}", fgcolor=col_normal)


    def _draw_current_trick_cards(self):
        # Draw the cards that are "on the table".

        #self._middle_trick_surf.convert_alpha()
        #self._middle_trick_surf.fill((0, 0, 0, 0))
        if self.game_state.leading_player is None:
            return                  # Before a game has started

        # Get the index of the leading player. The first card appears in their spot, and the rest clockwise.
        i_leader = self.game_state.players.index(self.game_state.leading_player)
        cards = self.game_state.current_trick_cards

        # Need to draw the cards in order of playing, so the first one is at the bottom.
        for i in range(4):
            i_player = (i_leader + i) % 4
            if len(cards) > i:
                self._middle_trick_surfs[i_player].fill((0, 0, 0, 0))
                rot_surf = pygame.transform.rotate(
                    self._card_assets[cards[i]], self._trick_rotations[i_player])
                self._screen.blit(rot_surf, (self._trick_coord_left + self._trick_coords[i_player][0], \
                                             self._trick_coord_top + self._trick_coords[i_player][1]))

    #pygame_gui:
    #- <body bgcolor='#FFFFFF'></body> - to change the background colour of encased text.
    #- <br> - to start a new line.
    #- <font face='verdana' color='#000000' size=3.5></font> - To set the font, colour and size of encased text.
    def _YELLOW(self, ff, fs, text): 
        # size={fs}
        return f"<font face='{ff}' color='#ffff00' size={fs}>{text}</font>"
    def _GREEN(self, ff, fs, text):
            # size={fs}
        return f"<font face='{ff}' color='#22bb22' size={fs}>{text}</font>"
    def _RED(self, ff, fs, text): 
        return f"<font face='{ff}' color='#ff0000' size={fs}>{text}</font>"
    def _NORMAL(self, ff, fs, text): 
        return f"<font face='{ff}' color='#CCCCCC' size={fs}>{text}</font>"

    def _draw_player_text(self):
        decl_pid = None
        if self.game_state.game_mode is not None:
            decl_pid = self.game_state.game_mode.declaring_player_id

        for i, p in enumerate(self.game_state.players):
            score = sum(PIP_SCORES[c.pip] for c in p.cards_in_scored_tricks)
            won = (score > 60) if i == decl_pid else (score >= 60)

            ff = self._font_face_text  #'fira_code'
            fs = self._font_face_text_size #= 4
            
            if (self.game_state.game_phase == GamePhase.playing and self.game_state.current_player_index == i):
                html_text = self._GREEN(ff, fs, f"Name:  {p.name}")
            else:
                html_text = self._YELLOW(ff, fs, f"Name:  {p.name}")

            html_text += '<br>' + self._NORMAL(ff, fs, f"Agent: {p.agent.__class__.__name__}")

            if i == self.game_state.i_player_dealer:
                html_text += '<br>(Dealer)'
                        
            if p == self.game_state.leading_player:
                html_text +=  '<br>(Leading)'
                                 
            if i == decl_pid:
                html_text += '<br>' + \
                    self._RED(ff, fs, f"Playing a {self.game_state.game_mode}")
        
            html_text += '<br>' + \
                f"Score: {score}"
    
            if self.game_state.game_phase == GamePhase.post_play and i == decl_pid:
                html_text += '<br>' + \
                    self._RED(ff, fs, 'Won!' if won else 'Lost!')
            #print (html_text)

            self.p_text_surf_ui[i].html_text = self._NORMAL(ff, fs, html_text)
            self.p_text_surf_ui[i].rebuild()

            #if self._warning_message != '' or self.p_warning_textbox.html_text != '' and self._warning_message == '':
            self.p_warning_textbox.html_text = self._RED(ff, fs, self._warning_message)
            self.p_warning_textbox.rebuild()


    def _draw_frame(self):
        # Draws a single frame.

        time_delta = self._fps_clock.tick(30)/1000.0  # Limit to 30FPS and set delta for pygame_gui
        self._screen.fill((0, 0, 0, 255))     # Black background
        self._screen.blit(self._background, (0, 0))    # Background image
        self._draw_player_cards()
        self._draw_current_trick_cards()
        self._draw_player_text()

        self._pygame_gui_manager.update(time_delta)
        self._pygame_gui_manager.draw_ui(self._screen)
        pygame.display.update()
        #pygame.display.flip()               # Flip buffers


    def _handle_pygame_events(self):
        # Handles events from the PyGame event queue (not the GameState events!)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                raise UserQuitGameException

            if event.type == VIDEORESIZE:
                self._resolution = event.dict['size']
                self._set_resolution()
                self.__enter__()

            # ESC = quit event.
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    raise UserQuitGameException

            # Spacebar = next event.
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    self._clicked_pos = pygame.mouse.get_pos()

                if self.game_state.game_phase == GamePhase.playing and self.game_state.current_player_index != -1:
                    if self.game_state.players[self.game_state.current_player_index].agent.__class__.__name__ == "GUIAgent":
            
                        # handle number keys
                        if self._select_by_code_first_char == '' and event.key in INDEX_KEY_CODE_MAP:
                            self._handle_number_key_pressed(INDEX_KEY_CODE_MAP[event.key])

                        # handle 2 chars key code
                        if self._select_by_code_first_char == '':
                            if event.key in SUIT_KEY_CODE_MAP:
                                self._select_by_code_first_char = SUIT_KEY_CODE_MAP[event.key]
                        elif event.key in PIP_KEY_CODE_MAP:
                            self._handle_code_keys_pressed( \
                                self._select_by_code_first_char + PIP_KEY_CODE_MAP[event.key])
                            self._select_by_code_first_char = ''
                        else: # user entered an invalid card code, start all over
                            self._select_by_code_first_char = ''

            # Mouse button = stop drawing and return control.
            if event.type == pygame.MOUSEBUTTONUP:
                # _draw_player_cards() will identify any card that was clicked on.
                self._clicked_pos = pygame.mouse.get_pos()

            # Handle pygame_gui elements
            if event.type == pygame.USEREVENT:
                if event.user_type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED:
                    if event.ui_element == self._resolution_dropdown:
                        w, h = [el.strip() for el in event.text.split('x')]
                        self._resolution = (int(w), int(h))
                        self._set_resolution()
                        self.__enter__()
                        
                if event.user_type == pygame_gui.UI_BUTTON_PRESSED:
                    if event.ui_element == self._save_button:
                        self._save_hands_as_yaml()
                    if event.ui_element == self._load_button:
                        self._load_hands_from_yaml()
                        #raise NotImplementedError("Sorry, not yet implemented.")
            
            self._pygame_gui_manager.process_events(event)


    def _handle_number_key_pressed(self, card_index):

        idx = self.game_state.current_player_index
        # if key is higher than the number of cards in hand do nothing
        if len(self.game_state.players[idx].cards_in_hand) > card_index:
            self._clicked_pos = self._get_simulated_click_pos(idx, card_index)  # workaround
            #self._clicked_pos = (8,0)
            #self._clicked_card = self._player_cards[self.game_state.current_player_index][card_index]


    def _handle_code_keys_pressed(self, code):
        #self.logger.debug(f"KEY CODE EVENT {code, self.game_state.current_player_index}")
        for card_index, card in enumerate(self._player_cards[self.game_state.current_player_index]):
            if card.code == code:
                self._handle_number_key_pressed(card_index) # workaround
                break


    def _get_simulated_click_pos(self, player_index, card_index):
        pos = None
        if not (card_index >= 0 and card_index < 8):
            raise ("card_index out of range!")
        if player_index == 1:
            pos = (self._player_card_topleft[1][0] + 10, \
                self._player_card_topleft[1][1] + card_index * self._card_offset + 20)
        elif player_index == 2:
            pos = (self._player_card_topleft[2][0] + (7 - card_index) * self._card_offset + self._card_dims[0] + 10 - self._card_offset,
                self._player_card_topleft[2][1] + 10)
        elif player_index == 3:
            pos = (self._player_card_topleft[3][0] + 10, \
                self._player_card_topleft[3][1] + (7 - card_index) * self._card_offset + self._card_dims[0] + 10 - self._card_offset)
        elif player_index == 0:
            pos = (self._player_card_topleft[0][0] \
                + card_index * self._card_offset + 20, self._player_card_topleft[0][1] + 10)
        else:
            raise ("player_index out of range!")
        return pos


    def on_game_state_changed(self):
        # Receiving this event when we should draw an update (and wait for the user to click).
        #self.logger.debug( "---> State changed.}")
        
        coords = [
            (100, 100),
            (40, 50),
            (100, 0),
            (160, 50)
        ]
        if len(self.game_state.current_trick_cards) == 0:  
            for i in range(len(coords)): # assign new coordinates to cards in tricks
                self._trick_coords[i] = (coords[i][0] + \
                    random.randint(0, 20), coords[i][1]+random.randint(0, 20))
                self._trick_rotations[i] = random.randint(0, 3)*30
  
        # Wait until the user clicks.
        self._clicked_pos = None
        self.wait_and_draw_until(lambda: self._clicked_pos is not None)
        

    def wait_and_draw_until(self, terminating_condition: Callable[[], bool]):
        # Runs the draw loop until the terminating condition returns true.
        while not terminating_condition():
            self._handle_pygame_events()
            self._draw_frame()


    def _save_hands_as_yaml(self):
        deck = []
        for i_player in range(4):
            for card in self._player_cards[i_player]:
                deck.append(card)
        save_deck_as_yaml(deck, FILENAME)


    def _load_hands_from_yaml(self):
        self.logger.warning("Loading decks is not fully supported!!!")
        #raise NotImplementedError("Sorry, not yet implemented!")
        deck = load_deck_from_yaml(FILENAME)
        cnt = int(len(deck)/4)
        for i in range(4):
            self.game_state.players[i].cards_in_scored_tricks = []
            self.game_state.players[i].cards_in_hand = set(deck[(i) * cnt:(i + 1) * cnt])
            #for card in self.game_state.players[i].cards_in_hand:
            #   self.logger.debug(card.suit, card.pip)
        self.game_state.clear_after_game()

FILENAME = 'gui/data/states/gui_deck.yaml'
