class ActionResult:
    def __init__(self, success: bool = True, message: str = ""):
        self.success = success
        self.message = message
