import asyncio
import random
import math
from js import document, window

# --- MODULE IMPORTS ---
from traffic_ai import TrafficBrain
from analytics import TrafficAnalytics

brain = TrafficBrain()
analytics = TrafficAnalytics(800, 800)

# --- SYSTEM CONFIG ---
CANVAS_WIDTH = 800
CANVAS_HEIGHT = 800
ROAD_WIDTH = 240
LANE_WIDTH = ROAD_WIDTH / 4
CENTER_X = CANVAS_WIDTH / 2
CENTER_Y = CANVAS_HEIGHT / 2
STOP_DIST = ROAD_WIDTH / 2 + 10

# Traffic Dynamics
SAFE_DISTANCE = 40
BRAKE_FORCE = 0.5

# State
traffic_state = 'N_GREEN'

# Data Bus
sensor_data = {
    'N': {'count': 0, 'total_wait': 0}, 'S': {'count': 0, 'total_wait': 0},
    'E': {'count': 0, 'total_wait': 0}, 'W': {'count': 0, 'total_wait': 0}
}
emergency_stats = {'N': False, 'S': False, 'E': False, 'W': False}

canvas = document.getElementById("trafficCanvas")
canvas.width = CANVAS_WIDTH
canvas.height = CANVAS_HEIGHT
ctx = canvas.getContext("2d")
document.getElementById("loading").innerText = "System Status: Online | Mode: Hybrid AI"


# --- HELPER: BEZIER CURVE ---
def get_bezier_point(t, p0, p1, p2, p3):
    u = 1 - t;
    tt = t * t;
    uu = u * u
    x = (uu * u * p0[0]) + (3 * uu * t * p1[0]) + (3 * u * tt * p2[0]) + (tt * t * p3[0])
    y = (uu * u * p0[1]) + (3 * uu * t * p1[1]) + (3 * u * tt * p2[1]) + (tt * t * p3[1])
    return (x, y)


