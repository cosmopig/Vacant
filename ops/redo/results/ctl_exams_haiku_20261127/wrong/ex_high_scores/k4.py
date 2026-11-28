class HighScores:
    def __init__(self, scores):
        self.scores = list(scores)

    def latest(self):
        return self.scores[-1]

    def personal_best(self):
        return max(self.scores)

    def personal_top_three(self):
        return sorted(set(self.scores), reverse=True)[:3]
