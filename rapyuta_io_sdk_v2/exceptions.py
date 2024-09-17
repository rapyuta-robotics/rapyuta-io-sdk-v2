class AuthenticationError(Exception):
    """Exception raised for errors in the authentication process."""
    def __init__(self, message="Authentication failed"):
        self.message = message
        super().__init__(self.message)