class Vehicle:
    def __init__(self, start_dir):
        self.start_dir = start_dir
        self.state = 'APPROACHING'
        self.waiting_time = 0
        self.angle = 0
        self.t = 0

        # Generator: 1.5% Ambulance Rate
        if random.random() < 0.015:
            self.type = 'AMBULANCE'
            self.color = "#FFFFFF"
            self.speed = random.uniform(6.5, 8.5)
            self.max_speed = self.speed
            self.width = 24;
            self.length = 45
        else:
            self.type = 'CAR'
            self.color = random.choice(["#E74C3C", "#3498DB", "#F1C40F", "#ECF0F1", "#111111"])
            self.speed = random.uniform(5.0, 7.0)
            self.max_speed = self.speed
            self.width = 22;
            self.length = 40

        # 4-Lane Logic
        self.intention = random.choices(['straight', 'left', 'right'], weights=[50, 25, 25])[0]
        if self.intention == 'left':
            self.lane_index = 0
        elif self.intention == 'right':
            self.lane_index = 1
        else:
            self.lane_index = random.choice([0, 1])

        lane_offset = LANE_WIDTH * 1.5 if self.lane_index == 0 else LANE_WIDTH * 0.5

        if start_dir == 'N':
            self.x = CENTER_X - lane_offset; self.y = CANVAS_HEIGHT + 60; self.vx, self.vy = 0, -1
        elif start_dir == 'S':
            self.x = CENTER_X + lane_offset; self.y = -60; self.vx, self.vy = 0, 1
        elif start_dir == 'E':
            self.x = -60; self.y = CENTER_Y - lane_offset; self.vx, self.vy = 1, 0
        elif start_dir == 'W':
            self.x = CANVAS_WIDTH + 60; self.y = CENTER_Y + lane_offset; self.vx, self.vy = -1, 0

    def get_stop_line_pos(self):
        if self.start_dir == 'N': return CENTER_Y + STOP_DIST
        if self.start_dir == 'S': return CENTER_Y - STOP_DIST
        if self.start_dir == 'E': return CENTER_X - STOP_DIST
        if self.start_dir == 'W': return CENTER_X + STOP_DIST
        return 0

    def check_car_ahead(self, all_vehicles):
        if self.state != 'APPROACHING': return False
        for other in all_vehicles:
            if other is self or other.start_dir != self.start_dir or other.lane_index != self.lane_index: continue

            dist = 9999;
            is_ahead = False
            if self.start_dir == 'N' and other.y < self.y:
                dist = self.y - other.y; is_ahead = True
            elif self.start_dir == 'S' and other.y > self.y:
                dist = other.y - self.y; is_ahead = True
            elif self.start_dir == 'E' and other.x > self.x:
                dist = other.x - self.x; is_ahead = True
            elif self.start_dir == 'W' and other.x < self.x:
                dist = self.x - other.x; is_ahead = True

            if not is_ahead: continue

            # Flow Optimization Physics
            required_gap = SAFE_DISTANCE
            if other.state in ['TURNING', 'DEPARTING']: required_gap = 10
            if self.speed > 3: required_gap += (self.speed * 1.5)
            if other.speed > self.speed and dist > 15: required_gap *= 0.5

            if dist < required_gap: return True
        return False

    def update(self, all_vehicles):
        should_stop = False
        if self.check_car_ahead(all_vehicles): should_stop = True

        if self.state == 'APPROACHING' and not should_stop:
            stop_pos = self.get_stop_line_pos()
            dist = -1
            if self.start_dir == 'N':
                dist = self.y - stop_pos
            elif self.start_dir == 'S':
                dist = stop_pos - self.y
            elif self.start_dir == 'E':
                dist = stop_pos - self.x
            elif self.start_dir == 'W':
                dist = self.x - stop_pos

            if 0 < dist < 120:
                current_dir_green = (traffic_state == f"{self.start_dir}_GREEN")
                current_dir_orange = (traffic_state == f"{self.start_dir}_ORANGE")

                # Emergency Logic
                if self.type == 'AMBULANCE' and current_dir_orange:
                    should_stop = False
                elif current_dir_green:
                    should_stop = False
                elif current_dir_orange:
                    if dist > 40: should_stop = True
                else:
                    should_stop = True

            if dist <= 0: self.start_turn()

        if should_stop:
            self.speed = max(0, self.speed - BRAKE_FORCE)
            self.waiting_time += 1
        else:
            if self.speed < 2:
                self.speed += 0.8  # Launch Boost
            else:
                self.speed = min(self.max_speed, self.speed + 0.2)

        if self.state in ['APPROACHING', 'DEPARTING']:
            self.x += self.vx * self.speed;
            self.y += self.vy * self.speed
            if self.vx == 0 and self.vy == -1:
                self.angle = 0
            elif self.vx == 0 and self.vy == 1:
                self.angle = math.pi
            elif self.vx == 1 and self.vy == 0:
                self.angle = math.pi / 2
            elif self.vx == -1 and self.vy == 0:
                self.angle = -math.pi / 2
        elif self.state == 'TURNING':
            self.t += (self.speed * 0.0055)
            if self.t >= 1.0:
                self.state = 'DEPARTING'
                p_last = self.curve_points[-1];
                p_prev = self.curve_points[-2]
                dx, dy = p_last[0] - p_prev[0], p_last[1] - p_prev[1]
                mag = math.sqrt(dx * dx + dy * dy)
                self.vx, self.vy = dx / mag, dy / mag
            else:
                p0, p1, p2, p3 = self.curve_points
                next_x, next_y = get_bezier_point(self.t, p0, p1, p2, p3)
                self.angle = math.atan2(next_y - self.y, next_x - self.x) + math.pi / 2
                self.x, self.y = next_x, next_y

    def start_turn(self):
        if self.intention == 'straight': self.state = 'DEPARTING'; return
        self.state = 'TURNING';
        self.t = 0
        p0 = (self.x, self.y)
        out_lane_0 = LANE_WIDTH * 1.5;
        out_lane_1 = LANE_WIDTH * 0.5

        if self.start_dir == 'N':
            if self.intention == 'left':
                p3 = (0, CENTER_Y + out_lane_0); p1 = p2 = (self.x, CENTER_Y + out_lane_0)
            elif self.intention == 'right':
                p3 = (CANVAS_WIDTH, CENTER_Y - out_lane_1); p1 = (self.x, CENTER_Y - 100); p2 = (CENTER_X + 100,
                                                                                                 CENTER_Y - out_lane_1)
        elif self.start_dir == 'S':
            if self.intention == 'left':
                p3 = (CANVAS_WIDTH, CENTER_Y - out_lane_0); p1 = p2 = (self.x, CENTER_Y - out_lane_0)
            elif self.intention == 'right':
                p3 = (0, CENTER_Y + out_lane_1); p1 = (self.x, CENTER_Y + 100); p2 = (CENTER_X - 100,
                                                                                      CENTER_Y + out_lane_1)
        elif self.start_dir == 'E':
            if self.intention == 'left':
                p3 = (CENTER_X - out_lane_0, 0); p1 = p2 = (CENTER_X - out_lane_0, self.y)
            elif self.intention == 'right':
                p3 = (CENTER_X + out_lane_1, CANVAS_HEIGHT); p1 = (CENTER_X + 100, self.y); p2 = (CENTER_X + out_lane_1,
                                                                                                  CENTER_Y + 100)
        elif self.start_dir == 'W':
            if self.intention == 'left':
                p3 = (CENTER_X + out_lane_0, CANVAS_HEIGHT); p1 = p2 = (CENTER_X + out_lane_0, self.y)
            elif self.intention == 'right':
                p3 = (CENTER_X - out_lane_1, 0); p1 = (CENTER_X - 100, self.y); p2 = (CENTER_X - out_lane_1,
                                                                                      CENTER_Y - 100)
        self.curve_points = [p0, p1, p2, p3]

    def draw(self):
        ctx.save();
        ctx.translate(self.x, self.y);
        ctx.rotate(self.angle)
        ctx.fillStyle = self.color;
        ctx.fillRect(-self.width / 2, -self.length / 2, self.width, self.length)
        ctx.fillStyle = "black";
        ctx.fillRect(-self.width / 2 + 2, -self.length / 2 + 2, self.width - 4, 10)

        if self.type == 'AMBULANCE':
            if int(window.performance.now() / 200) % 2 == 0:
                ctx.fillStyle = "red";
                ctx.fillRect(-self.width / 2, -5, self.width, 10)
            else:
                ctx.fillStyle = "blue";
                ctx.fillRect(-self.width / 2, -5, self.width, 10)
            ctx.fillStyle = "#D32F2F";
            ctx.fillRect(-2, -8, 4, 10);
            ctx.fillRect(-5, -5, 10, 4)

        if self.state in ['APPROACHING', 'TURNING'] and int(window.performance.now() / 250) % 2 == 0:
            ctx.fillStyle = "#FF9800"
            if self.intention == 'left':
                ctx.fillRect(-self.width / 2 - 2, -self.length / 2, 4, 10)
            elif self.intention == 'right':
                ctx.fillRect(self.width / 2 - 2, -self.length / 2, 4, 10)
        ctx.restore()


