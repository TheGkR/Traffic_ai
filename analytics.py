from js import window
import math


class TrafficAnalytics:
    def __init__(self, canvas_width, canvas_height):
        self.width = canvas_width
        self.height = canvas_height
        self.total_cars = 0
        self.total_wait_accumulated = 0
        self.start_time = window.performance.now()
        self.history_max_len = 50
        self.density_history = [0] * self.history_max_len
        self.update_timer = 0

    def track_passed_vehicle(self, vehicle):
        self.total_cars += 1
        self.total_wait_accumulated += (vehicle.waiting_time / 60)

    def update(self, vehicles):
        self.update_timer += 1
        if self.update_timer > 10:
            self.update_timer = 0
            current_congestion = sum(v.waiting_time for v in vehicles if v.state == 'APPROACHING') / 100
            self.density_history.append(current_congestion)
            if len(self.density_history) > self.history_max_len:
                self.density_history.pop(0)

    def draw_dashboard(self, ctx, traffic_state, emergency_stats):
        ctx.fillStyle = "rgba(10, 20, 30, 0.9)"
        ctx.fillRect(10, 10, 320, 200)
        ctx.strokeStyle = "rgba(0, 255, 200, 0.5)"
        ctx.lineWidth = 2
        ctx.strokeRect(10, 10, 320, 200)

        parts = traffic_state.split('_')
        direction = parts[0];
        color_name = parts[1]

        ctx.font = "bold 18px Consolas"
        if any(emergency_stats.values()):
            ctx.fillStyle = "#FF4444"
            ctx.fillText("🚨 EMERGENCY OVERRIDE", 25, 35)
        else:
            ctx.fillStyle = "#FFFFFF"
            icon = "🟢" if color_name == "GREEN" else "🟠"
            ctx.fillText(f"SIGNAL: {direction} {color_name} {icon}", 25, 35)

        current_time = (window.performance.now() - self.start_time) / 1000
        avg_wait = 0
        if self.total_cars > 0: avg_wait = self.total_wait_accumulated / self.total_cars
        throughput = (self.total_cars / current_time) * 60 if current_time > 0 else 0

        ctx.font = "12px Consolas";
        ctx.fillStyle = "#AAAAAA"
        ctx.fillText("TOTAL CARS", 25, 65);
        ctx.fillText("AVG WAIT", 125, 65);
        ctx.fillText("FLOW RATE", 225, 65)

        ctx.font = "bold 14px Consolas";
        ctx.fillStyle = "#00FFCC"
        ctx.fillText(f"{self.total_cars}", 25, 85)
        if avg_wait < 5:
            ctx.fillStyle = "#00FF00"
        elif avg_wait < 15:
            ctx.fillStyle = "#FFFF00"
        else:
            ctx.fillStyle = "#FF0000"
        ctx.fillText(f"{avg_wait:.1f}s", 125, 85)
        ctx.fillStyle = "#00BBFF"
        ctx.fillText(f"{int(throughput)}/min", 225, 85)

        graph_x = 25;
        graph_y = 120;
        graph_w = 290;
        graph_h = 50
        ctx.fillStyle = "rgba(0,0,0,0.5)";
        ctx.fillRect(graph_x, graph_y, graph_w, graph_h)
        ctx.beginPath();
        ctx.strokeStyle = "#FFFF00";
        ctx.lineWidth = 2
        max_val = max(self.density_history) if max(self.density_history) > 5 else 5
        for i, val in enumerate(self.density_history):
            px = graph_x + (i / (self.history_max_len - 1)) * graph_w
            py = (graph_y + graph_h) - (val / max_val) * graph_h
            if i == 0:
                ctx.moveTo(px, py)
            else:
                ctx.lineTo(px, py)
        ctx.stroke()
        ctx.fillStyle = "#888";
        ctx.font = "10px Arial"
        ctx.fillText("LIVE CONGESTION LEVEL", graph_x, graph_y - 5)
