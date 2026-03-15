"""
ackermann_car.py  –  v3
========================
Top-down 2D car simulation with proper Ackermann steering geometry.

KEY DESIGN DECISION  (fixes all dot/trajectory alignment issues)
-----------------------------------------------------------------
  self.x / self.y  IS the rear-axle centre — not the body centre.

  This means:
    • The yellow indicator dot is drawn at exactly (self.x, self.y) — zero offset.
    • The trajectory arc starts from exactly (self.x, self.y).
    • The body centre is at  rear_axle + forward * WHEELBASE/2  ... but we draw
      the body centred between the two axles, so:
        body_centre = rear_axle + forward * (WHEELBASE / 2)
    • The front axle is at:
        front_axle  = rear_axle + forward * WHEELBASE

Coordinate convention
---------------------
  heading   = degrees CLOCKWISE from screen-UP  (+Y is DOWN on screen)
  forward   = ( sin(h), -cos(h) )   in screen space
  right     = ( cos(h),  sin(h) )   in screen space

Controls
--------
  LEFT / RIGHT arrow  – each KEYDOWN steps steer by STEER_STEP degrees
  ESC / window close  – quit

The car drives forward at constant speed automatically.
"""

import math
import pygame

# ─────────────────────────────────────────────────────────────────────────────
# ADJUSTABLE CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

WINDOW_WIDTH        = 1920          # px
WINDOW_HEIGHT       = 1080          # px
FPS                 = 60

# --- Car dimensions (pixels) -------------------------------------------------
BODY_LENGTH         = 100           # bumper-to-bumper (visual only; slightly shorter than before)
BODY_WIDTH          = 56            # side-to-side width
WHEELBASE           = 76            # front-to-rear axle distance (physics + geometry)
TRACK_WIDTH         = 56            # lateral wheel-centre spacing (= BODY_WIDTH → corners)

# --- Wheel dimensions --------------------------------------------------------
WHEEL_LENGTH        = 28            # wheel rect long axis  (along heading)
WHEEL_WIDTH         = 10            # wheel rect short axis (lateral)

# --- Dynamics ----------------------------------------------------------------
MAX_STEERING_ANGLE  = 35.0          # degrees – max average front-wheel steer
STEER_STEP          = 5.0           # degrees added per key press
SPEED               = 120.0         # pixels / second

# --- Visual overhang (how far body extends past each axle) -------------------
# The axles are WHEELBASE apart; the body is BODY_LENGTH long.
# We centre the body between the axles, so each end overhangs by:
BODY_OVERHANG       = (BODY_LENGTH - WHEELBASE) / 2   # computed, not a tunable

# --- Colours -----------------------------------------------------------------
COLOR_BODY_OUTLINE  = (220,  60,  60)   # car body outline (transparent fill)
COLOR_REAR_DOT      = (255, 220,   0)   # rear-axle indicator dot (yellow)
COLOR_WHEEL         = ( 30,  30,  30)   # wheel fill
COLOR_WHEEL_OUTLINE = (160, 160, 160)   # wheel outline
COLOR_ARROW         = (255, 255, 255)   # direction arrow
COLOR_TRAJ          = (  0, 220, 255)   # trajectory circle/arc (cyan)
COLOR_BG            = ( 10,  10,  10)   # background


# ─────────────────────────────────────────────────────────────────────────────
# ACKERMANN GEOMETRY
# ─────────────────────────────────────────────────────────────────────────────
#
# Bicycle-model:  R = WHEELBASE / tan(δ)
#   R  = turning radius of the REAR AXLE CENTRE  (signed; + → right turn)
#   δ  = average front-wheel steering angle       (+ → right)
#
# Full Ackermann — both front wheels steer to their own angle so their
# perpendiculars intersect the same ICR on the rear-axle line:
#
#   δ_inner = atan( L / (|R| − T/2) )     inner wheel (turns more)
#   δ_outer = atan( L / (|R| + T/2) )     outer wheel (turns less)
#
# Right turn (+δ): right wheel is inner, left is outer.