vehicles = []


def get_light_color(direction):
    if traffic_state == f"{direction}_GREEN": return "#00FF00"
    if traffic_state == f"{direction}_ORANGE": return "#FF9800"
    return "#FF0000"


def draw_background():
    ctx.fillStyle = "#4CAF50";
    ctx.fillRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT)
    ctx.fillStyle = "#333";
    ctx.fillRect(CENTER_X - ROAD_WIDTH / 2, 0, ROAD_WIDTH, CANVAS_HEIGHT)
    ctx.fillRect(0, CENTER_Y - ROAD_WIDTH / 2, CANVAS_WIDTH, ROAD_WIDTH)

    ctx.strokeStyle = "#F1C40F";
    ctx.lineWidth = 4;
    ctx.setLineDash([])
    ctx.beginPath();
    ctx.moveTo(CENTER_X, 0);
    ctx.lineTo(CENTER_X, CANVAS_HEIGHT);
    ctx.stroke()
    ctx.beginPath();
    ctx.moveTo(0, CENTER_Y);
    ctx.lineTo(CANVAS_WIDTH, CENTER_Y);
    ctx.stroke()
    ctx.strokeStyle = "white";
    ctx.lineWidth = 2;
    ctx.setLineDash([15, 20])
    ctx.beginPath();
    ctx.moveTo(CENTER_X - LANE_WIDTH, 0);
    ctx.lineTo(CENTER_X - LANE_WIDTH, CENTER_Y - ROAD_WIDTH / 2);
    ctx.stroke()
    ctx.beginPath();
    ctx.moveTo(CENTER_X - LANE_WIDTH, CENTER_Y + ROAD_WIDTH / 2);
    ctx.lineTo(CENTER_X - LANE_WIDTH, CANVAS_HEIGHT);
    ctx.stroke()
    ctx.beginPath();
    ctx.moveTo(CENTER_X + LANE_WIDTH, 0);
    ctx.lineTo(CENTER_X + LANE_WIDTH, CENTER_Y - ROAD_WIDTH / 2);
    ctx.stroke()
    ctx.beginPath();
    ctx.moveTo(CENTER_X + LANE_WIDTH, CENTER_Y + ROAD_WIDTH / 2);
    ctx.lineTo(CENTER_X + LANE_WIDTH, CANVAS_HEIGHT);
    ctx.stroke()
    ctx.beginPath();
    ctx.moveTo(0, CENTER_Y - LANE_WIDTH);
    ctx.lineTo(CENTER_X - ROAD_WIDTH / 2, CENTER_Y - LANE_WIDTH);
    ctx.stroke()
    ctx.beginPath();
    ctx.moveTo(CENTER_X + ROAD_WIDTH / 2, CENTER_Y - LANE_WIDTH);
    ctx.lineTo(CANVAS_WIDTH, CENTER_Y - LANE_WIDTH);
    ctx.stroke()
    ctx.beginPath();
    ctx.moveTo(0, CENTER_Y + LANE_WIDTH);
    ctx.lineTo(CENTER_X - ROAD_WIDTH / 2, CENTER_Y + LANE_WIDTH);
    ctx.stroke()
    ctx.beginPath();
    ctx.moveTo(CENTER_X + ROAD_WIDTH / 2, CENTER_Y + LANE_WIDTH);
    ctx.lineTo(CANVAS_WIDTH, CENTER_Y + LANE_WIDTH);
    ctx.stroke()

    # ROI Visualization
    ctx.fillStyle = "rgba(0, 100, 255, 0.1)";
    ctx.strokeStyle = "rgba(0, 100, 255, 0.5)";
    ctx.setLineDash([])
    ctx.fillRect(CENTER_X - ROAD_WIDTH / 2, CANVAS_HEIGHT - 300, ROAD_WIDTH / 2, 290);
    ctx.strokeRect(CENTER_X - ROAD_WIDTH / 2, CANVAS_HEIGHT - 300, ROAD_WIDTH / 2, 290)
    ctx.fillRect(CENTER_X, 10, ROAD_WIDTH / 2, 290);
    ctx.strokeRect(CENTER_X, 10, ROAD_WIDTH / 2, 290)
    ctx.fillRect(10, CENTER_Y - ROAD_WIDTH / 2, 290, ROAD_WIDTH / 2);
    ctx.strokeRect(10, CENTER_Y - ROAD_WIDTH / 2, 290, ROAD_WIDTH / 2)
    ctx.fillRect(CANVAS_WIDTH - 300, CENTER_Y, 290, ROAD_WIDTH / 2);
    ctx.strokeRect(CANVAS_WIDTH - 300, CENTER_Y, 290, ROAD_WIDTH / 2)

    # Signal Lights
    ctx.lineWidth = 6;
    m = ROAD_WIDTH / 2
    ctx.strokeStyle = get_light_color('N');
    ctx.beginPath();
    ctx.moveTo(CENTER_X - m, CENTER_Y + m);
    ctx.lineTo(CENTER_X, CENTER_Y + m);
    ctx.stroke()
    ctx.strokeStyle = get_light_color('S');
    ctx.beginPath();
    ctx.moveTo(CENTER_X, CENTER_Y - m);
    ctx.lineTo(CENTER_X + m, CENTER_Y - m);
    ctx.stroke()
    ctx.strokeStyle = get_light_color('E');
    ctx.beginPath();
    ctx.moveTo(CENTER_X - m, CENTER_Y);
    ctx.lineTo(CENTER_X - m, CENTER_Y - m);
    ctx.stroke()
    ctx.strokeStyle = get_light_color('W');
    ctx.beginPath();
    ctx.moveTo(CENTER_X + m, CENTER_Y);
    ctx.lineTo(CENTER_X + m, CENTER_Y + m);
    ctx.stroke()


