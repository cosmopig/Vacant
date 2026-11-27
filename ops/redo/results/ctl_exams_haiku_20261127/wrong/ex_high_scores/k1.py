class HighScores:
    def __init__(self, scores):
        self.scores = list(scores)

    def latest(self):
        return self.scores[-1]

    def personal_best(self):
        return max(self.scores, default=0)

    def personal_top_three(self):
        return sorted(self.scores, reverse=True)[:min(3, len(self.scores) - 1)]