def ackermann_angles(steer_deg: float) -> tuple[float, float]:
    """Return (front_left_deg, front_right_deg).  Positive steer → right turn."""
    if abs(steer_deg) < 0.01:
        return 0.0, 0.0

    delta = math.radians(steer_deg)
    L, T  = WHEELBASE, TRACK_WIDTH
    R_abs = abs(L / math.tan(delta))
    sign  = math.copysign(1.0, delta)

    d_inner = math.degrees(math.atan(L / max(R_abs - T / 2, 0.1)))
    d_outer = math.degrees(math.atan(L / (R_abs + T / 2)))

    left_deg  = sign * d_outer   # left  = outer on right turn
    right_deg = sign * d_inner   # right = inner on right turn
    return left_deg, right_deg


# ─────────────────────────────────────────────────────────────────────────────
# DRAWING HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def rect_corners(cx, cy, length, width, heading_deg):
    """
    Four corners of a rectangle centred at (cx, cy).
    'length' runs along heading (forward/back); 'width' runs perpendicular.
    """
    h  = math.radians(heading_deg)
    fx, fy = math.sin(h), -math.cos(h)
    rx, ry = math.cos(h),  math.sin(h)
    hl, hw = length / 2, width / 2
    return [
        (cx + fx*hl + rx*hw,  cy + fy*hl + ry*hw),  # front-right
        (cx + fx*hl - rx*hw,  cy + fy*hl - ry*hw),  # front-left
        (cx - fx*hl - rx*hw,  cy - fy*hl - ry*hw),  # rear-left
        (cx - fx*hl + rx*hw,  cy - fy*hl + ry*hw),  # rear-right
    ]

def draw_outline_rect(surface, colour, cx, cy, length, width, heading_deg, t=2):
    pygame.draw.polygon(surface, colour,
                        rect_corners(cx, cy, length, width, heading_deg), t)

def draw_filled_rect(surface, fill, outline, cx, cy, length, width, heading_deg):
    pts = rect_corners(cx, cy, length, width, heading_deg)
    pygame.draw.polygon(surface, fill,    pts)
    pygame.draw.polygon(surface, outline, pts, 1)


# ─────────────────────────────────────────────────────────────────────────────
# TRAJECTORY  (full circle or straight line)
# ─────────────────────────────────────────────────────────────────────────────
#
# Origin: rear-axle centre  (ra_x, ra_y)  — passed in directly.
#
# steer = 0  →  straight line ahead from rear axle.
#
# steer ≠ 0  →  full circle:
#   R   = WHEELBASE / tan(steer)      signed; + → ICR to the right
#   ICR = rear_axle + right * R
#   radius = |R|
#
#   We draw a complete circle centred at ICR with radius |R|.
#   pygame.draw.circle handles all edge cases neatly for a full circle.
#   We use an SRCALPHA surface so the circle is semi-transparent.

def draw_trajectory(surface, ra_x: float, ra_y: float,
                    heading_deg: float, steer_deg: float):
    """
    ra_x, ra_y  = rear-axle centre (world coords).
    heading_deg = car heading (CW from screen-up).
    steer_deg   = average front-wheel steer (+ = right).
    """
    h  = math.radians(heading_deg)
    fx, fy =  math.sin(h), -math.cos(h)   # forward
    rx, ry =  math.cos(h),  math.sin(h)   # right

    traj = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
    col  = (*COLOR_TRAJ, 160)

    if abs(steer_deg) < 0.5:
        # Straight line forward from rear axle
        dist = max(WINDOW_WIDTH, WINDOW_HEIGHT) * 2
        pygame.draw.line(traj, col,
                         (int(ra_x), int(ra_y)),
                         (int(ra_x + fx * dist), int(ra_y + fy * dist)), 3)
    else:
        delta  = math.radians(steer_deg)
        R      = WHEELBASE / math.tan(delta)    # signed
        radius = abs(R)

        if radius > max(WINDOW_WIDTH, WINDOW_HEIGHT) * 3:
            # Radius so large it looks straight
            dist = max(WINDOW_WIDTH, WINDOW_HEIGHT) * 2
            pygame.draw.line(traj, col,
                             (int(ra_x), int(ra_y)),
                             (int(ra_x + fx * dist), int(ra_y + fy * dist)), 3)
        else:
            # ICR = rear axle + right * R  (R is signed, so this always correct)
            icr_x = ra_x + rx * R
            icr_y = ra_y + ry * R

            # Draw FULL CIRCLE — pygame.draw.circle, 3 px thick, semi-transparent
            r_int = int(radius)
            if r_int > 2:
                pygame.draw.circle(traj, col,
                                   (int(icr_x), int(icr_y)),
                                   r_int, 3)

    surface.blit(traj, (0, 0))