def collect_sensor_data():
    global sensor_data, emergency_stats
    current_data = {
        'N': {'count': 0, 'total_wait': 0}, 'S': {'count': 0, 'total_wait': 0},
        'E': {'count': 0, 'total_wait': 0}, 'W': {'count': 0, 'total_wait': 0}
    }
    current_emb = {'N': False, 'S': False, 'E': False, 'W': False}
    DETECT_DIST = 300

    for v in vehicles:
        if v.state != 'APPROACHING': continue
        dist = 9999
        if v.start_dir == 'N':
            dist = v.y - CANVAS_HEIGHT + DETECT_DIST
        elif v.start_dir == 'S':
            dist = DETECT_DIST - v.y
        elif v.start_dir == 'E':
            dist = DETECT_DIST - v.x
        elif v.start_dir == 'W':
            dist = v.x - CANVAS_WIDTH + DETECT_DIST

        if 0 < dist < DETECT_DIST:
            current_data[v.start_dir]['count'] += 1
            current_data[v.start_dir]['total_wait'] += (v.waiting_time / 10)
            if v.type == 'AMBULANCE':
                current_emb[v.start_dir] = True

    sensor_data = current_data
    emergency_stats = current_emb


def is_spawn_clear(direction, lane_index):
    spawn_check_dist = 60
    lane_offset = LANE_WIDTH * 1.5 if lane_index == 0 else LANE_WIDTH * 0.5
    for v in vehicles:
        if v.start_dir != direction or v.lane_index != lane_index: continue
        if direction == 'N' and v.y > CANVAS_HEIGHT - spawn_check_dist: return False
        if direction == 'S' and v.y < spawn_check_dist: return False
        if direction == 'E' and v.x < spawn_check_dist: return False
        if direction == 'W' and v.x > CANVAS_WIDTH - spawn_check_dist: return False
    return True


