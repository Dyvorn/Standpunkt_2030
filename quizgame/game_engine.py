import time
from typing import Dict, List, Optional

class GameEngine:
    def __init__(self):
        self.players: Dict[str, dict] = {}  # sid -> {name, points}
        self.questions: List[dict] = []
        self.current_question_index = -1
        self.state = "SETUP"  # SETUP, LOBBY, QUESTION, RESOLUTION, RESULTS
        self.question_start_time = 0
        self.answers_received = 0

    def add_player(self, sid: str, name: str):
        if sid not in self.players:
            self.players[sid] = {"name": name, "points": 0, "last_correct": False, "rank": 0}

    def load_questions(self, selected_data: List[dict]):
        self.questions = []
        for data in selected_data:
            self.questions.extend(data["fragen"])
        self.current_question_index = -1

    def next_question(self) -> Optional[dict]:
        self.current_question_index += 1
        if self.current_question_index < len(self.questions):
            self.state = "QUESTION"
            self.answers_received = 0
            self.question_start_time = time.time()
            # Reset player answer status
            for p in self.players.values(): p["answered"] = False
            return self.questions[self.current_question_index]
        self.state = "RESULTS"
        return None

    def submit_answer(self, sid: str, answer_index: int) -> bool:
        if self.state != "QUESTION" or sid not in self.players:
            return False
        
        player = self.players[sid]
        if player.get("answered"):
            return False

        current_q = self.questions[self.current_question_index]
        is_correct = current_q["antworten"][answer_index]["korrekt"]
        
        if is_correct:
            elapsed = time.time() - self.question_start_time
            # Max 1000 Punkte, sinkt über 20 Sekunden auf 500, danach konstant
            points = int(max(500, 1000 - (elapsed * 25)))
            player["points"] += points
            player["last_correct"] = True
        else:
            player["last_correct"] = False

        player["answered"] = True
        self.answers_received += 1
        return True

    def get_leaderboard(self) -> List[dict]:
        sorted_players = sorted(
            self.players.values(), 
            key=lambda x: x["points"], 
            reverse=True
        )
        for i, p in enumerate(sorted_players):
            p["rank"] = i + 1
        return sorted_players

    def get_current_question(self):
        if 0 <= self.current_question_index < len(self.questions):
            return self.questions[self.current_question_index]
        return None

    def reset(self):
        self.players = {}
        self.questions = []
        self.current_question_index = -1
        self.state = "SETUP"