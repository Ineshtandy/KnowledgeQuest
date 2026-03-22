import pygame
import sys
import random
from PIL import Image

pygame.init()
WIDTH, HEIGHT = 800, 700
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Western Boss Fight")
clock = pygame.time.Clock()
font = pygame.font.Font(None, 28)

# rgb color setup
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLACK = (0, 0, 0)

# Western palette
DESERT_SAND = (235, 160, 75)
DESERT_DARK = (180, 150, 110)
SKY_BLUE = (135, 206, 235)
ROAD_GRAY = (120, 100, 80)

# panel setup
question_panel_height = 100
chatbot_panel_height = 100
gameplay_top = question_panel_height
gameplay_bottom = HEIGHT - chatbot_panel_height
gameplay_height = gameplay_bottom - gameplay_top

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
    def __init__(self, x, y, target_y, speed=12):
        self.x = x
        self.y = y
        self.target_y = target_y
        self.speed = speed
        self.hit = False

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
bosses = [BossSprite("dragon.avif", 0.5), BossSprite("dragon.avif", 0.5)]
boss_index = 0
boss_hp_list = [100, 150]
boss_hp = boss_hp_list[boss_index]
hp_anim_current = boss_hp
transitioning = False
damage_flash = 0

# road setup
road_bottom_width = 280  # slightly wider
road_top_width = 120     # slightly wider
num_road_lines = 20
line_height = 10
line_spacing = 40
scroll_offset = 0.0
scroll_speed = 2.5
sky_height = 80

# test questions
def get_question():
    return random.choice([
        {"question":"7 x 8?", "options":["54","56","64","49"], "answer":"56"},
        {"question":"Capital of France?", "options":["Paris","Rome","Berlin","Madrid"], "answer":"Paris"}
    ])

current_question = get_question()
user_input = ""
feedback = ""

# set gameplay surface
gameplay_surface = pygame.Surface((WIDTH, gameplay_height))
bullets = []

running = True
while running:
    screen.fill(DESERT_SAND)

    # question panel
    pygame.draw.rect(screen, WHITE, (0, 0, WIDTH, question_panel_height))
    pygame.draw.rect(screen, BLACK, (0, 0, WIDTH, question_panel_height), 2)
    screen.blit(font.render(current_question["question"], True, BLACK), (10, 40))

    # chatbot panel
    pygame.draw.rect(screen, WHITE, (0, HEIGHT-chatbot_panel_height, WIDTH, chatbot_panel_height))
    pygame.draw.rect(screen, BLACK, (0, HEIGHT-chatbot_panel_height, WIDTH, chatbot_panel_height), 2)
    screen.blit(font.render("Type your answer: " + user_input, True, BLACK), (10, HEIGHT-90))
    screen.blit(font.render(feedback, True, RED), (10, HEIGHT-50))

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

    # set cowboy position
    cowboy_x = WIDTH // 2
    cowboy_y = gameplay_height - 60

    # draw bullets
    for bullet in bullets[:]:
        bullet.update()
        bullet.draw(gameplay_surface)
        if bullet.hit:
            boss_hp -= 10
            boss_hp = max(boss_hp, 0)
            damage_flash = 15
            bullets.remove(bullet)

    # boss setup
    if boss_index < len(bosses) and boss_hp > 0 and not transitioning:
        boss = bosses[boss_index]
        if damage_flash > 0:
            img = boss.image.copy()
            img.fill((255,0,0,100), special_flags=pygame.BLEND_RGBA_MULT)
            gameplay_surface.blit(pygame.transform.scale(img, (64,64)), (WIDTH//2-32, 80))
            damage_flash -= 1
        else:
            boss.draw(gameplay_surface, WIDTH//2, 100, 0.5)

    # create HP box
    if boss_hp > 0:
        if hp_anim_current > boss_hp:
            hp_anim_current -= 1
        pygame.draw.rect(gameplay_surface, BLACK, (620,10,150,40))
        pygame.draw.rect(gameplay_surface, WHITE, (620,10,150,40),2)
        pygame.draw.rect(gameplay_surface, RED, (622,12,146,36))
        green_w = int(146 * (hp_anim_current / boss_hp_list[boss_index]))
        pygame.draw.rect(gameplay_surface, GREEN, (622,12,green_w,36))
        gameplay_surface.blit(font.render(f"{boss_hp}", True, WHITE), (670,20))

    # Draw cowboy 
    gameplay_surface.blit(
        cowboy_img,
        (cowboy_x - cowboy_width // 2, cowboy_y - cowboy_height // 2)
    )

    screen.blit(gameplay_surface, (0, gameplay_top))

    # Events
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN and not transitioning:
            if event.key == pygame.K_RETURN:
                if user_input.lower() == current_question["answer"].lower():
                    bullets.append(Bullet(cowboy_x, cowboy_y, 100))
                    feedback = "Hit!"
                else:
                    feedback = "Miss!"
                user_input = ""
                current_question = get_question()
            elif event.key == pygame.K_BACKSPACE:
                user_input = user_input[:-1]
            else:
                user_input += event.unicode

    # Boss death
    if boss_hp <= 0 and not transitioning:
        transitioning = True

    if transitioning:
        scroll_offset += scroll_speed
        if scroll_offset >= gameplay_height:
            scroll_offset = 0
            transitioning = False
            boss_index += 1
            if boss_index < len(bosses):
                boss_hp = boss_hp_list[boss_index]
                hp_anim_current = boss_hp
            else:
                running = False

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()