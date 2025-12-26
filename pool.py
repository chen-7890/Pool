import pygame
import pymunk
import math
import random

# Configuration 
WIDTH, HEIGHT = 1300, 650
TABLE_WIDTH = 1200
FPS = 60
BALL_RADIUS = 15
L, R = 50, 1150                 
T, B = 50, 600 
FRICTION = 0.98
CX, CY = (L + R) // 2, (T + B) // 2
POCKETS = [
    (L, T), (CX, T), (R, T),   # Top rail
    (L, B), (CX, B), (R, B)    # Bottom rail
]
SIDEBAR_RECT = pygame.Rect(1220, 50, 40, 550)
RESET_RECT = pygame.Rect(910, 410, 80, 40)
PLAY_BUTTON_RECT = pygame.Rect(WIDTH//2 - 100, HEIGHT//2 - 40, 200, 80)
UI_OFFSET_X = 1170

# States 
STATE_MENU = 0
STATE_GAME = 1

# Ball Types 
# 0: Cue, 1: Solid, 2: Stripe, 3: Black
def create_pool_ball(space, pos, color, ball_type):
    body, shape = create_ball(space, pos, color)
    shape.ball_type = ball_type # Custom property for logic
    return body, shape

# Basic function for creating balls
def create_ball(space, pos, color=(255, 255, 255, 255)):
    mass = 1
    moment = pymunk.moment_for_circle(mass, 0, BALL_RADIUS)
    body = pymunk.Body(mass, moment)
    body.position = pos
    shape = pymunk.Circle(body, BALL_RADIUS)
    shape.elasticity = 0.8
    shape.friction = 0.5
    shape.color = color
    shape.filter = pymunk.ShapeFilter(categories=0b10)
    space.add(body, shape)
    return body, shape # Return both so we can track the cue shape

# Functions for saving and loading high score in and out text file
def save_high_score(score):
    try:
        with open("highscore.txt", "w") as f:       # 'w' mode overwrites the file with the new highest score
            f.write(str(score))
    except Exception as e:
        print(f"Error saving high score: {e}")

def load_high_score():
    try:
        with open("highscore.txt", "r") as f:
            return int(f.read())
    except:
        return 0 # Return 0 if the file doesn't exist yet

# Main function of the program
def main():
    pygame.init()
    pygame.mixer.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Arial", 18, bold=True)
    big_font = pygame.font.SysFont("Arial", 60, bold=True)
    
    # Game State Varibles  
    
    cue_ball = None
    current_state = STATE_MENU
    space = pymunk.Space()
    space.gravity = (0, 0)
    
    score = 0
    game_over = lost = game_won = False
    scratch_reason = ""
    golden_pocket_index = 0
    start_ticks = pygame.time.get_ticks()
    balls_stopped = True
    current_angle = 0.0
    power_level = 0.0
    aiming_locked = is_powering = False
    first_turn_active = True
    running = True
    fast_forward = False
    
    # Game Settings 
    settings = {
        "zones": True,
        "portals": True,
        "bumpers": True
    }
    
    # Checkbox UI Positions 
    menu_font = pygame.font.SysFont("Arial", 22, bold=True)
    checkboxes = {
        "zones": pygame.Rect(WIDTH//2 - 100, 390, 25, 25),
        "portals": pygame.Rect(WIDTH//2 - 100, 430, 25, 25),
        "bumpers": pygame.Rect(WIDTH//2 - 100, 470, 25, 25)
    }
    
    # This timer prevents a machine-gun sound effect when balls stay touching
    last_hit_time = 0
    final_time = 0
    
    # Hazards
    ice_zone = pygame.Rect(0, 0, 0, 0)
    mud_zone = pygame.Rect(0, 0, 0, 0)
    warp_portal_a = pymunk.Vec2d(-100, -100)
    warp_portal_b = pymunk.Vec2d(-100, -100)
    warp_cooldowns = {} # Prevents infinite teleport loops
    bumpers = []
    
    # Setup Walls
    static_body = space.static_body
    wall_thickness = 20 
    offset = wall_thickness / 2
    
    walls = [
        ((L, T - offset), (R, T - offset)), # Top
        ((R + offset, T), (R + offset, B)), # Right
        ((R, B + offset), (L, B + offset)), # Bottom
        ((L - offset, B), (L - offset, T))  # Left
    ]
    
    for start, end in walls:
        wall = pymunk.Segment(static_body, start, end, wall_thickness)
        wall.elasticity = 0.8
        wall.friction = 0.5
        wall.filter = pymunk.ShapeFilter(categories=0b01)
        space.add(wall)
    
    # Sound Function
    def load_sfx(name):
        for ext in [".wav", ".mp3"]:
            try:
                return pygame.mixer.Sound(name + ext)
            except:
                continue
        return None

    ball_sound = load_sfx("ball_hit")
    wall_sound = load_sfx("wall_hit")
    cue_sound = load_sfx("cueballhit") 

    # Reset Function
    def reset_table():
        nonlocal cue_ball
        # Clear existing balls
        to_remove = [s for s in space.shapes if s.filter.categories == 0b10]
        for shape in to_remove:
            space.remove(shape, shape.body)
        
        # Color Map 
        ball_colors = {
            1: (255, 215, 0),  2: (0, 0, 255),    3: (255, 0, 0), 
            4: (128, 0, 128),  5: (255, 165, 0),  6: (0, 128, 0), 
            7: (128, 0, 0),    8: (10, 10, 10),   # 8 is Black
            9: (255, 215, 0),  10: (0, 0, 255),   11: (255, 0, 0), 
            12: (128, 0, 128), 13: (255, 165, 0), 14: (0, 128, 0), 
            15: (128, 0, 0)
        }

        # Create Cue Ball
        new_cue_ball, _ = create_pool_ball(space, (300, CY), (255, 255, 255), 0)

        # Rack Balls
        start_x = 800
        ball_ids = [1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15]
        random.shuffle(ball_ids)
        
        # Insert the 8-ball ID at index 4 
        ball_ids.insert(4, 8)

        # Reset the counter to 0 for proper list indexing
        ball_count = 0 
        for col in range(5):
            for row in range(col + 1):
                pos_x = start_x + (col * (BALL_RADIUS * 2 - 1))
                pos_y = CY + (row * (BALL_RADIUS * 2 + 1)) - (col * BALL_RADIUS)
                
                # Use ball_count as the index directly (0 to 14)
                current_id = ball_ids[ball_count]
                
                # Assign logic type based on the ID
                if current_id == 8:
                    b_type = 3  # Black Ball Logic
                elif current_id <= 7:
                    b_type = 1  # Solids
                else:
                    b_type = 2  # Stripes
                
                color = ball_colors.get(current_id, (200, 200, 200))
                body, shape = create_pool_ball(space, (pos_x, pos_y), color, b_type)
                body.used_hazards = set() 
                
                # Move to the next index in ball_ids
                ball_count += 1
        return new_cue_ball

    # Spawn Bumpers
    def spawn_hazards():
        if not settings["bumpers"]:
            return
        # Clear old bumpers correctly
        for b_shape in bumpers:
            if b_shape.body in space.bodies:
                space.remove(b_shape.body, b_shape)
        bumpers.clear()
        
        for _ in range(2):
            valid_pos = False
            hx, hy = 0, 0
            attempts = 0
            while not valid_pos and attempts < 100:
                attempts += 1
                hx = random.randint(L + 60, R - 60)
                hy = random.randint(T + 60, B - 60)
                # Use a slightly larger radius for the query to prevent overlapping
                hit = space.point_query_nearest((hx, hy), 60, pymunk.ShapeFilter())
                if not hit:
                    valid_pos = True
            
            # Create a new body for each bumper
            b_body = pymunk.Body(body_type=pymunk.Body.STATIC)
            b_body.position = (hx, hy)
            b_shape = pymunk.Circle(b_body, 25)
            b_shape.elasticity = 1.2 
            b_shape.friction = 0.5
            # Add a unique filter so they don't catch ghost queries from balls
            b_shape.filter = pymunk.ShapeFilter(categories=0b100) 
            
            space.add(b_body, b_shape) 
            bumpers.append(b_shape)
                
    # Spawn Mud and Ice Zones
    def spawn_zones():
        if not settings["zones"]:
            return
        nonlocal ice_zone, mud_zone
        safe_L, safe_R = L + 100, R - 250
        safe_T, safe_B = T + 100, B - 200
        
        ice_zone = pygame.Rect(random.randint(safe_L, safe_R), random.randint(safe_T, safe_B), 200, 120)
        mud_zone = pygame.Rect(random.randint(safe_L, safe_R), random.randint(safe_T, safe_B), 200, 120)
        
        # Simple check to ensure they don't perfectly overlap
        if ice_zone.colliderect(mud_zone):
            mud_zone.x += 200 # Shift mud if it hits ice
        
    # Spawn Portals
    def spawn_portals():
        if not settings["portals"]:
            return
        nonlocal warp_portal_a, warp_portal_b
        
        def get_clear_pos():
            safe_L, safe_R = L + 80, R - 80
            safe_T, safe_B = T + 80, B - 80
            for _ in range(100):
                pos = pymunk.Vec2d(random.randint(safe_L, safe_R), random.randint(safe_T, safe_B))
                # Check distance from all balls, bumpers, and pockets
                balls_clear = all((pos - b.position).length > 120 for b in space.bodies if b.body_type == pymunk.Body.DYNAMIC)
                bumpers_clear = all((pos - b.body.position).length > 100 for b in bumpers)
                pockets_clear = all((pos - pymunk.Vec2d(*p)).length > 100 for p in POCKETS)
                
                if balls_clear and bumpers_clear and pockets_clear:
                    return pos
            return pymunk.Vec2d((L+R)//2, (T+B)//2)

        warp_portal_a = get_clear_pos()
        warp_portal_b = get_clear_pos()

    
    def draw_settings_menu(screen):
        for key, rect in checkboxes.items():
            # Draw the outer white box
            pygame.draw.rect(screen, (255, 255, 255), rect, 2)
            
            # If enabled, draw a green fill
            if settings[key]:
                pygame.draw.rect(screen, (0, 255, 0), rect.inflate(-8, -8))
                
            # Label the checkbox
            label = menu_font.render(f"Enable {key.capitalize()}", True, (255, 255, 255))
            screen.blit(label, (rect.right + 15, rect.y))
            
    cue_ball = reset_table()
    
    while running:
        # Background and Felt
        screen.fill((30, 30, 30)) 
        pygame.draw.rect(screen, (50, 30, 10), (L-10, T-10, 820, 420))
        pygame.draw.rect(screen, (20, 100, 20), (L, T, 800, 400))
        
        # Draw Pockets
        for p in POCKETS:
            pygame.draw.circle(screen, (0, 0, 0), p, 25)

        mouse_pos = pygame.mouse.get_pos()
        # Check if all balls have stopped 
        currently_stopped = all(b.velocity.length < 5 for b in space.bodies if b.body_type == pymunk.Body.DYNAMIC)
        
        # If balls were moving but have just stopped, rotate the hazard position
        if currently_stopped and not balls_stopped:
            high_score = load_high_score()
            if score > high_score:
                save_high_score(score)
            golden_pocket_index = random.randint(0, len(POCKETS) - 1)
            
            # Only spawn if the user actually wants them enabled
            if settings["bumpers"]: spawn_hazards()
            if settings["portals"]: spawn_portals()
            if settings["zones"]: spawn_zones()
            
            if first_turn_active:
                first_turn_active = False
            else:
                warp_cooldowns = {}
            
        # Update the persistent state for the next frame
        balls_stopped = currently_stopped

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            # Fast Forward upon pressing 'k'    
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_k:
                    fast_forward = True
            if event.type == pygame.KEYUP:
                if event.key == pygame.K_k:
                    fast_forward = False
            
            # Logic for Menu
            if current_state == STATE_MENU:
                if event.type == pygame.MOUSEBUTTONDOWN:
                    for key, rect in checkboxes.items():
                        if rect.collidepoint(mouse_pos):
                            settings[key] = not settings[key] # Flip True to False or vice versa
                            
                    # When PLAY is pressed, initialize only the selected hazards
                    if PLAY_BUTTON_RECT.collidepoint(mouse_pos):
                        current_state = STATE_GAME
                        # Trigger spawning ONLY if the setting is True
                        if settings["bumpers"]: spawn_hazards()
                        if settings["portals"]: spawn_portals()
                        if settings["zones"]: spawn_zones()
            
            # Logic for Game
            elif current_state == STATE_GAME:
                # Reset using 'r' key logic
                if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                    space = pymunk.Space()
                    space.gravity = (0, 0)
                    
                    # Reset walls
                    static_body = space.static_body
                    for start, end in walls:
                        wall = pymunk.Segment(static_body, start, end, wall_thickness)
                        wall.elasticity = 0.8
                        wall.friction = 0.5
                        wall.filter = pymunk.ShapeFilter(categories=0b01)
                        space.add(wall)
                    
                    # Reset all game state variables
                    score = 0
                    game_over = lost = game_won = False
                    scratch_reason = ""
                    start_ticks = pygame.time.get_ticks()
                    aiming_locked = is_powering = False
                    power_level = 0.0
                    balls_stopped = True
                    golden_pocket_index = 0
                    bumpers.clear()
                    warp_portal_a = pymunk.Vec2d(-100, -100) 
                    warp_portal_b = pymunk.Vec2d(-100, -100)
                    mud_zone = pygame.Rect(0, 0, 0, 0)
                    ice_zone = pygame.Rect(0, 0, 0, 0)
                    
                    spawn_zones()
                    cue_ball = reset_table()
                    
                    current_state = STATE_MENU
                
                # Switch between Aiming and Powering    
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if balls_stopped:
                        # Power Bar logic
                        if SIDEBAR_RECT.collidepoint(mouse_pos):
                            if aiming_locked: 
                                is_powering = True
                        # Table logic (Locking Aim)
                        elif mouse_pos[0] < TABLE_WIDTH:
                            aiming_locked = not aiming_locked
                # Powering Logic
                if event.type == pygame.MOUSEBUTTONUP and is_powering:
                    # Power only if power level is a certain level
                    if power_level > 0.05:
                        impulse_vec = pymunk.Vec2d(math.cos(current_angle), math.sin(current_angle))
                        cue_ball.apply_impulse_at_world_point(impulse_vec * (power_level * 5000), cue_ball.position)
                        aiming_locked = False 
                        if cue_sound:
                            # Scale volume based on how much power was used
                            cue_sound.set_volume(max(0.3, power_level))
                            cue_sound.play()
            
                    is_powering, power_level = False, 0.0
                    
        # Drawing Menu
        if current_state == STATE_MENU:
            
            screen.fill((20, 40, 20))
            # Title
            title = big_font.render("CHAOS POOL", True, (255, 215, 0))
            screen.blit(title, (WIDTH//2 - title.get_width()//2, HEIGHT//2 - 150))
            # Button
            btn_col = (60, 180, 60) if PLAY_BUTTON_RECT.collidepoint(mouse_pos) else (40, 120, 40)
            pygame.draw.rect(screen, btn_col, PLAY_BUTTON_RECT, border_radius=12)
            pygame.draw.rect(screen, (255, 255, 255), PLAY_BUTTON_RECT, 3, border_radius=12)
            btn_txt = font.render("PLAY", True, (255, 255, 255))
            screen.blit(btn_txt, (PLAY_BUTTON_RECT.centerx - btn_txt.get_width()//2, PLAY_BUTTON_RECT.centery - btn_txt.get_height()//2))
            
            current_high = load_high_score()
            high_txt = font.render(f"HIGH SCORE: {current_high}", True, (255, 215, 0)) # Gold color
            screen.blit(high_txt, (20, 50)) # Placed just below your current score
            draw_settings_menu(screen)
        
        # Game Calculations    
        elif current_state == STATE_GAME:
            # Aim/Power Calculations 
            if balls_stopped:
                if is_powering:
                    clamped_y = max(SIDEBAR_RECT.top, min(mouse_pos[1], SIDEBAR_RECT.bottom))
                    power_level = (clamped_y - SIDEBAR_RECT.top) / SIDEBAR_RECT.height
            if balls_stopped and cue_ball is not None:
                if not aiming_locked:
                    dx = mouse_pos[0] - cue_ball.position.x
                    dy = mouse_pos[1] - cue_ball.position.y
                    current_angle = math.atan2(dy, dx)
            
            # Physics Execution 
            iterations = 50 if fast_forward else 5
            dt = (1/FPS) / 5
            for _ in range(iterations):
                space.step(dt)
                
                # Portal Logic
                portals = [warp_portal_a, warp_portal_b]
                for body in [b for b in space.bodies if b.body_type == pymunk.Body.DYNAMIC]:
                    for i, portal in enumerate(portals):
                        dist = (portal - body.position).length
                        
                        # If ball hits portal and isn't on cooldown
                        if dist < 25 and body not in warp_cooldowns:
                            destination = portals[1 - i]
                            
                            # Calculate Ejection Offset
                            # If the ball is nearly still, we'll just push it right/left
                            if body.velocity.length < 10:
                                eject_dir = pymunk.Vec2d(1, 0) 
                            else:
                                eject_dir = body.velocity.normalized()
                            
                            # Move the ball to the destination plus a 30-pixel push forward
                            body.position = destination + (eject_dir * 30)
                            warp_cooldowns[body] = 40 # Prevent instant re-warping
                
                # Decay cooldowns
                for body in list(warp_cooldowns.keys()):
                    warp_cooldowns[body] -= 1
                    if warp_cooldowns[body] <= 0:
                        del warp_cooldowns[body]
                
                # Apply Floor Hazards 
                for body in [b for b in space.bodies if b.body_type == pymunk.Body.DYNAMIC]:
                    pos = body.position
                    
                    # Mud Zone: Heavy resistance
                    if mud_zone.collidepoint(pos.x, pos.y):
                        # Percent-based slowdown (Current logic)
                        body.velocity *= 0.98  
                        
                    # Ice Zone: Low friction
                    elif ice_zone.collidepoint(pos.x, pos.y):
                        if body.velocity.length > 10: 
                            body.velocity *= 1.01 
                
                # Sound Detection
                current_time = pygame.time.get_ticks()
                dynamic_bodies = [b for b in space.bodies if b.body_type == pymunk.Body.DYNAMIC]

                for i, b1 in enumerate(dynamic_bodies):
                    # Check for Wall Hits (checking if ball edge crosses table boundaries)
                    if b1.position.x < L+15 or b1.position.x > R-15 or b1.position.y < T+15 or b1.position.y > B-15:
                        # Only play if moving fast enough and hasn't played in the last 100ms
                        if b1.velocity.length > 200 and current_time - last_hit_time > 100:
                            if wall_sound: 
                                wall_sound.set_volume(0.5)
                                wall_sound.play()
                            last_hit_time = current_time

                    # Check for Ball-to-Ball Hits
                    for b2 in dynamic_bodies[i+1:]:
                        # Distance formula: sqrt((x2-x1)^2 + (y2-y1)^2)
                        dist = (b1.position - b2.position).length
                        
                        # If distance is less than two radii, they are colliding
                        if dist < (BALL_RADIUS * 2):
                            rel_vel = (b1.velocity - b2.velocity).length
                            
                            # Threshold to ensure it's a hit, not just rolling against each other
                            if rel_vel > 150 and current_time - last_hit_time > 100:
                                if ball_sound:
                                    # Dynamically set volume based on impact speed
                                    ball_sound.set_volume(min(rel_vel/1500, 1.0))
                                    ball_sound.play()
                                last_hit_time = current_time
                
                # Pocket Suction Effect 
                for body in [b for b in space.bodies if b.body_type == pymunk.Body.DYNAMIC]:
                    for p_pos in POCKETS:
                        p_vec = pymunk.Vec2d(*p_pos)
                        dist = (p_vec - body.position).length
                        if dist < 40: # Start pulling when the ball is nearby
                            # Apply a small force toward the center of the pocket
                            force_dir = (p_vec - body.position).normalized()
                            body.apply_force_at_world_point(force_dir * 500, body.position)            
                
            # Removing balls once they hit the pockets
            balls_to_remove = []
            cue_potted = False
            black_potted = False
            for shape in space.shapes:
                if shape.filter.categories == 0b10:
                    for p_pos in POCKETS:
                        if (pymunk.Vec2d(*p_pos) - shape.body.position).length < 40:
                            balls_to_remove.append(shape)

            # Scoring/Flagging Balls entering Pockets
            for shape in balls_to_remove:
                # Identify which pocket it entered
                p_idx = -1
                for i, p_pos in enumerate(POCKETS):
                    if (pymunk.Vec2d(*p_pos) - shape.body.position).length < 50:
                        p_idx = i
                        break
                
                b_type = getattr(shape, 'ball_type', -1)
            
                if b_type == 0:
                    # Cue Ball - Scratch Logic
                    points = -50
                    cue_potted = True
                    shape.body.position, shape.body.velocity = (300, CY), (0, 0)
                if b_type == 1 or b_type == 2:
                    # Object Ball Scoring
                    points = 100 # Initialize points here
                    
                    if p_idx == golden_pocket_index:
                        points *= 2 # Double points for golden pocket
                    
                if b_type == 3:
                    black_potted = True
                    points = 500
                    
                score += points
                # Remove object balls from play
                space.remove(shape, shape.body)

            # Evaluate Win/Loss conditions
            remaining_standard = [s for s in space.shapes if getattr(s, 'ball_type', -1) in [1, 2]]

            if black_potted:
                if cue_potted:
                    game_over = lost = True
                    scratch_reason = "SCRATCH ON 8-BALL!"
                elif len(remaining_standard) > 0:
                    game_over = lost = True
                    scratch_reason = "8-BALL POTTED TOO EARLY!"
                else:
                    game_over = True
                    lost = False
                    game_won = True

            elif cue_potted:
                # Normal scratch logic
                if not remaining_standard and not any(getattr(s, 'ball_type', -1) == 3 for s in space.shapes):
                    game_over = lost = True
                    scratch_reason = "SCRATCH ON FINAL TARGET!"

            # Velocity Clamping & Friction 
            for body in space.bodies:
                if body.body_type == pymunk.Body.DYNAMIC:
                    if body.velocity.length > 3000:
                        body.velocity = body.velocity.normalized() * 3000
                    body.velocity *= math.pow(FRICTION, 1/iterations)
            
            for body in [b for b in space.bodies if b.body_type == pymunk.Body.DYNAMIC]:
                # Apply standard friction
                body.velocity *= math.pow(FRICTION, 1/5)
                body.angular_velocity *= 0.99  # Also slow down the rotation
                
                # Hard Stop Threshold
                # If the ball is moving slower than 13 pixels per second, kill its momentum
                if body.velocity.length < 13: 
                    body.velocity = (0, 0)
                    body.angular_velocity = 0

            # Drawing Game 
            
            # Table & Physics Objects 
            screen.fill((30, 30, 30)) 
            pygame.draw.rect(screen, (50, 30, 10), (L-20, T-20, (R-L)+40, (B-T)+40))    # Draw Table Frame 
            pygame.draw.rect(screen, (20, 100, 20), (L, T, R-L, B-T))                   # Draw Table Body
            
            # Draw Golden Pockets
            for i, p in enumerate(POCKETS):
                if i == golden_pocket_index:
                    # Golden Glow
                    pygame.draw.circle(screen, (255, 215, 0), p, 35)
                    pygame.draw.circle(screen, (0, 0, 0), p, 28)
                else:
                    pygame.draw.circle(screen, (0, 0, 0), p, 25)
            
            # Draw bumpers 
            pulse = math.sin(pygame.time.get_ticks() * 0.01) * 3
            for b in bumpers:
                pos = b.body.position + b.offset
                # Draw outer glow
                pygame.draw.circle(screen, (255, 0, 255), (int(pos.x), int(pos.y)), int(20 + pulse), 2)
                # Draw main body
                pygame.draw.circle(screen, (200, 0, 255), (int(pos.x), int(pos.y)), 20)

            # Draw Warp Portals 
            warp_time = pygame.time.get_ticks() * 0.005
            for i, portal in enumerate([warp_portal_a, warp_portal_b]):
                # Rotating outer ring
                color = (0, 150, 255) if i == 0 else (0, 255, 200) # Blue and Teal
                pygame.draw.circle(screen, color, (int(portal.x), int(portal.y)), 25, 3)
                
                # Swirling inner lines
                for j in range(3):
                    angle = warp_time + (j * 2.09) # 120 degrees apart
                    end_x = portal.x + math.cos(angle) * 20
                    end_y = portal.y + math.sin(angle) * 20
                    pygame.draw.line(screen, color, (portal.x, portal.y), (end_x, end_y), 2)
            
            # Draw Floor Hazards 
            if settings["zones"]:
                # Ice (Cyan/Translucent White)
                ice_surface = pygame.Surface((ice_zone.width, ice_zone.height), pygame.SRCALPHA)
                ice_surface.fill((173, 216, 230, 120)) # Light blue with alpha
                screen.blit(ice_surface, (ice_zone.x, ice_zone.y))
                pygame.draw.rect(screen, (255, 255, 255), ice_zone, 2) # Border
                
                # Mud (Brown)
                mud_surface = pygame.Surface((mud_zone.width, mud_zone.height), pygame.SRCALPHA)
                mud_surface.fill((101, 67, 33, 180)) # Dark brown with alpha
                screen.blit(mud_surface, (mud_zone.x, mud_zone.y))
                pygame.draw.rect(screen, (60, 40, 20), mud_zone, 2) # Border
                
            # Draw Balls
            for shape in space.shapes:
                if shape.filter.categories == 0b10: # All pool balls
                    pos = shape.body.position
                    pygame.draw.circle(screen, shape.color, (int(pos.x), int(pos.y)), BALL_RADIUS)
                    
                    # If the ball is a stripe (Type 2), add the white center
                    if hasattr(shape, 'ball_type') and shape.ball_type == 2:
                        pygame.draw.circle(screen, (255, 255, 255), (int(pos.x), int(pos.y)), BALL_RADIUS // 2 + 2)
                        pygame.draw.circle(screen, shape.color, (int(pos.x), int(pos.y)), BALL_RADIUS // 3)
                    
                    # Visual logic for Black Ball (Type 3)
                    if hasattr(shape, 'ball_type') and shape.ball_type == 3:
                        pygame.draw.circle(screen, (255, 255, 255), (int(pos.x), int(pos.y)), 6)
                        pygame.draw.circle(screen, (0, 0, 0), (int(pos.x), int(pos.y)), 3)

                    # Shine highlight
                    pygame.draw.circle(screen, (255, 255, 255), (int(pos.x-4), int(pos.y-4)), 3)

            # --- Aiming & Cue Stick (Frozen during Power Stage) ---
            if balls_stopped and not (game_won or game_over):
                direction = pymunk.Vec2d(math.cos(current_angle), math.sin(current_angle))
                ray_start = cue_ball.position + (direction * (BALL_RADIUS + 0.1))
                query = space.segment_query_first(ray_start, ray_start + (direction * 2000), 0, pymunk.ShapeFilter())
                
                if query:
                    hit_center = query.point - (direction * BALL_RADIUS)
                    line_color = (0, 255, 255) if aiming_locked else (255, 255, 255)
                    
                    # Guide Line & Ghost Ball
                    pygame.draw.line(screen, line_color, cue_ball.position, hit_center, 1)
                    pygame.draw.circle(screen, line_color, (int(hit_center.x), int(hit_center.y)), BALL_RADIUS, 1)
                    
                    # Target Trajectory (Yellow)
                    if query.shape.body.body_type == pymunk.Body.DYNAMIC:
                        target_pos = query.shape.body.position
                        impact_dir = (target_pos - hit_center).normalized()
                        pygame.draw.line(screen, (255, 223, 0), target_pos, target_pos + (impact_dir * 80), 2)

                # CUE STICK (Drawn LAST to be on top of rails)
                stick_offset = 20 + (power_level * 100)
                stick_start = cue_ball.position - (direction * stick_offset)
                stick_end = stick_start - (direction * 400)
                pygame.draw.line(screen, (139, 69, 19), stick_start, stick_end, 7) # Wood
                pygame.draw.line(screen, (240, 240, 240), stick_start, stick_start + (direction * 12), 6) # Tip

            # Sidebar UI (Power Bar & Stats) 
            pygame.draw.rect(screen, (50, 50, 50), SIDEBAR_RECT) # Background
            if power_level > 0:
                h = SIDEBAR_RECT.height * power_level
                third = SIDEBAR_RECT.height / 3
                # Segmented Power Bar Drawing
                pygame.draw.rect(screen, (0, 255, 0), (SIDEBAR_RECT.x, SIDEBAR_RECT.top, SIDEBAR_RECT.width, min(h, third)))
                if h > third:
                    pygame.draw.rect(screen, (255, 255, 0), (SIDEBAR_RECT.x, SIDEBAR_RECT.top + third, SIDEBAR_RECT.width, min(h - third, third)))
                if h > third * 2:
                    pygame.draw.rect(screen, (255, 0, 0), (SIDEBAR_RECT.x, SIDEBAR_RECT.top + third * 2, SIDEBAR_RECT.width, h - third * 2))
            label_x = SIDEBAR_RECT.x - 20 # Adjust this offset to your liking
            
            # AIM Text (Top)
            aim_text = font.render(f"AIM: {'LOCKED' if aiming_locked else 'FREE'}", True, (255, 255, 255))
            screen.blit(aim_text, (label_x, SIDEBAR_RECT.top - 30))
            
            # PWR Text (Bottom)
            pwr_text = font.render(f"PWR: {int(power_level*100)}%", True, (255, 255, 255))
            screen.blit(pwr_text, (label_x, SIDEBAR_RECT.bottom + 10))
            
            # Static UI Labels
            screen.blit(font.render(f"SCORE: {score}", True, (255, 255, 255)), (L, 15))
            
            # Timer calculation for display
            seconds_elapsed = final_time if game_won else (pygame.time.get_ticks() - start_ticks) // 1000
            time_str = f"TIME: {seconds_elapsed // 60:02}:{seconds_elapsed % 60:02}"
            screen.blit(font.render(time_str, True, (255, 255, 255)), (L, 35))

            # Overlays (Win/Loss) 
            if game_over:
                overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 180))
                screen.blit(overlay, (0, 0))
                
                msg_text = "GAME OVER - YOU LOST!" if lost else "YOU WIN! TABLE CLEARED"
                msg_color = (255, 50, 50) if lost else (50, 255, 50)
                
                big_font = pygame.font.SysFont("Arial", 60, bold=True)
                txt = big_font.render(msg_text, True, msg_color)
                screen.blit(txt, (WIDTH//2 - txt.get_width()//2, HEIGHT//2 - 80))
                
                # Show the specific reason if it exists
                if scratch_reason:
                    reason_txt = font.render(scratch_reason, True, (255, 255, 255))
                    screen.blit(reason_txt, (WIDTH//2 - reason_txt.get_width()//2, HEIGHT//2 - 10))
                
                retry_txt = font.render("Press 'R' to Reset", True, (200, 200, 200))
                screen.blit(retry_txt, (WIDTH//2 - retry_txt.get_width()//2, HEIGHT//2 + 40))

        pygame.display.flip()
        clock.tick(FPS)
    pygame.quit()

if __name__ == "__main__":
    main()