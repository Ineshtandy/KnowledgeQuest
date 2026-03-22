import pygame
import sys
import random
import json
import threading
import queue
import urllib.request
import urllib.error
from collections import deque
from PIL import Image

pygame.init()
DEFAULT_WIDTH, DEFAULT_HEIGHT = 1000, 900
WINDOW_FLAGS = pygame.RESIZABLE
screen = pygame.display.set_mode((DEFAULT_WIDTH, DEFAULT_HEIGHT), WINDOW_FLAGS)
WIDTH, HEIGHT = screen.get_size()
pygame.display.set_caption("Western Boss Fight")
clock = pygame.time.Clock()
font = pygame.font.Font(None, 28)
question_font = pygame.font.Font(None, 30)
input_font = pygame.font.Font(None, 30)

# rgb color setup
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLACK = (0, 0, 0)
PARCHMENT = (248, 237, 214)
PARCHMENT_EDGE = (120, 90, 60)
INPUT_BG = (250, 250, 250)
INPUT_EDGE = (65, 65, 65)
INPUT_DISABLED = (225, 225, 225)

# Western palette
DESERT_SAND = (235, 160, 75)
DESERT_DARK = (180, 150, 110)
SKY_BLUE = (135, 206, 235)
ROAD_GRAY = (120, 100, 80)

# Layout setup
MIN_WINDOW_WIDTH = 800
MIN_WINDOW_HEIGHT = 600
MIN_GAMEPLAY_HEIGHT = 320
CHATBOT_PANEL_HEIGHT = 96

question_panel_height = 0
chatbot_panel_height = CHATBOT_PANEL_HEIGHT
gameplay_top = 0
gameplay_bottom = 0
gameplay_height = 0
gameplay_surface: pygame.Surface | None = None


def _recompute_layout(new_width: int, new_height: int) -> None:
    global WIDTH, HEIGHT
    global question_panel_height, chatbot_panel_height
    global gameplay_top, gameplay_bottom, gameplay_height
    global gameplay_surface

    WIDTH = max(MIN_WINDOW_WIDTH, int(new_width))
    HEIGHT = max(MIN_WINDOW_HEIGHT, int(new_height))

    chatbot_panel_height = CHATBOT_PANEL_HEIGHT

    desired_question_height = max(180, int(HEIGHT * 0.30))
    max_question_height = max(120, HEIGHT - chatbot_panel_height - MIN_GAMEPLAY_HEIGHT)
    question_panel_height = max(120, min(desired_question_height, max_question_height))

    gameplay_top = question_panel_height
    gameplay_bottom = HEIGHT - chatbot_panel_height
    gameplay_height = max(1, gameplay_bottom - gameplay_top)

    gameplay_surface = pygame.Surface((WIDTH, gameplay_height))


_recompute_layout(WIDTH, HEIGHT)

# Load image and make background transparent
def load_transparent_image(path, scale=1):
    pil_image = Image.open(path).convert("RGBA")
    new_data = []
    for item in pil_image.getdata():
        if item[0] > 240 and item[1] > 240 and item[2] > 240:
            new_data.append((255, 255, 255, 0))
        else:
            new_data.append(item)
    pil_image.putdata(new_data)
    w, h = pil_image.size
    pil_image = pil_image.resize((int(w*scale), int(h*scale)))
    mode = pil_image.mode
    size = pil_image.size
    data = pil_image.tobytes()
    return pygame.image.fromstring(data, size, mode).convert_alpha()

