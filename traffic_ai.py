# traffic_ai.py
# System: Pressure-Based Adaptive Control (PB-ACS)
# Logic: Dynamic Scoring with Cycle Cooldowns & Emergency Override

class TrafficBrain:
    def __init__(self):
        # --- TIMING CONFIGURATION (Frames) ---
        self.MIN_GREEN_TIME = 60    # ~1 sec (Prevents rapid flickering)
        self.MAX_GREEN_TIME = 450   # ~7.5 sec (Hard limit to prevent starvation)
        self.ORANGE_TIME = 60       # ~1 sec (Clearance safety buffer)
        
        # --- STATE TRACKING ---
        self.current_phase_timer = 0
        self.pending_switch_target = None
        self.last_green_lane = None # Prevents N-S infinite loops
        
        # --- AI WEIGHTS (The Algorithm's Core) ---
        self.W_QUEUE = 3.0          # High priority on clearing high traffic volume
        self.W_WAIT = 0.05          # Exponential penalty for making cars wait
        self.COOLDOWN_PENALTY = 50.0 # Punishment for a lane that was JUST green

    def calculate_urgency(self, lane, data, current_green_lane):
        """
        Calculates a 'Pressure Score' for a given lane.
        Formula: (Cars * Weight) + (WaitTime * Weight) - (Cooldown)
        """
        count = data[lane]['count']
        wait = data[lane]['total_wait']
        
        # Base Pressure Score
        score = (count * self.W_QUEUE) + (wait * self.W_WAIT)
        
        # Anti-Ping-Pong Logic (Cooldown)
        # If this lane was green right before the current one, penalize it heavily 
        # so other lanes get a fair chance, UNLESS it's critically backed up (>8 cars).
        if lane == self.last_green_lane and count < 8: 
            score -= self.COOLDOWN_PENALTY
            
        # Hysteresis (Survival Bonus)
        # Give a small bonus to the lane that is CURRENTLY green to maintain flow.
        if lane == current_green_lane:
            score += 5.0
            
        return score

    def get_decision(self, current_state, sensor_data, emergency_data):
        self.current_phase_timer += 1
        
        parts = current_state.split('_')
        current_dir = parts[0]
        color = parts[1]
        
        # ==========================================
        # PRIORITY 0: EMERGENCY OVERRIDE (Ambulance)
        # ==========================================
        emergency_lane = None
        for direction, has_ambulance in emergency_data.items():
            if has_ambulance: 
                emergency_lane = direction
                break
            
        if emergency_lane:
            if current_dir == emergency_lane and color == 'GREEN':
                return current_state
            elif current_dir != emergency_lane and color == 'GREEN':
                self.current_phase_timer = 0
                self.pending_switch_target = emergency_lane
                self.last_green_lane = current_dir 
                return f"{current_dir}_ORANGE"

        # ==========================================
        # PRIORITY 1: ORANGE LIGHT SEQUENCER
        # ==========================================
        if color == 'ORANGE':
            if self.current_phase_timer > self.ORANGE_TIME:
                self.current_phase_timer = 0
                next_dir = self.pending_switch_target
                return f"{next_dir}_GREEN"
            return current_state

        # ==========================================
        # PRIORITY 2: ADAPTIVE AI LOGIC (PB-ACS)
        # ==========================================
        elif color == 'GREEN':
            # Safety Lock
            if self.current_phase_timer < self.MIN_GREEN_TIME:
                return current_state
                
            # Calculate Pressures
            scores = {}
            for lane in ['N', 'S', 'E', 'W']:
                scores[lane] = self.calculate_urgency(lane, sensor_data, current_dir)
            
            # Find the strongest competitor
            other_lanes = {k: v for k, v in scores.items() if k != current_dir}
            best_challenger = max(other_lanes, key=other_lanes.get)
            challenger_score = scores[best_challenger]
            current_score = scores[current_dir]
            
            should_switch = False
            
            # Decision Gates
            if self.current_phase_timer > self.MAX_GREEN_TIME:
                should_switch = True
            elif challenger_score > (current_score * 2.0) + 10:
                should_switch = True
            elif current_score < 5.0 and challenger_score > 5.0:
                should_switch = True

            # Execute
            if should_switch:
                self.current_phase_timer = 0
                self.pending_switch_target = best_challenger
                self.last_green_lane = current_dir 
                return f"{current_dir}_ORANGE"
            
            return current_state
