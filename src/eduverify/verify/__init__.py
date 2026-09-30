from dataclasses import dataclass


@dataclass
class Issue:
    severity: str  # "error" | "warning"
    code: str
    message: str

    def __str__(self):
        return f"[{self.severity}] {self.code}: {self.message}"