# Boss class
class BossSprite:
    def __init__(self, avif_path, scale=1):
        self.frames = self.load_avif(avif_path, scale)
        self.index = 0
        self.image = self.frames[self.index]
        self.counter = 0

    def load_avif(self, path, scale=1):
        pil_image = Image.open(path)
        frames = []
        try:
            while True:
                frame = pil_image.convert("RGBA")
                new_data = []
                for item in frame.getdata():
                    if item[0] > 240 and item[1] > 240 and item[2] > 240:
                        new_data.append((255, 255, 255, 0))
                    else:
                        new_data.append(item)
                frame.putdata(new_data)
                w, h = frame.size
                frame = frame.resize((int(w*scale), int(h*scale)))
                mode = frame.mode
                size = frame.size
                data = frame.tobytes()
                surface = pygame.image.fromstring(data, size, mode).convert_alpha()
                frames.append(surface)
                pil_image.seek(pil_image.tell() + 1)
        except EOFError:
            pass
        return frames

    def draw(self, surface, x, y, scale=1.0):
        w, h = self.image.get_size()
        scaled = pygame.transform.scale(self.image, (int(w*scale), int(h*scale)))
        surface.blit(scaled, (x - scaled.get_width()//2, y - scaled.get_height()//2))

# Golden Arrow Bullet class
class Bullet:
    def __init__(
        self,
        x: int,
        y: int,
        target_y: int,
        *,
        speed: int = 12,
        authorized_damage: int = 0,
        phase_id: int = 0,
    ):
        self.x = x
        self.y = y
        self.target_y = target_y
        self.speed = speed
        self.hit = False
        self.authorized_damage = authorized_damage
        self.phase_id = phase_id

    def update(self):
        if self.y > self.target_y:
            self.y -= self.speed
        else:
            self.hit = True

    def draw(self, surface):
        tip_color = (255, 215, 0)
        body_color = (212, 175, 55)
        pygame.draw.polygon(surface, tip_color, [
            (self.x, self.y),
            (self.x - 4, self.y + 10),
            (self.x + 4, self.y + 10)
        ])
        pygame.draw.rect(surface, body_color, (self.x - 2, self.y + 10, 4, 15))

# load cowboy
cowboy_img = load_transparent_image("cowboy.jpg", scale=0.25)
cowboy_width, cowboy_height = cowboy_img.get_size()

# boss setup
bosses = [
    BossSprite("b1.png", 0.5),
    BossSprite("b2.png", 0.5),
    BossSprite("b3.png", 0.5),
    BossSprite("b4.png", 0.5),
]
boss_index = 0

# Roadside props
cactus_sprite = BossSprite("cacti.avif", 0.35)
cactus_base_image = cactus_sprite.frames[0] if cactus_sprite.frames else cactus_sprite.image


def _boss_index_for_level_index(level_index: int) -> int:
    # Backend uses 0-based level indexes.
    # Map: level 0 -> b1, level 1 -> b2, level 2 -> b3, level 3+ -> b4.
    if level_index <= 0:
        return 0
    if level_index == 1:
        return 1
    if level_index == 2:
        return 2
    return 3

# Visual HP rules (presentation only):
# - max hp always 100
# - 25 hits to clear => 4 hp per authorized hit
# - hp cannot reach 0 until backend sends level_advanced/session_finished
boss_visual_hp_max = 100
hits_to_clear = 4
hp_chunk = boss_visual_hp_max // hits_to_clear

boss_visual_hp = boss_visual_hp_max
hp_anim_current = boss_visual_hp
boss_phase_id = 0
transitioning = False
damage_flash = 0
session_finished = False

campfire_mode = False
shake_timer = 0
shake_magnitude = 4

# road setup
road_bottom_width = 280  # slightly wider
road_top_width = 120     # slightly wider
num_road_lines = 20
line_height = 10
line_spacing = 40
scroll_offset = 0.0
scroll_speed = 2.5
sky_height = 80


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _road_edges_at_y(y: float) -> tuple[float, float, float]:
    """Returns (left_edge_x, right_edge_x, depth_t) for a given y in gameplay_surface coords."""
    denom = max(1.0, float(gameplay_height - sky_height))
    depth_t = _clamp((float(y) - float(sky_height)) / denom, 0.0, 1.0)
    road_w = float(road_top_width) + depth_t * float(road_bottom_width - road_top_width)
    left_edge_x = (WIDTH / 2.0) - (road_w / 2.0)
    right_edge_x = (WIDTH / 2.0) + (road_w / 2.0)
    return left_edge_x, right_edge_x, depth_t


def _new_cactus_prop(*, y: float | None = None) -> dict:
    side = random.choice(["left", "right"])
    jitter = random.randint(-18, 18)
    base_scale = random.uniform(0.90, 1.10)
    if y is None:
        y = float(random.randint(sky_height + 10, gameplay_height - 10))
    return {"side": side, "y": float(y), "jitter": jitter, "base_scale": base_scale}


roadside_cacti: list[dict] = []
for _ in range(12):
    roadside_cacti.append(_new_cactus_prop())

# Backend-driven state
API_BASE_URL = "http://127.0.0.1:8000"
session_id: str | None = None
display_text = "What would you like to learn?"
input_mode = "topic"  # topic | answer | session_complete
awaiting_backend = False
pending_events: deque[str] = deque()
response_queue: queue.Queue[dict] = queue.Queue()
top_scroll_y = 0
top_scroll_step = 30
backend_level_index = 0
pending_boss_index: int | None = None
pending_hp_after_transition: int | None = None


def _post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _submit_to_backend(text: str) -> None:
    global session_id
    try:
        if session_id is None:
            result = _post_json(f"{API_BASE_URL}/sessions", {"topic": text})
        else:
            result = _post_json(f"{API_BASE_URL}/sessions/{session_id}/answer", {"answer": text})
        response_queue.put({"ok": True, "result": result})
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
        response_queue.put({"ok": False, "error": str(exc)})


def _wrap_line(text: str, active_font: pygame.font.Font, max_w: int) -> list[str]:
    if not text:
        return [""]

    words = text.split(" ")
    lines: list[str] = []
    current = ""

    def push_current() -> None:
        nonlocal current
        lines.append(current)
        current = ""

    for word in words:
        candidate = f"{current} {word}".strip() if current else word
        if candidate and active_font.size(candidate)[0] <= max_w:
            current = candidate
            continue

        if current:
            push_current()

        if active_font.size(word)[0] <= max_w:
            current = word
            continue

        # Hard break a very long token by characters.
        chunk = ""
        for ch in word:
            chunk_candidate = f"{chunk}{ch}"
            if chunk_candidate and active_font.size(chunk_candidate)[0] <= max_w:
                chunk = chunk_candidate
            else:
                lines.append(chunk)
                chunk = ch
        current = chunk

    if current:
        push_current()

    return lines


def _layout_wrapped_lines(text: str, active_font: pygame.font.Font, max_w: int) -> list[str]:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    paragraph_lines = normalized.split("\n")

    wrapped: list[str] = []
    for paragraph in paragraph_lines:
        if not paragraph:
            wrapped.append("")
            continue
        wrapped.extend(_wrap_line(paragraph, active_font, max_w))
    return wrapped


def _measure_wrapped_text_height(
    text: str,
    active_font: pygame.font.Font,
    max_w: int,
    *,
    line_spacing: int = 4,
) -> int:
    wrapped_lines = _layout_wrapped_lines(text, active_font, max_w)
    line_h = active_font.get_linesize() + line_spacing
    return max(line_h, len(wrapped_lines) * line_h)


def _tail_text_for_width(text: str, active_font: pygame.font.Font, max_w: int) -> str:
    if not text:
        return ""
    if active_font.size(text)[0] <= max_w:
        return text

    out = ""
    for ch in reversed(text):
        candidate = ch + out
        if active_font.size(candidate)[0] <= max_w:
            out = candidate
        else:
            break
    return out


def _render_wrapped_text(
    surface: pygame.Surface,
    text: str,
    rect: pygame.Rect,
    color: tuple[int, int, int],
    *,
    scroll_y: int,
    active_font: pygame.font.Font,
    line_spacing: int = 4,
) -> tuple[bool, bool]:
    wrapped_lines = _layout_wrapped_lines(text, active_font, rect.width)
    line_h = active_font.get_linesize() + line_spacing
    content_h = max(line_h, len(wrapped_lines) * line_h)
    max_scroll = max(0, content_h - rect.height)
    clamped_scroll = max(0, min(scroll_y, max_scroll))

    start_idx = clamped_scroll // line_h
    y = rect.y - (clamped_scroll % line_h)

    old_clip = surface.get_clip()
    surface.set_clip(rect)
    for line in wrapped_lines[start_idx:]:
        if y >= rect.bottom:
            break
        if y + line_h > rect.y:
            rendered = active_font.render(line, True, color)
            surface.blit(rendered, (rect.x, y))
        y += line_h
    surface.set_clip(old_clip)

    return (clamped_scroll > 0, clamped_scroll < max_scroll)
user_input = ""
feedback = ""
feedback_color = RED

assert gameplay_surface is not None
bullets = []

running = True
while running:
    screen.fill(DESERT_SAND)

    # consume backend responses (non-blocking)
    while True:
        try:
            msg = response_queue.get_nowait()
        except queue.Empty:
            break

        awaiting_backend = False
        if not msg.get("ok"):
            feedback = "Network error"
            feedback_color = RED
            pending_events.append("error_state")
            continue

        result = msg.get("result") or {}
        if session_id is None and result.get("session_id"):
            session_id = result.get("session_id")

        raw_level_index = result.get("current_level_index")
        if isinstance(raw_level_index, int):
            backend_level_index = raw_level_index

        new_display_text = str(result.get("display_text") or display_text)
        if new_display_text != display_text:
            top_scroll_y = 0
        display_text = new_display_text
        input_mode = str(result.get("input_mode") or input_mode)
        events = result.get("ui_events") or []
        if isinstance(events, list):
            for e in events:
                if isinstance(e, str):
                    pending_events.append(e)
        if bool(result.get("session_complete")):
            session_finished = True

    # question panel
    pygame.draw.rect(screen, PARCHMENT, (0, 0, WIDTH, question_panel_height))
    pygame.draw.rect(screen, PARCHMENT_EDGE, (0, 0, WIDTH, question_panel_height), 2)
    question_text_rect = pygame.Rect(10, 10, WIDTH - 20, question_panel_height - 20)
    top_content_h = _measure_wrapped_text_height(
        display_text,
        question_font,
        question_text_rect.width,
        line_spacing=6,
    )
    top_scroll_max = max(0, top_content_h - question_text_rect.height)
    if top_scroll_y > top_scroll_max:
        top_scroll_y = top_scroll_max

    can_scroll_up, can_scroll_down = _render_wrapped_text(
        screen,
        display_text,
        question_text_rect,
        BLACK,
        scroll_y=top_scroll_y,
        active_font=question_font,
        line_spacing=6,
    )
    if can_scroll_up:
        screen.blit(font.render("^", True, PARCHMENT_EDGE), (WIDTH - 28, 6))
    if can_scroll_down:
        screen.blit(font.render("v", True, PARCHMENT_EDGE), (WIDTH - 28, question_panel_height - 30))

    # chatbot panel
    pygame.draw.rect(screen, WHITE, (0, HEIGHT-chatbot_panel_height, WIDTH, chatbot_panel_height))
    pygame.draw.rect(screen, BLACK, (0, HEIGHT-chatbot_panel_height, WIDTH, chatbot_panel_height), 2)
    if input_mode == "topic":
        prompt = "Type a topic"
    elif input_mode == "session_complete":
        prompt = "Session complete"
    else:
        prompt = "Type your answer"

    prompt_surface = font.render(f"{prompt}:", True, BLACK)
    prompt_y = HEIGHT - chatbot_panel_height + 8
    screen.blit(prompt_surface, (10, prompt_y))

    input_rect = pygame.Rect(10, HEIGHT - chatbot_panel_height + 36, WIDTH - 20, 36)
    if awaiting_backend or input_mode == "session_complete":
        fill_color = INPUT_DISABLED
    else:
        fill_color = INPUT_BG
    pygame.draw.rect(screen, fill_color, input_rect)
    pygame.draw.rect(screen, INPUT_EDGE, input_rect, 2)

    input_padding_x = 8
    visible_area_w = input_rect.width - (input_padding_x * 2)
    visible_text = _tail_text_for_width(user_input, input_font, visible_area_w)
    text_surface = input_font.render(visible_text, True, BLACK)
    text_x = input_rect.x + input_padding_x
    text_y = input_rect.y + (input_rect.height - text_surface.get_height()) // 2
    screen.blit(text_surface, (text_x, text_y))

    # Blinking caret indicates the field is active.
    caret_on = ((pygame.time.get_ticks() // 500) % 2 == 0)
    if input_mode != "session_complete" and not awaiting_backend and caret_on:
        caret_x = text_x + text_surface.get_width() + 1
        caret_top = input_rect.y + 6
        caret_bottom = input_rect.y + input_rect.height - 6
        if caret_x <= input_rect.right - input_padding_x:
            pygame.draw.line(screen, BLACK, (caret_x, caret_top), (caret_x, caret_bottom), 2)

    screen.blit(font.render(feedback, True, feedback_color), (10, HEIGHT-22))

    # fill initial game surface
    gameplay_surface.fill(DESERT_SAND)

    # draw sky gradient
    for i in range(sky_height):
        ratio = i / sky_height
        r = int(135 + (255 - 135) * ratio)
        g = int(206 + (220 - 206) * ratio)
        b = int(235 + (180 - 235) * ratio)
        pygame.draw.line(gameplay_surface, (r, g, b), (0, i), (WIDTH, i))

    # draw trapezoidal road
    pygame.draw.polygon(gameplay_surface, ROAD_GRAY, [
        (WIDTH//2 - road_top_width//2, sky_height),
        (WIDTH//2 + road_top_width//2, sky_height),
        (WIDTH//2 + road_bottom_width//2, gameplay_height),
        (WIDTH//2 - road_bottom_width//2, gameplay_height)
    ])

    # draw road lines
    for i in range(num_road_lines):
        y = gameplay_height - (i*(line_spacing+line_height) - scroll_offset) % gameplay_height
        if y >= sky_height:
            scale = (y - sky_height) / (gameplay_height - sky_height)
            h = int(line_height + scale*30)
            pygame.draw.rect(gameplay_surface, WHITE, (WIDTH//2 - 2, y, 4, h))

    # draw moving pebbles on road
    for _ in range(20):
        x = random.randint(0, WIDTH)
        y = random.randint(sky_height, gameplay_height)
        pygame.draw.circle(gameplay_surface, DESERT_DARK, (x, y), 2)

    # roadside cacti (planted just outside the road edges)
    cactus_margin = 22
    min_cactus_scale = 0.25
    max_cactus_scale = 0.85
    for cactus in sorted(roadside_cacti, key=lambda c: c.get("y", 0.0)):
        y_base = float(cactus.get("y", float(sky_height)))
        if y_base < float(sky_height):
            continue
        left_edge_x, right_edge_x, depth_t = _road_edges_at_y(y_base)
        prop_scale = (min_cactus_scale + depth_t * (max_cactus_scale - min_cactus_scale)) * float(cactus.get("base_scale", 1.0))

        src_w, src_h = cactus_base_image.get_size()
        dst_w = max(1, int(src_w * prop_scale))
        dst_h = max(1, int(src_h * prop_scale))
        cactus_img = pygame.transform.scale(cactus_base_image, (dst_w, dst_h))

        jitter = int(cactus.get("jitter", 0))
        if cactus.get("side") == "right":
            x_base = int(right_edge_x + cactus_margin + jitter)
        else:
            x_base = int(left_edge_x - cactus_margin + jitter)

        # Plant on the ground at y_base: bottom of sprite sits on y_base.
        draw_x = x_base - (dst_w // 2)
        draw_y = int(y_base) - dst_h
        gameplay_surface.blit(cactus_img, (draw_x, draw_y))

    # set cowboy position
    cowboy_x = WIDTH // 2
    cowboy_y = gameplay_height - 60

    # Play pending backend-driven events (stop when one starts a transition)
    while pending_events and not transitioning:
        evt = pending_events.popleft()
        if evt == "answer_correct":
            bullets.append(
                Bullet(
                    cowboy_x,
                    cowboy_y,
                    100,
                    authorized_damage=hp_chunk,
                    phase_id=boss_phase_id,
                )
            )
            feedback = "Hit!"
            feedback_color = GREEN
        elif evt == "answer_incorrect":
            feedback = "Miss!"
            feedback_color = RED
            shake_timer = 12
        elif evt == "teaching_started":
            campfire_mode = True
        elif evt == "level_demoted":
            pending_boss_index = _boss_index_for_level_index(backend_level_index)
            pending_hp_after_transition = 75
            boss_visual_hp = 0
            hp_anim_current = 0
            transitioning = True
        elif evt == "level_advanced":
            # HP may become 0 only as a finisher for backend-approved advancement.
            pending_boss_index = _boss_index_for_level_index(backend_level_index)
            pending_hp_after_transition = boss_visual_hp_max
            boss_visual_hp = 0
            hp_anim_current = 0
            transitioning = True
        elif evt == "session_finished":
            session_finished = True
            boss_visual_hp = 0
            hp_anim_current = 0
        elif evt == "error_state":
            feedback = "Backend error"
            feedback_color = RED
        # question_presented/state_synced: no direct animation needed in MVP

    # draw bullets
    for bullet in bullets[:]:
        bullet.update()
        bullet.draw(gameplay_surface)
        if bullet.hit:
            # Late-hit protection: ignore hits during transitions or after phase change.
            if (not transitioning) and bullet.phase_id == boss_phase_id and bullet.authorized_damage > 0:
                boss_visual_hp = max(1, boss_visual_hp - int(bullet.authorized_damage))
                damage_flash = 15
            bullets.remove(bullet)

    # boss setup
    if boss_index < len(bosses) and boss_visual_hp > 0 and not transitioning:
        boss = bosses[boss_index]
        if damage_flash > 0:
            img = boss.image.copy()
            img.fill((255,0,0,100), special_flags=pygame.BLEND_RGBA_MULT)
            gameplay_surface.blit(pygame.transform.scale(img, (64,64)), (WIDTH//2-32, 80))
            damage_flash -= 1
        else:
            boss.draw(gameplay_surface, WIDTH//2, 100, 0.5)

    # create HP box
    if boss_visual_hp > 0:
        if hp_anim_current > boss_visual_hp:
            hp_anim_current -= 1
        hp_box_w = 150
        hp_box_h = 40
        hp_box_x = max(10, WIDTH - hp_box_w - 30)
        hp_box_y = 10
        pygame.draw.rect(gameplay_surface, BLACK, (hp_box_x, hp_box_y, hp_box_w, hp_box_h))
        pygame.draw.rect(gameplay_surface, WHITE, (hp_box_x, hp_box_y, hp_box_w, hp_box_h), 2)
        pygame.draw.rect(gameplay_surface, RED, (hp_box_x + 2, hp_box_y + 2, hp_box_w - 4, hp_box_h - 4))
        green_w = int((hp_box_w - 4) * (hp_anim_current / boss_visual_hp_max))
        pygame.draw.rect(gameplay_surface, GREEN, (hp_box_x + 2, hp_box_y + 2, green_w, hp_box_h - 4))
        hp_label = font.render(f"{boss_visual_hp}", True, WHITE)
        label_x = hp_box_x + (hp_box_w - hp_label.get_width()) // 2
        label_y = hp_box_y + (hp_box_h - hp_label.get_height()) // 2
        gameplay_surface.blit(hp_label, (label_x, label_y))

    # Teaching/campfire overlay
    if campfire_mode and not transitioning:
        overlay = pygame.Surface((WIDTH, gameplay_height), pygame.SRCALPHA)
        overlay.fill((255, 200, 120, 80))
        gameplay_surface.blit(overlay, (0, 0))

    # Draw cowboy 
    gameplay_surface.blit(
        cowboy_img,
        (cowboy_x - cowboy_width // 2, cowboy_y - cowboy_height // 2)
    )

    # Optional screen shake
    shake_x = 0
    shake_y = 0
    if shake_timer > 0:
        shake_timer -= 1
        shake_x = random.randint(-shake_magnitude, shake_magnitude)
        shake_y = random.randint(-shake_magnitude, shake_magnitude)

    screen.blit(gameplay_surface, (0 + shake_x, gameplay_top + shake_y))

    # Events
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.VIDEORESIZE:
            screen = pygame.display.set_mode((event.w, event.h), WINDOW_FLAGS)
            _recompute_layout(event.w, event.h)
            for cactus in roadside_cacti:
                cactus["y"] = float(_clamp(float(cactus.get("y", float(sky_height))), float(sky_height + 10), float(gameplay_height - 10)))
        elif event.type == pygame.MOUSEWHEEL:
            top_scroll_y = max(0, min(top_scroll_max, top_scroll_y - event.y * top_scroll_step))
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                top_scroll_y = max(0, min(top_scroll_max, top_scroll_y - top_scroll_step))
                continue
            if event.key == pygame.K_DOWN:
                top_scroll_y = max(0, min(top_scroll_max, top_scroll_y + top_scroll_step))
                continue

            if not transitioning and not session_finished:
                if event.key == pygame.K_RETURN:
                    typed = user_input.strip()
                    if not typed or awaiting_backend:
                        continue
                    awaiting_backend = True
                    feedback = "Thinking..."
                    feedback_color = BLACK
                    user_input = ""
                    t = threading.Thread(target=_submit_to_backend, args=(typed,), daemon=True)
                    t.start()
                elif event.key == pygame.K_BACKSPACE:
                    user_input = user_input[:-1]
                else:
                    user_input += event.unicode

    if transitioning:
        scroll_offset += scroll_speed
        for cactus in roadside_cacti:
            cactus["y"] = float(cactus.get("y", float(sky_height))) + float(scroll_speed)
            if float(cactus["y"]) > float(gameplay_height + 80):
                cactus.update(_new_cactus_prop(y=float(random.randint(sky_height + 6, sky_height + 36))))
        if scroll_offset >= gameplay_height:
            scroll_offset = 0
            transitioning = False
            boss_phase_id += 1
            if pending_boss_index is not None:
                boss_index = max(0, min(pending_boss_index, len(bosses) - 1))
            else:
                boss_index = max(0, min(_boss_index_for_level_index(backend_level_index), len(bosses) - 1))

            next_hp = pending_hp_after_transition if pending_hp_after_transition is not None else boss_visual_hp_max
            boss_visual_hp = next_hp
            hp_anim_current = next_hp
            bullets.clear()
            damage_flash = 0
            pending_boss_index = None
            pending_hp_after_transition = None

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()