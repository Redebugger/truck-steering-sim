import pygame
import math
import sys

# ── Ackermann helpers ────────────────────────────────────────────────────────

def ackermann(inner_angle_deg, dims):
    """Return outer steer angle (deg) given inner steer angle (deg)."""
    o_inner = math.radians(inner_angle_deg)
    W_B = dims["W_B"]
    D   = dims["D"]
    if abs(o_inner) < 1e-9:
        return 0.0
    o_outer = math.atan(W_B / ((W_B / math.tan(o_inner)) + D))
    return math.degrees(o_outer)

# ── Truck dimensions (metres) ─────────────────────────────────────────────────

DIMS = {
    "D":    4.318,   # KPI-to-KPI distance
    "W_B":  5.842,   # wheelbase
    "T_F":  5.7912,  # front track
    "T_R":  5.08,    # rear track
    "D_S":  1.27,    # dual spacing (rear axle)
    "T_W":  0.889,   # tyre width
    "T_D":  3.1496,  # tyre diameter
}

# ── Display constants ─────────────────────────────────────────────────────────

WIDTH, HEIGHT = 960, 700
FPS           = 60
SCALE         = 55          # pixels per metre
ANGLE_STEP    = 0.5         # degrees per key-press
MAX_INNER     = 45.0

BG            = (245, 245, 242)
BODY_COLOR    = (80,  90, 100)
TYRE_COLOR    = (50,  50,  50)
AXLE_COLOR    = (120, 130, 140)
KPI_COLOR     = (200,  60,  60)
STEER_COLOR   = (220, 100,  40)
TEXT_COLOR    = (40,   40,  40)
GRID_COLOR    = (210, 210, 207)
DIM_COLOR     = (150, 150, 150)

def m2p(metres):
    return metres * SCALE

# ── Drawing helpers ───────────────────────────────────────────────────────────

def draw_tyre(surface, cx, cy, angle_deg, width_m, diam_m, color=TYRE_COLOR):
    """Draw a single tyre rectangle rotated about its centre."""
    w = m2p(width_m)
    h = m2p(diam_m)
    rect_surf = pygame.Surface((w, h), pygame.SRCALPHA)
    rect_surf.fill((*color, 255))
    # white sidewall stripe
    pygame.draw.rect(rect_surf, (200, 200, 200), (0, 0, w, 4))
    pygame.draw.rect(rect_surf, (200, 200, 200), (0, h - 4, w, 4))
    rotated = pygame.transform.rotate(rect_surf, -angle_deg)
    rx, ry = rotated.get_rect(center=(cx, cy)).topleft
    surface.blit(rotated, (rx, ry))

def draw_axle(surface, x1, y1, x2, y2):
    pygame.draw.line(surface, AXLE_COLOR, (int(x1), int(y1)), (int(x2), int(y2)), 4)

def draw_kpi(surface, x, y):
    pygame.draw.circle(surface, KPI_COLOR, (int(x), int(y)), 5)