async def main_loop():
    global traffic_state

    while True:
        # Spawn Logic
        if random.random() < 0.08:
            new_dir = random.choice(['N', 'S', 'E', 'W'])
            intention = random.choices(['straight', 'left', 'right'], weights=[50, 25, 25])[0]
            lane_idx = 0 if intention == 'left' else (1 if intention == 'right' else random.choice([0, 1]))
            if is_spawn_clear(new_dir, lane_idx):
                v = Vehicle(new_dir)
                v.intention = intention;
                v.lane_index = lane_idx
                lane_offset = LANE_WIDTH * 1.5 if lane_idx == 0 else LANE_WIDTH * 0.5
                if new_dir == 'N':
                    v.x = CENTER_X - lane_offset
                elif new_dir == 'S':
                    v.x = CENTER_X + lane_offset
                elif new_dir == 'E':
                    v.y = CENTER_Y - lane_offset
                elif new_dir == 'W':
                    v.y = CENTER_Y + lane_offset
                vehicles.append(v)

        collect_sensor_data()

        # AI Decision
        traffic_state = brain.get_decision(traffic_state, sensor_data, emergency_stats)

        # Analytics
        analytics.update(vehicles)

        draw_background()
        for v in vehicles[:]:
            v.update(vehicles)
            v.draw()
            if (v.x < -100 or v.x > CANVAS_WIDTH + 100 or v.y < -100 or v.y > CANVAS_HEIGHT + 100):
                analytics.track_passed_vehicle(v)
                vehicles.remove(v)

        # Dashboard
        analytics.draw_dashboard(ctx, traffic_state, emergency_stats)

        await asyncio.sleep(0.016)


asyncio.ensure_future(main_loop())