# ─────────────────────────────────────────────────────────────────────────────
# CAR CLASS
# ─────────────────────────────────────────────────────────────────────────────

class Car:
    """
    self.x, self.y  = REAR-AXLE CENTRE position in screen space.
    self.heading    = CW degrees from screen-up.
    self.steer      = average front-wheel steer angle; + = right turn.
    """

    def __init__(self, x: float, y: float, heading_deg: float = 0.0):
        self.x       = float(x)
        self.y       = float(y)
        self.heading = float(heading_deg)
        self.steer   = 0.0

    # ── Input ────────────────────────────────────────────────────────────────

    def apply_steer_step(self, direction: int):
        """direction: +1 = right, -1 = left."""
        self.steer = max(-MAX_STEERING_ANGLE,
                         min(MAX_STEERING_ANGLE,
                             self.steer + direction * STEER_STEP))

    # ── Physics ──────────────────────────────────────────────────────────────

    def update(self, dt: float):
        """
        Kinematic bicycle model (rear-axle reference point):
            heading_rate = SPEED * tan(steer) / WHEELBASE    [rad/s, + = CW]
        Position update integrates the rear-axle velocity.
        """
        if abs(self.steer) > 0.01:
            delta    = math.radians(self.steer)
            yaw_rate = SPEED * math.tan(delta) / WHEELBASE   # rad/s
            self.heading = (self.heading + math.degrees(yaw_rate) * dt) % 360.0

        h = math.radians(self.heading)
        # Rear axle moves in the heading direction
        self.x = (self.x + math.sin(h) * SPEED * dt) % WINDOW_WIDTH
        self.y = (self.y - math.cos(h) * SPEED * dt) % WINDOW_HEIGHT

    # ── Draw ─────────────────────────────────────────────────────────────────

    def draw(self, surface):
        h  = self.heading
        hr = math.radians(h)
        fx, fy =  math.sin(hr), -math.cos(hr)   # forward unit vector
        rx, ry =  math.cos(hr),  math.sin(hr)   # right   unit vector

        # ── 1. Trajectory (full circle or straight line) ──────────────────────
        #       Originates exactly at rear axle = (self.x, self.y)
        draw_trajectory(surface, self.x, self.y, h, self.steer)

        # ── 2. Rear-axle dot ──────────────────────────────────────────────────
        #       Drawn at exactly self.x, self.y — no offset needed.
        pygame.draw.circle(surface, COLOR_REAR_DOT,
                           (int(self.x), int(self.y)), 6)
        pygame.draw.circle(surface, (0, 0, 0),
                           (int(self.x), int(self.y)), 6, 1)

        # ── 3. Derived positions ──────────────────────────────────────────────
        #
        # Front axle:   rear + forward * WHEELBASE
        # Body centre:  rear + forward * WHEELBASE/2  (midpoint of the two axles)
        # Body corners: body_centre ± forward*(BODY_LENGTH/2) ± right*(BODY_WIDTH/2)
        #
        # Because the body overhangs the axles equally (BODY_OVERHANG on each end),
        # the wheel centres (= axle ± right*(TRACK_WIDTH/2)) lie INSIDE the body
        # corners longitudinally.  We place the wheel centres on the axle lines and
        # the body corners just outside them — visually correct.

        front_ax_x = self.x + fx * WHEELBASE
        front_ax_y = self.y + fy * WHEELBASE

        body_cx = self.x + fx * (WHEELBASE / 2)
        body_cy = self.y + fy * (WHEELBASE / 2)

        # ── 4. Car body (outline only) ────────────────────────────────────────
        draw_outline_rect(surface, COLOR_BODY_OUTLINE,
                          body_cx, body_cy, BODY_LENGTH, BODY_WIDTH, h, t=2)

        # ── 5. Direction arrow (inside body, pointing forward) ────────────────
        arrow_tip_x  = body_cx + fx * BODY_LENGTH * 0.30
        arrow_tip_y  = body_cy + fy * BODY_LENGTH * 0.30
        arrow_base_x = body_cx + fx * BODY_LENGTH * 0.05
        arrow_base_y = body_cy + fy * BODY_LENGTH * 0.05
        pygame.draw.polygon(surface, COLOR_ARROW, [
            (arrow_tip_x,             arrow_tip_y),
            (arrow_base_x - rx * 7,   arrow_base_y - ry * 7),
            (arrow_base_x + rx * 7,   arrow_base_y + ry * 7),
        ])

        # ── 6. Wheels ─────────────────────────────────────────────────────────
        #
        # Wheel centres are on the axle lines, laterally offset by TRACK_WIDTH/2.
        # Rear wheels: zero steer (always parallel to body).
        # Front wheels: Ackermann angles added to body heading.

        hw = TRACK_WIDTH / 2

        # Rear wheels (on rear axle = self.x, self.y)
        rl_x = self.x - rx * hw;  rl_y = self.y - ry * hw
        rr_x = self.x + rx * hw;  rr_y = self.y + ry * hw

        # Front wheels (on front axle)
        fl_x = front_ax_x - rx * hw;  fl_y = front_ax_y - ry * hw
        fr_x = front_ax_x + rx * hw;  fr_y = front_ax_y + ry * hw

        fl_steer, fr_steer = ackermann_angles(self.steer)

        draw_filled_rect(surface, COLOR_WHEEL, COLOR_WHEEL_OUTLINE,
                         fl_x, fl_y, WHEEL_LENGTH, WHEEL_WIDTH, h + fl_steer)
        draw_filled_rect(surface, COLOR_WHEEL, COLOR_WHEEL_OUTLINE,
                         fr_x, fr_y, WHEEL_LENGTH, WHEEL_WIDTH, h + fr_steer)
        draw_filled_rect(surface, COLOR_WHEEL, COLOR_WHEEL_OUTLINE,
                         rl_x, rl_y, WHEEL_LENGTH, WHEEL_WIDTH, h)
        draw_filled_rect(surface, COLOR_WHEEL, COLOR_WHEEL_OUTLINE,
                         rr_x, rr_y, WHEEL_LENGTH, WHEEL_WIDTH, h)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Ackermann Steering Simulation  v3")
    clock = pygame.time.Clock()
    font  = pygame.font.SysFont("monospace", 15)

    # Start the car near the centre; rear axle at spawn point
    car = Car(WINDOW_WIDTH / 2, WINDOW_HEIGHT / 2, heading_deg=0.0)

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if   event.key == pygame.K_ESCAPE: running = False
                elif event.key == pygame.K_LEFT:   car.apply_steer_step(-1)
                elif event.key == pygame.K_RIGHT:  car.apply_steer_step(+1)

        car.update(dt)

        screen.fill(COLOR_BG)
        car.draw(screen)

        # ── HUD ───────────────────────────────────────────────────────────────
        fl, fr = ackermann_angles(car.steer)
        hud = [
            f"Steer (avg):  {car.steer:+.1f}°",
            f"FL / FR:      {fl:+.1f}° / {fr:+.1f}°",
            f"Heading:      {car.heading:.1f}°",
            f"Speed:        {SPEED} px/s",
            "",
            f"← / → : steer ±{STEER_STEP}° per press",
            "ESC : quit",
        ]
        for i, line in enumerate(hud):
            surf = font.render(line, True, (180, 180, 180))
            screen.blit(surf, (10, 10 + i * 20))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