def draw_dim_line(surface, p1, p2, label, font, offset=(0, -18)):
    """Draw a simple dimension annotation."""
    mx = (p1[0] + p2[0]) / 2 + offset[0]
    my = (p1[1] + p2[1]) / 2 + offset[1]
    pygame.draw.line(surface, DIM_COLOR, p1, p2, 1)
    # tick marks
    for px, py in (p1, p2):
        pygame.draw.line(surface, DIM_COLOR, (px, py - 5), (px, py + 5), 1)
    txt = font.render(label, True, DIM_COLOR)
    surface.blit(txt, txt.get_rect(center=(int(mx), int(my))))

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Ackermann Steering Visualiser")
    clock  = pygame.time.Clock()

    font_sm  = pygame.font.SysFont("monospace", 13)
    font_med = pygame.font.SysFont("monospace", 15, bold=True)
    font_lg  = pygame.font.SysFont("monospace", 20, bold=True)
    font_title = pygame.font.SysFont("monospace", 22, bold=True)

    inner_angle = 0.0          # degrees – positive = steer left

    # Truck geometry in metres, origin at rear-axle centre
    # We'll draw with Y increasing upward (flip for pygame later).
    # All positions computed in "truck space" then mapped to screen.

    def truck_to_screen(tx, ty, ox, oy):
        """truck-space (right=+x, up=+y) → screen pixels."""
        sx = ox + m2p(tx)
        sy = oy - m2p(ty)
        return sx, sy

    # Screen origin = rear axle centre
    ox = WIDTH  / 2
    oy = HEIGHT / 2 + m2p(DIMS["W_B"] / 2) - 30

    running = True
    while running:
        # ── Events ────────────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            inner_angle = min(inner_angle + ANGLE_STEP, MAX_INNER)
        if keys[pygame.K_RIGHT]:
            inner_angle = max(inner_angle - ANGLE_STEP, -MAX_INNER)

        outer_angle = ackermann(abs(inner_angle), DIMS)
        if inner_angle < 0:
            outer_angle = -outer_angle

        # Assign left/right steer angles
        # Positive inner_angle → steer LEFT → left wheel is inner
        if inner_angle >= 0:
            left_angle  =  inner_angle
            right_angle =  outer_angle
        else:
            left_angle  =  outer_angle
            right_angle =  inner_angle

        # ── Background ────────────────────────────────────────────────────────
        screen.fill(BG)

        # light grid
        for gx in range(0, WIDTH, 40):
            pygame.draw.line(screen, GRID_COLOR, (gx, 0), (gx, HEIGHT), 1)
        for gy in range(0, HEIGHT, 40):
            pygame.draw.line(screen, GRID_COLOR, (0, gy), (WIDTH, gy), 1)

        # ── Compute key positions ─────────────────────────────────────────────

        # Rear axle: y=0, x = ±T_R/2
        rear_left  = truck_to_screen(-DIMS["T_R"]/2,  0, ox, oy)
        rear_right = truck_to_screen( DIMS["T_R"]/2,  0, ox, oy)
        rear_mid   = truck_to_screen(0,                0, ox, oy)

        # Rear dual tyres: inner/outer separated by D_S
        # Positions relative to axle end
        rl_inner = truck_to_screen(-DIMS["T_R"]/2 + DIMS["D_S"]/2, 0, ox, oy)
        rl_outer = truck_to_screen(-DIMS["T_R"]/2 - DIMS["D_S"]/2, 0, ox, oy)
        rr_inner = truck_to_screen( DIMS["T_R"]/2 - DIMS["D_S"]/2, 0, ox, oy)
        rr_outer = truck_to_screen( DIMS["T_R"]/2 + DIMS["D_S"]/2, 0, ox, oy)

        # Front axle: y = W_B
        front_left  = truck_to_screen(-DIMS["T_F"]/2, DIMS["W_B"], ox, oy)
        front_right = truck_to_screen( DIMS["T_F"]/2, DIMS["W_B"], ox, oy)
        front_mid   = truck_to_screen(0,               DIMS["W_B"], ox, oy)

        # KPI positions (inner edge of front track)
        kpi_left  = truck_to_screen(-DIMS["D"]/2, DIMS["W_B"], ox, oy)
        kpi_right = truck_to_screen( DIMS["D"]/2, DIMS["W_B"], ox, oy)

        # ── Draw chassis outline ──────────────────────────────────────────────
        chassis_w = m2p(DIMS["T_F"]) * 0.55
        chassis_h = m2p(DIMS["W_B"]) * 0.85
        chassis_rect = pygame.Rect(
            front_mid[0] - chassis_w / 2,
            front_mid[1] - m2p(DIMS["W_B"]) * 0.05,
            chassis_w, chassis_h
        )
        chassis_surf = pygame.Surface((int(chassis_w), int(chassis_h)), pygame.SRCALPHA)
        chassis_surf.fill((160, 170, 175, 80))
        pygame.draw.rect(chassis_surf, (120, 130, 140, 160), chassis_surf.get_rect(), 2)
        screen.blit(chassis_surf, chassis_rect.topleft)

        # ── Draw axles ────────────────────────────────────────────────────────
        draw_axle(screen, *rear_left,  *rear_right)
        draw_axle(screen, *front_left, *front_right)

        # Kingpin to kingpin line (dashed style – alternate segments)
        kpi_dx = kpi_right[0] - kpi_left[0]
        segs = 18
        for i in range(0, segs, 2):
            x1 = kpi_left[0] + kpi_dx * i / segs
            x2 = kpi_left[0] + kpi_dx * (i + 1) / segs
            pygame.draw.line(screen, (180, 180, 180),
                             (int(x1), kpi_left[1]), (int(x2), kpi_right[1]), 1)

        # ── Draw rear tyres (dual) ─────────────────────────────────────────────
        for pos in (rl_inner, rl_outer, rr_inner, rr_outer):
            draw_tyre(screen, pos[0], pos[1], 0,
                      DIMS["T_W"], DIMS["T_D"])

        # ── Draw front tyres (steered) ─────────────────────────────────────────
        draw_tyre(screen, front_left[0],  front_left[1],  left_angle,
                  DIMS["T_W"], DIMS["T_D"], color=STEER_COLOR)
        draw_tyre(screen, front_right[0], front_right[1], right_angle,
                  DIMS["T_W"], DIMS["T_D"], color=STEER_COLOR)

        # ── Draw KPI dots ─────────────────────────────────────────────────────
        draw_kpi(screen, *kpi_left)
        draw_kpi(screen, *kpi_right)

        # KPI labels
        for pos, label in ((kpi_left, "KPI"), (kpi_right, "KPI")):
            t = font_sm.render(label, True, KPI_COLOR)
            screen.blit(t, (pos[0] - 18, pos[1] - 22))

        # ── Dimension annotations ─────────────────────────────────────────────
        # W_B
        draw_dim_line(screen,
            (int(rear_mid[0]) - 14, int(rear_mid[1])),
            (int(front_mid[0]) - 14, int(front_mid[1])),
            f"W_B={DIMS['W_B']}m", font_sm, offset=(-38, 0))

        # D (KPI to KPI)
        draw_dim_line(screen,
            (int(kpi_left[0]),  int(kpi_left[1])  + 28),
            (int(kpi_right[0]), int(kpi_right[1]) + 28),
            f"D={DIMS['D']}m", font_sm, offset=(0, 14))

        # T_F
        draw_dim_line(screen,
            (int(front_left[0]),  int(front_left[1])  - 28),
            (int(front_right[0]), int(front_right[1]) - 28),
            f"T_F={DIMS['T_F']}m", font_sm, offset=(0, -14))

        # T_R
        draw_dim_line(screen,
            (int(rear_left[0]),  int(rear_left[1])  + 28),
            (int(rear_right[0]), int(rear_right[1]) + 28),
            f"T_R={DIMS['T_R']}m", font_sm, offset=(0, 14))

        # ── HUD panel ─────────────────────────────────────────────────────────
        panel_x, panel_y = 16, 16
        panel_w, panel_h = 310, 195
        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surf.fill((255, 255, 255, 200))
        pygame.draw.rect(panel_surf, (180, 180, 175), panel_surf.get_rect(), 1)
        screen.blit(panel_surf, (panel_x, panel_y))

        title = font_title.render("Ackermann Steering", True, TEXT_COLOR)
        screen.blit(title, (panel_x + 10, panel_y + 10))

        lines = [
            ("← / →", "steer left / right"),
            ("",       ""),
            (f"Inner angle : {inner_angle:+.1f}°",  ""),
            (f"Outer angle : {(outer_angle if inner_angle >= 0 else -outer_angle):+.1f}°", ""),
            (f"Left  wheel : {left_angle:+.1f}°",   ""),
            (f"Right wheel : {right_angle:+.1f}°",  ""),
        ]
        for i, (main_txt, sub_txt) in enumerate(lines):
            color = STEER_COLOR if "angle" in main_txt.lower() else TEXT_COLOR
            t = font_med.render(main_txt, True, color)
            screen.blit(t, (panel_x + 10, panel_y + 42 + i * 22))
            if sub_txt:
                s = font_sm.render(sub_txt, True, (130, 130, 130))
                screen.blit(s, (panel_x + 190, panel_y + 44 + i * 22))

        # ── Direction indicator arc ───────────────────────────────────────────
        if abs(inner_angle) > 0.5:
            arc_color = STEER_COLOR
            arc_cx, arc_cy = WIDTH - 80, HEIGHT - 80
            arc_r = 50
            start_a = math.radians(90)
            end_a   = math.radians(90 - inner_angle * 2)
            pygame.draw.arc(screen, arc_color,
                            (arc_cx - arc_r, arc_cy - arc_r, arc_r*2, arc_r*2),
                            min(start_a, end_a), max(start_a, end_a), 4)
            label = font_med.render(f"{'LEFT' if inner_angle > 0 else 'RIGHT'}", True, arc_color)
            screen.blit(label, label.get_rect(center=(arc_cx, arc_cy + arc_r + 14)))

        # ── Title ─────────────────────────────────────────────────────────────
        top_label = font_title.render("Min. Viability Step 1 – Steering Sim", True, TEXT_COLOR)
        screen.blit(top_label, top_label.get_rect(midtop=(WIDTH // 2, 8)))

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
